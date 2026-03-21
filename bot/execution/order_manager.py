"""
bot/execution/order_manager.py — Order lifecycle management.

Handles:
  - Limit order placement with aggressive-passive pricing
  - Timeout cancellation (3 min for entries, 5 min for exits)
  - Emergency market exits when hazard gates trigger
  - Internal pending order tracking (to avoid re-querying the API each loop)

Pricing strategy (maker-fee optimization):
  BUY:  limit = mid + 20% × spread  (aggressive passive — fills when price dips slightly)
  SELL: limit = mid − 20% × spread

At 0.05% maker vs 0.10% taker, saving 0.05% on a 2-way trade = 0.10% round-trip savings.
Over 100 trades on $1M this is ~$1,000 saved — meaningful for competition returns.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import config
from bot.data.roostoo_client import RoostooClient, floor_to_precision, validate_order_params
from bot.infra.logger import log_trade

logger = logging.getLogger(__name__)


@dataclass
class PendingOrder:
    """Tracks an in-flight order for timeout management."""
    order_id: int
    pair: str
    side: str          # "BUY" or "SELL"
    order_type: str    # "LIMIT" or "MARKET"
    quantity: float
    price: Optional[float]
    submitted_at: float  # time.time()
    timeout_seconds: int
    reason: str = ""   # Strategic reason (logged for audit)


class OrderManager:
    """
    Manages the order lifecycle: place, track, cancel on timeout, market-exit on emergency.

    The internal pending order dict is the source of truth between API calls.
    It is reconciled against the real API state on startup and periodically.
    """

    def __init__(self, client: RoostooClient, exchange_info: Dict[str, Any]) -> None:
        self._client = client
        self._exchange_info = exchange_info
        self._pending: Dict[int, PendingOrder] = {}  # order_id → PendingOrder

    # ── Pricing ────────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_limit_price(
        bid: float,
        ask: float,
        side: str,
        price_precision: int,
    ) -> float:
        """
        Compute aggressive-passive limit price.

        BUY:  mid + 20% × spread (closer to ask but still inside)
        SELL: mid − 20% × spread (closer to bid but still inside)

        This aims to fill as a maker while reducing queue-waiting time.
        """
        mid = (bid + ask) / 2.0
        spread = ask - bid
        if side == "BUY":
            raw = mid + config.LIMIT_PRICE_AGGRESSION * spread
        else:
            raw = mid - config.LIMIT_PRICE_AGGRESSION * spread
        return floor_to_precision(raw, price_precision)

    # ── Order placement ────────────────────────────────────────────────────────

    def place_limit_order(
        self,
        pair: str,
        side: str,
        usd_amount: float,
        bid: float,
        ask: float,
        last_price: float,
        reason: str = "",
    ) -> Optional[PendingOrder]:
        """
        Place a limit order for a given USD notional amount.

        Args:
            pair:       e.g. "BTC/USD"
            side:       "BUY" or "SELL"
            usd_amount: Target notional in USD.
            bid, ask:   Current top-of-book prices.
            last_price: Last traded price (fallback for quantity calc).
            reason:     Strategy reason for logging.

        Returns:
            PendingOrder if successfully submitted, None on failure.
        """
        pairs_info = self._exchange_info.get("TradePairs", {})
        if pair not in pairs_info:
            logger.warning("Pair %s not in exchange info — skipping", pair)
            return None

        info = pairs_info[pair]
        price = self._compute_limit_price(bid, ask, side, info["PricePrecision"])
        if price <= 0:
            logger.warning("Invalid limit price %.6f for %s", price, pair)
            return None

        # Convert USD notional to asset quantity
        raw_qty = usd_amount / price
        validated, error = validate_order_params(pair, raw_qty, price, self._exchange_info)
        if error:
            logger.warning("Order validation failed for %s: %s", pair, error)
            return None

        qty, adj_price = validated  # type: ignore[misc]
        timeout = (
            config.ORDER_TIMEOUT_ENTRY_SECONDS
            if side == "BUY"
            else config.ORDER_TIMEOUT_EXIT_SECONDS
        )

        try:
            resp = self._client.place_order(pair=pair, side=side, quantity=qty, price=adj_price)
            if not resp.get("Success", False):
                logger.warning("place_order returned failure for %s %s: %s", side, pair, resp)
                log_trade(pair, side, "LIMIT", qty, adj_price, None, "REJECTED", reason=reason)
                return None

            order_id = int(resp.get("OrderId", 0))
            pending = PendingOrder(
                order_id=order_id,
                pair=pair,
                side=side,
                order_type="LIMIT",
                quantity=qty,
                price=adj_price,
                submitted_at=time.time(),
                timeout_seconds=timeout,
                reason=reason,
            )
            self._pending[order_id] = pending
            log_trade(pair, side, "LIMIT", qty, adj_price, order_id, "SUBMITTED", reason=reason)
            return pending

        except Exception as exc:
            logger.error("place_order exception for %s %s: %s", side, pair, exc)
            return None

    def place_market_order(
        self,
        pair: str,
        side: str,
        quantity: float,
        reason: str = "",
    ) -> bool:
        """
        Place an emergency market order. Used for stop-loss and kill-switch exits.
        Always succeeds or logs failure — never raises.
        """
        try:
            # Validate quantity precision before sending to exchange
            pairs_info = self._exchange_info.get("TradePairs", {})
            if pair not in pairs_info:
                logger.warning("Pair %s not in exchange info — skipping market order", pair)
                return False

            info = pairs_info[pair]
            # Floor quantity to exchange precision
            adj_qty = floor_to_precision(quantity, info["AmountPrecision"])
            
            if adj_qty <= 0:
                logger.warning("Adjusted quantity is zero for %s — skipping market order", pair)
                return False

            resp = self._client.place_order(pair=pair, side=side, quantity=adj_qty)
            success = resp.get("Success", False)
            order_id = resp.get("OrderId")
            status = "FILLED_EST" if success else "REJECTED"
            log_trade(pair, side, "MARKET", adj_qty, None, order_id, status, reason=reason)
            if not success:
                logger.error("Market order failed for %s %s: %s", side, pair, resp)
            return success
        except Exception as exc:
            logger.error("Market order exception for %s %s: %s", side, pair, exc)
            return False

    # ── Timeout management ────────────────────────────────────────────────────

    def cancel_timed_out_orders(self) -> List[PendingOrder]:
        """
        Cancel any pending orders that have exceeded their timeout.
        Called every loop iteration.

        Returns:
            List of orders that were cancelled.
        """
        now = time.time()
        cancelled: List[PendingOrder] = []

        for order_id, order in list(self._pending.items()):
            age = now - order.submitted_at
            if age > order.timeout_seconds:
                logger.info(
                    "Cancelling timed-out order #%d (%s %s, age=%.0fs)",
                    order_id, order.side, order.pair, age,
                )
                try:
                    self._client.cancel_order(pair=order.pair, order_id=order_id)
                    log_trade(
                        order.pair, order.side, order.order_type,
                        order.quantity, order.price, order_id, "CANCELLED_TIMEOUT",
                        reason=f"Timed out after {age:.0f}s",
                    )
                    cancelled.append(order)
                except Exception as exc:
                    logger.warning("Cancel failed for order #%d: %s", order_id, exc)
                finally:
                    # Remove from tracking regardless (avoid infinite cancel loops)
                    self._pending.pop(order_id, None)

        return cancelled

    def remove_pending(self, order_id: int) -> None:
        """Remove an order from tracking (called after confirmed fill)."""
        self._pending.pop(order_id, None)

    def cancel_all(self) -> None:
        """Cancel all tracked pending orders (used for emergency exit)."""
        for order_id, order in list(self._pending.items()):
            try:
                self._client.cancel_order(pair=order.pair, order_id=order_id)
                log_trade(
                    order.pair, order.side, order.order_type,
                    order.quantity, order.price, order_id, "CANCELLED_EMERGENCY",
                    reason="Emergency exit triggered",
                )
            except Exception as exc:
                logger.warning("Cancel failed for order #%d: %s", order_id, exc)
        self._pending.clear()
        logger.info("All pending orders cancelled")

    @property
    def pending_orders(self) -> Dict[int, PendingOrder]:
        return dict(self._pending)

    def add_pending(self, order: PendingOrder) -> None:
        """Add a restored order (used during state reconciliation on startup)."""
        self._pending[order.order_id] = order
