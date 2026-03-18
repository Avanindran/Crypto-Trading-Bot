"""
main.py — Autonomous crypto momentum bot entry point.

Strategy: Transitional-drift Momentum with Regime-Adaptive Hazard Gating
Thesis:   Exploit incomplete cross-asset expectation diffusion in crypto spot markets.
          Leaders move first; secondary assets update more slowly, creating temporary
          continuation/drift windows.

Scoring formula: PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
  C1_i   = Asset momentum z-score (F-layer / alpha signal)
  λ_t    = Market hazard rate from regime engine (B→C layer)
  M_t_i  = Per-asset diffusion maturity; (1 − M_t) = C3 = remaining drift capacity

Run:
  python main.py

Requires:
  - .env file with ROOSTOO_API_KEY and ROOSTOO_API_SECRET
  - AWS EC2 instance (Sydney region) for live competition
  - tmux for persistent background execution: tmux new-session -d -s bot 'python main.py'
"""
import logging
import os
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv

import config
import state as state_module
from bot.data.fear_greed_client import FearGreedClient
from bot.data.feature_builder import build_all_features
from bot.data.funding_rate_client import FundingRateClient
from bot.data.market_cache import MarketCache
from bot.data.roostoo_client import RoostooClient
from bot.execution.order_manager import OrderManager
from bot.execution.reconcile import reconcile_on_startup, verify_startup_conditions
from bot.infra.logger import log_state, setup_logging
from bot.portfolio.allocator import compute_target_weights, weights_to_usd
from bot.risk.constraints import ConstraintEngine
from bot.risk.drawdown import DrawdownLevel, DrawdownTracker
from bot.risk.kill_switch import (
    check_btc_gate,
    execute_emergency_exit,
    per_position_stop_check,
)
from bot.strategy.maturity import compute_all_maturity
from bot.strategy.ranking import rank_assets, should_exit
from bot.strategy.regime import RegimeEngine, RegimeState
from bot.strategy.signals import compute_c1_scores

logger = logging.getLogger(__name__)


def run() -> None:
    """
    Main bot loop.

    Lifecycle:
      1. Startup checks + state reconciliation
      2. Warmup period (4h — accumulate price history)
      3. Main trading loop:
         a. Fetch ticker
         b. Build features
         c. Compute regime → λ_t
         d. Check risk gates (drawdown, BTC gate, kill switch)
         e. Compute C1, M_t, ranking
         f. Compute target portfolio
         g. Process exits (stop-loss, signal decay, maturity)
         h. Process entries (new positions)
         i. Manage pending orders (cancel timeouts)
         j. Persist state
         k. Log strategy state
         l. Sleep until next loop
    """
    setup_logging()
    load_dotenv()

    api_key = os.getenv("ROOSTOO_API_KEY", "")
    api_secret = os.getenv("ROOSTOO_API_SECRET", "")
    if not api_key or not api_secret:
        raise RuntimeError("ROOSTOO_API_KEY and ROOSTOO_API_SECRET must be set in .env")

    logger.info("=" * 60)
    logger.info("Starting momentum bot — Team178-Hamburglers")
    logger.info("Strategy: Transitional-drift momentum (C1 × exp(-λ) × C3)")
    logger.info("=" * 60)

    # ── Startup checks ─────────────────────────────────────────────────────────
    client = RoostooClient(api_key, api_secret)
    startup_data = verify_startup_conditions(client)
    exchange_info: Dict[str, Any] = startup_data["exchange_info"]
    wallet: Dict[str, Any] = startup_data["wallet"]

    # ── Initialize components ─────────────────────────────────────────────────
    cache = MarketCache(maxlen=config.CACHE_MAXLEN)
    regime_engine = RegimeEngine()
    order_manager = OrderManager(client, exchange_info)
    constraints = ConstraintEngine()
    funding_client = FundingRateClient()
    fng_client = FearGreedClient()

    initial_nav = float(wallet.get("USD", {}).get("Free", 1_000_000.0))
    drawdown_tracker = DrawdownTracker(initial_nav)

    # ── State restoration ─────────────────────────────────────────────────────
    saved = state_module.load_state()
    if saved:
        constraints.from_dict(saved.get("constraints", {}))
        logger.info("Restored position state from disk")
    else:
        logger.info("Starting with clean state")

    # ── Reconcile with live API ────────────────────────────────────────────────
    internal_positions = {
        pair: rec.qty
        for pair, rec in constraints.all_positions().items()
    }
    real_positions, usd_free = reconcile_on_startup(client, internal_positions)

    # Sync constraints with real positions (don't track positions we don't hold)
    for pair in list(constraints.all_positions().keys()):
        if pair not in real_positions:
            constraints.record_exit(pair)

    # ── Get tradable pairs from exchange info ─────────────────────────────────
    tradable_pairs = list(exchange_info.get("TradePairs", {}).keys())
    logger.info("Tradable pairs: %d", len(tradable_pairs))

    # ── Main loop variables ────────────────────────────────────────────────────
    loop_count = 0
    signal_phase = 0   # 0=pre-warmup, 1=restricted(r_30m+r_24h only), 2=partial(+r_2h), 3=full(+r_6h)
    prices_for_nav: Dict[str, float] = {}

    # ── Main loop ──────────────────────────────────────────────────────────────
    while True:
        loop_start = time.time()
        loop_count += 1

        try:
            # ── a. Fetch ticker ────────────────────────────────────────────────
            ticker_data = client.get_ticker()
            if not ticker_data:
                logger.warning("Empty ticker response — skipping loop %d", loop_count)
                time.sleep(config.LOOP_INTERVAL_SECONDS)
                continue

            # Update price cache for NAV computation
            prices_for_nav = {pair: float(info["LastPrice"]) for pair, info in ticker_data.items()}

            # Ingest into rolling cache
            cache.ingest(ticker_data)

            # ── b. Periodic API calls (within rate budget) ─────────────────────
            if loop_count % config.BALANCE_POLL_EVERY_N_LOOPS == 0:
                try:
                    wallet = client.get_balance()
                    usd_free = float(wallet.get("USD", {}).get("Free", usd_free))
                except Exception as exc:
                    logger.warning("Balance poll failed: %s", exc)

            # ── c. Update position price tracking ─────────────────────────────
            for pair in list(constraints.all_positions().keys()):
                price = prices_for_nav.get(pair)
                if price:
                    constraints.update_price(pair, price)

            # ── d. Update drawdown tracker ─────────────────────────────────────
            current_positions = {pair: rec.qty for pair, rec in constraints.all_positions().items()}
            dd_state = drawdown_tracker.update(usd_free, current_positions, prices_for_nav)

            # ── e. Signal quality phase gate ───────────────────────────────────
            #
            # Phase 0: Not enough cache data for any features — wait.
            # Phase 1: r_30m + r_24h + RS available (~30m). Restricted mode.
            # Phase 2: r_2h now available (~2h). Partial mode.
            # Phase 3: r_6h (primary horizon) now available (~6h). Full mode.
            #
            # min_samples is the minimum snapshot count across active tradable pairs.
            active_pairs = [p for p in tradable_pairs if cache.snapshot_count(p) > 0]
            min_samples = cache.min_samples_across_pairs(active_pairs) if active_pairs else 0

            prev_phase = signal_phase
            if min_samples < config.WARMUP_MIN_SAMPLES:
                signal_phase = 0
            elif min_samples < config.WARMUP_PARTIAL_SAMPLES:
                signal_phase = 1
            elif min_samples < config.WARMUP_FULL_SAMPLES:
                signal_phase = 2
            else:
                signal_phase = 3

            if signal_phase != prev_phase:
                phase_labels = {0: "pre-warmup", 1: "restricted", 2: "partial", 3: "full"}
                logger.info(
                    "Signal quality phase: %s → %s (min_samples=%d)",
                    phase_labels[prev_phase], phase_labels[signal_phase], min_samples,
                )

            if signal_phase == 0:
                logger.info("Pre-warmup: %d/%d min samples. Waiting.", min_samples, config.WARMUP_MIN_SAMPLES)
                _persist_and_sleep(constraints, loop_start)
                continue

            # ── f. Fetch external signals (funding rates + Fear & Greed) ──────
            funding_rates = funding_client.get_funding_rates(loop_count)
            fng_value = fng_client.get_fear_greed_value()

            # ── g. Build features ──────────────────────────────────────────────
            asset_features, cs = build_all_features(cache, tradable_pairs, funding_rates)

            # ── h. Compute regime → λ_t ────────────────────────────────────────
            regime, lambda_t = regime_engine.compute(asset_features, cs, fng_value=fng_value)

            # ── i. Kill switch: emergency exit checks ─────────────────────────
            block_entries = False

            # Kill switch 1: Portfolio drawdown
            if dd_state.level == DrawdownLevel.EMERGENCY or dd_state.in_recovery:
                if dd_state.level == DrawdownLevel.EMERGENCY and current_positions:
                    execute_emergency_exit(
                        order_manager, current_positions,
                        reason=f"Portfolio drawdown {dd_state.drawdown_pct:.2%}",
                    )
                    for pair in list(current_positions.keys()):
                        constraints.record_exit(pair)
                    current_positions = {}
                block_entries = True

            # Kill switch 2: BTC gate
            btc_block, btc_emergency, btc_reason = check_btc_gate(asset_features)
            if btc_emergency and current_positions:
                execute_emergency_exit(order_manager, current_positions, reason=btc_reason)
                for pair in list(current_positions.keys()):
                    constraints.record_exit(pair)
                current_positions = {}
            if btc_block:
                block_entries = True
                logger.info("BTC gate blocking new entries: %s", btc_reason)

            # Kill switch 3: Regime is HAZARD_DEFENSIVE
            if regime == RegimeState.HAZARD_DEFENSIVE:
                block_entries = True

            # ── i. Cancel timed-out pending orders ────────────────────────────
            if loop_count % config.PENDING_POLL_EVERY_N_LOOPS == 0:
                order_manager.cancel_timed_out_orders()

            # ── j. Process per-position stops ─────────────────────────────────
            for pair, rec in list(constraints.all_positions().items()):
                price = prices_for_nav.get(pair)
                if not price:
                    continue

                # Hard stop + trailing stop
                stop, stop_reason = per_position_stop_check(
                    pair, rec.entry_price, price, rec.high_since_entry
                )
                if stop:
                    logger.info("Stop triggered for %s: %s", pair, stop_reason)
                    order_manager.place_market_order(pair, "SELL", rec.qty, reason=stop_reason)
                    constraints.record_exit(pair)
                    continue

                # Force exit: max hold time exceeded
                force, force_reason = constraints.should_force_exit(pair)
                if force:
                    logger.info("Force exit %s: %s", pair, force_reason)
                    order_manager.place_market_order(pair, "SELL", rec.qty, reason=force_reason)
                    constraints.record_exit(pair)
                    continue

            # ── k. Compute C1, M_t, ranking ────────────────────────────────────
            c1_scores = compute_c1_scores(asset_features, cs)
            maturity = compute_all_maturity(asset_features)
            ranked = rank_assets(c1_scores, maturity, lambda_t, regime)

            # ── l. Process signal-based exits ─────────────────────────────────
            current_positions = {pair: rec.qty for pair, rec in constraints.all_positions().items()}
            for pair, qty in list(current_positions.items()):
                # Check if signal has decayed enough to exit
                exit_flag, exit_reason = should_exit(pair, c1_scores, maturity)
                if exit_flag:
                    can_exit, hold_reason = constraints.can_exit(pair)
                    if can_exit:
                        logger.info("Signal exit %s: %s", pair, exit_reason)
                        snap = cache.latest(pair)
                        if snap:
                            order_manager.place_limit_order(
                                pair=pair, side="SELL",
                                usd_amount=qty * snap.last_price,
                                bid=snap.bid, ask=snap.ask,
                                last_price=snap.last_price,
                                reason=exit_reason,
                            )
                            constraints.record_exit(pair)
                    else:
                        logger.debug("Exit blocked for %s: %s", pair, hold_reason)

            # ── m. Compute target portfolio (with phase-aware overrides) ───────
            # During thin-signal phases (1 and 2), apply tighter position limits
            # and entry thresholds to compensate for missing return windows.
            if signal_phase == 1:
                phase_max_pos = config.WARMUP_PHASE1_MAX_POSITIONS
                phase_gross_cap = config.WARMUP_PHASE1_GROSS_CAP
                phase_c1_min = config.WARMUP_PHASE1_C1_THRESHOLD
            elif signal_phase == 2:
                phase_max_pos = config.WARMUP_PHASE2_MAX_POSITIONS
                phase_gross_cap = config.WARMUP_PHASE2_GROSS_CAP
                phase_c1_min = config.WARMUP_PHASE2_C1_THRESHOLD
            else:
                phase_max_pos = None   # No phase override — use regime params
                phase_gross_cap = None
                phase_c1_min = None

            # Filter ranked list to phase-aware max positions and C1 threshold
            phase_ranked = ranked
            if phase_max_pos is not None:
                phase_ranked = [r for r in ranked if r.c1_score >= phase_c1_min][:phase_max_pos]

            if not block_entries and phase_ranked:
                dd_gross_override = drawdown_tracker.gross_cap_override(dd_state.level)
                # Apply the more conservative of drawdown override and phase cap
                if phase_gross_cap is not None:
                    gross_override = min(dd_gross_override if dd_gross_override else phase_gross_cap, phase_gross_cap)
                else:
                    gross_override = dd_gross_override
                target_weights = compute_target_weights(
                    phase_ranked, asset_features, regime, gross_override
                )
                target_usd = weights_to_usd(target_weights, drawdown_tracker.current_nav)

                # Process entries for assets not already held
                for pair, target_value in target_usd.items():
                    if pair in current_positions:
                        continue  # Already holding — no action needed

                    # Check entry constraints
                    can_enter, deny_reason = constraints.can_enter(pair)
                    if not can_enter:
                        logger.debug("Entry blocked for %s: %s", pair, deny_reason)
                        continue

                    # Check USD budget
                    if target_value > usd_free * 0.99:
                        target_value = usd_free * 0.99  # Don't exceed available cash

                    if target_value < 10:  # Skip dust entries
                        continue

                    snap = cache.latest(pair)
                    if snap is None:
                        continue

                    pending = order_manager.place_limit_order(
                        pair=pair, side="BUY",
                        usd_amount=target_value,
                        bid=snap.bid, ask=snap.ask,
                        last_price=snap.last_price,
                        reason=f"C1={c1_scores.get(pair, 0):.3f} λ={lambda_t:.2f} regime={regime.value}",
                    )
                    if pending:
                        # Record entry at limit price for stop calculations
                        qty_estimate = target_value / snap.last_price
                        constraints.record_entry(pair, snap.last_price, qty_estimate)
                        usd_free -= target_value  # Track available budget

            # ── n. Persist state ──────────────────────────────────────────────
            _persist_and_log(
                constraints, dd_state, regime, lambda_t,
                c1_scores, maturity, loop_count, signal_phase,
                fng_value=fng_value,
            )

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as exc:
            logger.error("Unexpected error in main loop: %s", exc, exc_info=True)
            # Don't crash — skip cycle and continue

        # ── Sleep until next loop ─────────────────────────────────────────────
        elapsed = time.time() - loop_start
        sleep_time = max(0.0, config.LOOP_INTERVAL_SECONDS - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)


def _persist_and_sleep(constraints: ConstraintEngine, loop_start: float) -> None:
    """Save state and sleep during warmup."""
    state_module.save_state({"constraints": constraints.to_dict()})
    elapsed = time.time() - loop_start
    time.sleep(max(0.0, config.LOOP_INTERVAL_SECONDS - elapsed))


def _persist_and_log(
    constraints: ConstraintEngine,
    dd_state: Any,
    regime: RegimeState,
    lambda_t: float,
    c1_scores: Dict[str, float],
    maturity: Dict[str, float],
    loop_count: int,
    signal_phase: int = 3,
    fng_value: Optional[float] = None,
) -> None:
    """Persist state and emit strategy state log entry."""
    state_data = {"constraints": constraints.to_dict()}
    state_module.save_state(state_data)

    _PHASE_LABELS = {0: "pre-warmup", 1: "restricted", 2: "partial", 3: "full"}

    # Strategy state log (for audit and debugging)
    log_state({
        "loop": loop_count,
        "signal_phase": _PHASE_LABELS[signal_phase],
        "regime": regime.value,
        "lambda_t": lambda_t,
        "fear_greed": round(fng_value) if fng_value is not None else None,
        "drawdown_level": dd_state.level.value,
        "drawdown_pct": round(dd_state.drawdown_pct * 100, 4),
        "peak_nav": round(dd_state.peak_nav, 2),
        "current_nav": round(dd_state.current_nav, 2),
        "positions": list(constraints.all_positions().keys()),
        "top_c1": sorted(c1_scores.items(), key=lambda x: -x[1])[:5] if c1_scores else [],
        "in_recovery": dd_state.in_recovery,
    })


if __name__ == "__main__":
    run()
