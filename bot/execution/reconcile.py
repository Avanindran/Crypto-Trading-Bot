"""
bot/execution/reconcile.py — Startup state reconciliation.

On every bot restart, reconcile internal state against the real API state.
This ensures that:
  1. Stale pending orders from the previous session are cancelled.
  2. Actual open positions (from the balance) override any stale internal state.
  3. Internal position tracking matches reality before trading resumes.

Reconcile is run once at startup, before the main loop begins.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from bot.data.roostoo_client import RoostooClient

logger = logging.getLogger(__name__)


def reconcile_on_startup(
    client: RoostooClient,
    internal_positions: Dict[str, float],
) -> Tuple[Dict[str, float], float]:
    """
    Reconcile bot state against the live API on startup.

    Steps:
      1. Cancel all stale pending orders (clean slate).
      2. Fetch real balance — override internal position tracking.
      3. Log any discrepancies.

    Args:
        client:             Authenticated Roostoo API client.
        internal_positions: Internal position dict (pair → qty) from saved state.

    Returns:
        (reconciled_positions, usd_free)
          reconciled_positions: Updated dict matching real balances.
          usd_free:             Free USD available for new trades.
    """
    logger.info("Starting state reconciliation...")

    # ── Step 1: Cancel all pending orders from previous session ───────────────
    try:
        client.cancel_order()  # No args = cancel all
        logger.info("Cancelled all stale pending orders from previous session")
    except Exception as exc:
        logger.warning("Failed to cancel stale orders (may be none): %s", exc)

    # ── Step 2: Fetch real balances ───────────────────────────────────────────
    try:
        wallet = client.get_balance()
    except Exception as exc:
        logger.error("Failed to fetch balance during reconciliation: %s", exc)
        return internal_positions, 0.0

    usd_free = float(wallet.get("USD", {}).get("Free", 0.0))

    # Build actual positions from real non-zero coin balances
    reconciled: Dict[str, float] = {}
    for coin, balances in wallet.items():
        if coin == "USD":
            continue
        free = float(balances.get("Free", 0.0))
        frozen = float(balances.get("Freeze", 0.0))
        total = free + frozen
        if total > 1e-8:  # Ignore dust (small negative rounding errors)
            pair = f"{coin}/USD"
            reconciled[pair] = total

    # ── Step 3: Log discrepancies ─────────────────────────────────────────────
    internal_pairs = set(internal_positions.keys())
    real_pairs = set(reconciled.keys())

    unexpected = real_pairs - internal_pairs
    missing = internal_pairs - real_pairs

    if unexpected:
        logger.warning(
            "Unexpected positions found in real wallet (not in internal state): %s",
            unexpected,
        )
    if missing:
        logger.warning(
            "Internal positions not found in real wallet (likely filled/closed): %s",
            missing,
        )

    logger.info(
        "Reconciliation complete. USD free=%.2f, positions=%s",
        usd_free,
        {p: f"{q:.6f}" for p, q in reconciled.items()},
    )
    return reconciled, usd_free


def verify_startup_conditions(client: RoostooClient) -> Dict[str, Any]:
    """
    Run pre-flight checks before entering the main loop.

    Checks:
      1. Clock skew (must be < 30s to ensure HMAC signatures are valid)
      2. Exchange info loads successfully with at least 1 pair
      3. USD balance > $1000 (sanity check)

    Raises:
        RuntimeError if any critical check fails.

    Returns:
        Dict with exchange_info and wallet data for the main loop to use.
    """
    import time

    # Check 1: Clock skew
    server_time_ms = client.get_server_time()
    local_time_ms = int(time.time() * 1000)
    skew_ms = abs(server_time_ms - local_time_ms)
    if skew_ms > 30_000:
        raise RuntimeError(
            f"Clock skew {skew_ms}ms exceeds 30s — HMAC signatures will fail. "
            "Sync system clock before running."
        )
    logger.info("Clock skew: %dms (OK)", skew_ms)

    # Check 2: Exchange info
    exchange_info = client.get_exchange_info()
    n_pairs = len(exchange_info.get("TradePairs", {}))
    if n_pairs == 0:
        raise RuntimeError("Exchange info returned 0 tradable pairs")
    logger.info("Exchange info: %d tradable pairs", n_pairs)

    # Check 3: Balance check
    wallet = client.get_balance()
    usd_free = float(wallet.get("USD", {}).get("Free", 0.0))
    if usd_free < 1000:
        raise RuntimeError(f"Insufficient USD balance: {usd_free:.2f}")
    logger.info("USD balance: %.2f (OK)", usd_free)

    return {"exchange_info": exchange_info, "wallet": wallet}
