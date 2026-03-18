"""
bot/risk/kill_switch.py — Emergency exit logic and BTC direct gates.

Implements two emergency exit paths:

  Path 1 — Portfolio drawdown kill switch
    Triggered when portfolio drawdown ≤ -12% (DRAWDOWN_KILL threshold).
    Cancels all pending orders, then market-sells all positions.

  Path 2 — BTC direct gate (independent of LSI)
    BTC 2h return < -3%:  Block all new long entries
    BTC 2h return < -6%:  Emergency exit all positions

The BTC gate catches fast market crashes that may lag behind the LSI
computation (which uses rolling z-scores and responds more slowly).

After emergency exit, the bot holds 100% cash until the recovery gate
in drawdown.py passes (-8% drawdown from peak).
"""
import logging
from typing import Dict, Optional

import config
from bot.data.feature_builder import AssetFeatures
from bot.execution.order_manager import OrderManager

logger = logging.getLogger(__name__)


def check_btc_gate(
    asset_features: Dict[str, AssetFeatures],
    btc_pair: str = "BTC/USD",
) -> tuple[bool, bool, str]:
    """
    Check BTC-specific entry/exit gates.

    Args:
        asset_features: Per-asset feature dict.
        btc_pair:       Symbol to use as BTC proxy.

    Returns:
        (block_new_entries, trigger_emergency_exit, reason)
    """
    btc = asset_features.get(btc_pair)
    if btc is None or btc.r_2h is None:
        return False, False, ""

    btc_r2h = btc.r_2h

    if btc_r2h <= config.BTC_EMERGENCY_EXIT_RETURN:
        return True, True, f"BTC 2h return {btc_r2h:.2%} ≤ emergency threshold {config.BTC_EMERGENCY_EXIT_RETURN:.2%}"

    if btc_r2h <= config.BTC_BLOCK_NEW_ENTRIES_RETURN:
        return True, False, f"BTC 2h return {btc_r2h:.2%} ≤ block threshold {config.BTC_BLOCK_NEW_ENTRIES_RETURN:.2%}"

    return False, False, ""


def execute_emergency_exit(
    order_manager: OrderManager,
    positions: Dict[str, float],  # pair → qty
    reason: str,
) -> None:
    """
    Execute full emergency exit:
      1. Cancel all pending orders (no new fills contaminating exit)
      2. Market-sell all open positions

    Args:
        order_manager: For cancellation and market orders.
        positions:     Current positions to liquidate.
        reason:        String logged as reason for audit trail.
    """
    logger.warning("EMERGENCY EXIT: %s", reason)

    # Step 1: Cancel all pending orders
    order_manager.cancel_all()

    # Step 2: Market-sell all positions
    for pair, qty in positions.items():
        if qty > 1e-8:
            logger.warning("Emergency market sell: %s qty=%.6f", pair, qty)
            order_manager.place_market_order(
                pair=pair,
                side="SELL",
                quantity=qty,
                reason=f"EMERGENCY EXIT: {reason}",
            )

    logger.warning("Emergency exit complete — all positions liquidated")


def per_position_stop_check(
    pair: str,
    entry_price: float,
    current_price: float,
    high_since_entry: float,
) -> tuple[bool, str]:
    """
    Check per-position stop conditions:
      - Hard stop-loss: current_price < entry_price × (1 + STOP_LOSS_PCT)
      - Trailing stop: current_price < high_since_entry × (1 - TRAILING_STOP_TRAIL_PCT)
        (only active if gain has exceeded TRAILING_STOP_ACTIVATION)

    Returns:
        (should_stop, reason)
    """
    # Hard stop
    stop_price = entry_price * (1.0 + config.STOP_LOSS_PCT)
    if current_price <= stop_price:
        return True, (
            f"Hard stop: price {current_price:.6f} ≤ stop {stop_price:.6f} "
            f"({config.STOP_LOSS_PCT:.1%} from entry {entry_price:.6f})"
        )

    # Trailing stop (only activates after reaching activation threshold)
    max_gain = (high_since_entry - entry_price) / entry_price if entry_price > 0 else 0
    if max_gain >= config.TRAILING_STOP_ACTIVATION:
        trailing_price = high_since_entry * (1.0 - config.TRAILING_STOP_TRAIL_PCT)
        if current_price <= trailing_price:
            return True, (
                f"Trailing stop: price {current_price:.6f} ≤ trailing {trailing_price:.6f} "
                f"(high={high_since_entry:.6f})"
            )

    return False, ""
