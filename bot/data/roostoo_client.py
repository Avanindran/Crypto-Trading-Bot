"""
bot/data/roostoo_client.py — Roostoo mock-exchange API client.

Implements all 7 endpoints with:
  - HMAC-SHA256 signing for authenticated endpoints
  - Millisecond timestamps throughout
  - 3-retry exponential backoff on connection errors
  - Clean exception handling: API errors are logged and raised;
    callers skip the cycle rather than crashing.

Authentication pattern (per roostoo_demo.py):
  query_string = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
  signature = HMAC-SHA256(secret, query_string).hexdigest()
  headers = {"RST-API-KEY": api_key, "MSG-SIGNATURE": signature}
"""
import hashlib
import hmac
import logging
import math
import time
from typing import Any, Dict, Optional

import requests

import config
from bot.infra.retry import with_retry

logger = logging.getLogger(__name__)

# ── Precision helpers ─────────────────────────────────────────────────────────

def floor_to_precision(value: float, precision: int) -> float:
    """
    Floor a value to the given decimal precision.
    Always floors (never rounds up) to avoid exceeding available balance.

    Args:
        value: Raw quantity or price.
        precision: Number of decimal places (from exchangeInfo AmountPrecision / PricePrecision).

    Returns:
        Value floored to precision decimal places.
    """
    factor = 10 ** precision
    return math.floor(value * factor) / factor


def validate_order_params(
    pair: str,
    quantity: float,
    price: Optional[float],
    exchange_info: Dict[str, Any],
) -> tuple[Optional[tuple[float, Optional[float]]], Optional[str]]:
    """
    Apply exchange precision rules and minimum order check.

    Returns:
        ((adjusted_qty, adjusted_price), None) on success
        (None, error_message) on failure
    """
    pairs_info = exchange_info.get("TradePairs", {})
    if pair not in pairs_info:
        return None, f"Pair {pair} not in exchange info"

    info = pairs_info[pair]
    adj_qty = floor_to_precision(quantity, info["AmountPrecision"])

    if adj_qty <= 0:
        return None, f"Adjusted quantity is zero for {pair}"

    adj_price: Optional[float] = None
    if price is not None:
        adj_price = floor_to_precision(price, info["PricePrecision"])
        notional = adj_price * adj_qty
    else:
        # Market order — use last price for notional check approximation
        notional = quantity * (price or 1.0)

    if notional < info.get("MiniOrder", 0):
        return None, f"Notional {notional:.4f} < MiniOrder {info.get('MiniOrder')} for {pair}"

    return (adj_qty, adj_price), None


# ── Client ────────────────────────────────────────────────────────────────────

class RoostooClient:
    """
    Stateless HTTP client for the Roostoo mock trading API.

    All methods raise on unrecoverable errors after retries are exhausted.
    The main loop catches these and skips the affected cycle.
    """

    def __init__(self, api_key: str, api_secret: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})

    # ── Signature ──────────────────────────────────────────────────────────────

    def _sign(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC-SHA256 signature for signed endpoints.
        Params are sorted alphabetically before hashing (per API spec).
        """
        query_string = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()))
        return hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signed_headers(self, params: Dict[str, Any]) -> Dict[str, str]:
        return {
            "RST-API-KEY": self._api_key,
            "MSG-SIGNATURE": self._sign(params),
        }

    @staticmethod
    def _ts_ms() -> int:
        """Current time as 13-digit millisecond timestamp."""
        return int(time.time() * 1000)

    # ── Public / Timestamp endpoints ──────────────────────────────────────────

    @with_retry()
    def get_server_time(self) -> int:
        """Returns server timestamp in milliseconds."""
        resp = self._session.get(config.BASE_URL + "/v3/serverTime", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        server_ts: int = data.get("ServerTime", data.get("serverTime", 0))
        logger.debug("Server time: %d", server_ts)
        return server_ts

    @with_retry()
    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Returns exchange metadata including precision rules and minimum order sizes.
        Cache the result; refresh only on startup and after schema changes.
        """
        resp = self._session.get(config.BASE_URL + "/v3/exchangeInfo", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("Exchange info loaded: %d pairs", len(data.get("TradePairs", {})))
        return data

    @with_retry()
    def get_ticker(self, pair: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches latest ticker snapshot(s).
        Called every loop — returns all pairs when pair=None (1 API call for all data).

        Response per pair: {MaxBid, MinAsk, LastPrice, Change, CoinTradeValue, UnitTradeValue}
        Change is the 24h percentage change — used directly as r_24h signal.
        """
        params: Dict[str, Any] = {"timestamp": self._ts_ms()}
        if pair:
            params["pair"] = pair
        resp = self._session.get(config.BASE_URL + "/v3/ticker", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("Success", False):
            raise RuntimeError(f"Ticker call failed: {data}")
        return data.get("Data", {})

    # ── Signed endpoints ───────────────────────────────────────────────────────

    @with_retry()
    def get_balance(self) -> Dict[str, Any]:
        """
        Returns wallet balances keyed by coin symbol.
        Structure: {"USD": {"Free": ..., "Freeze": ...}, "BTC": {...}, ...}
        """
        params = {"timestamp": self._ts_ms()}
        resp = self._session.get(
            config.BASE_URL + "/v3/balance",
            params=params,
            headers=self._signed_headers(params),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("Success", False):
            raise RuntimeError(f"Balance call failed: {data}")
        return data.get("Wallet", {})

    @with_retry()
    def get_pending_count(self) -> int:
        """Returns the count of currently pending (unfilled) orders."""
        params = {"timestamp": self._ts_ms()}
        resp = self._session.get(
            config.BASE_URL + "/v3/pending_count",
            params=params,
            headers=self._signed_headers(params),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("Success", False):
            raise RuntimeError(f"pending_count call failed: {data}")
        return int(data.get("Count", 0))

    @with_retry()
    def place_order(
        self,
        pair: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a LIMIT or MARKET order.

        Args:
            pair:     e.g. "BTC/USD"
            side:     "BUY" or "SELL"
            quantity: Asset quantity (already precision-adjusted)
            price:    Limit price (None → MARKET order)

        Returns:
            API response dict with order_id and status.
        """
        params: Dict[str, Any] = {
            "timestamp": self._ts_ms(),
            "pair": pair,
            "side": side,
            "quantity": quantity,
        }
        if price is not None:
            params["type"] = "LIMIT"
            params["price"] = price
        else:
            params["type"] = "MARKET"

        resp = self._session.post(
            config.BASE_URL + "/v3/place_order",
            data=params,
            headers=self._signed_headers(params),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("Success", False):
            logger.warning("place_order failed for %s %s: %s", side, pair, data)
        else:
            logger.info("Order placed: %s %s qty=%.6f price=%s id=%s",
                        side, pair, quantity, price, data.get("OrderId"))
        return data

    @with_retry()
    def cancel_order(
        self,
        pair: Optional[str] = None,
        order_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Cancel orders. With no arguments, cancels ALL pending orders.
        Provide pair to cancel all orders for that pair, or order_id for a specific order.
        """
        params: Dict[str, Any] = {"timestamp": self._ts_ms()}
        if pair:
            params["pair"] = pair
        if order_id is not None:
            params["order_id"] = order_id

        resp = self._session.post(
            config.BASE_URL + "/v3/cancel_order",
            data=params,
            headers=self._signed_headers(params),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("cancel_order: pair=%s order_id=%s result=%s", pair, order_id, data.get("Success"))
        return data

    @with_retry()
    def query_order(
        self,
        pair: Optional[str] = None,
        order_id: Optional[int] = None,
        pending_only: bool = False,
    ) -> Dict[str, Any]:
        """Query order history or a specific order."""
        params: Dict[str, Any] = {"timestamp": self._ts_ms()}
        if pair:
            params["pair"] = pair
        if order_id is not None:
            params["order_id"] = order_id
        if pending_only:
            params["pending_only"] = True

        resp = self._session.post(
            config.BASE_URL + "/v3/query_order",
            data=params,
            headers=self._signed_headers(params),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data
