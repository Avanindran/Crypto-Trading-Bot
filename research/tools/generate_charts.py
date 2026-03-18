"""
research/generate_charts.py — Generate strategy evaluation charts for judges.

Produces:
  research/charts/deprecated/equity_curve.png  — Strategy NAV vs BTC buy-and-hold with regime overlay (deprecated)
  research/charts/06_vector_tests/drawdown.png — Portfolio drawdown with risk threshold lines

Uses the same simulation as backtest_simulation.py.
Requires: matplotlib (pip install matplotlib)

Run:
  python research/tools/generate_charts.py
"""
import math
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ── Import helpers from backtest_simulation ────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.join(_HERE, '..')  # research/ root
sys.path.insert(0, _ROOT)

from backtest_simulation import (
    FALLBACK_PAIRS, BACKTEST_START_YEAR, BACKTEST_START_MONTH,
    BACKTEST_END_YEAR, BACKTEST_END_MONTH,
    REGIME_PARAMS, STOP_LOSS_PCT, MT_BLOCK_PCT_RANK,
    C1_EXIT_THRESHOLD, FEE_PER_TRADE, REBALANCE_HOURS,
    BTC_VOL_ZSCORE_DEFENSIVE, BTC_VOL_ZSCORE_NEUTRAL, VOL_LOOKBACK_PERIODS,
    fetch_roostoo_pairs, load_all_prices_parallel,
    get_price, compute_return, rolling_vol,
    z_score_current, pct_rank, cross_sectional_z, classify_regime,
)

CHARTS_DIR = os.path.join(_ROOT, "charts")


# ── Simulation with time-series collection ────────────────────────────────────

def run_simulation_for_charts(
    all_prices: Dict[str, Dict[int, float]],
    pairs: List[str] = None,
) -> Tuple[List[int], List[float], List[float], List[float], List[str], List[float]]:
    """
    Re-runs backtest and returns time-series data for charting.

    Returns:
        timestamps       — list of Unix ms timestamps (at rebalance points)
        nav_series       — normalized NAV (strategy, net of fees)
        nav_gross_series — normalized NAV (strategy, pre-fee: nav + cumulative fees paid)
        btc_series       — normalized BTC buy-and-hold
        regime_series    — list of regime strings ('TREND'/'NEUTRAL'/'DEFENSIVE')
        dd_series        — drawdown at each rebalance point
    """
    btc_prices = all_prices.get("BTCUSDT", {})
    if not btc_prices:
        return [], [], [], [], [], []
    btc_ts_sorted = sorted(btc_prices.keys())
    period_start_ts = btc_ts_sorted[0]
    period_start_cutoff = period_start_ts + 48 * 3_600_000

    # Keep only pairs with data from the start of the period (same filter as backtest)
    all_active = {
        sym: p for sym, p in all_prices.items()
        if len(p) > 100 and min(p.keys(), default=period_start_cutoff + 1) <= period_start_cutoff
    }
    if "BTCUSDT" not in all_active:
        all_active["BTCUSDT"] = btc_prices
    active_pairs = list(all_active.keys())
    all_prices = all_active

    # Use BTC timestamps as the main loop driver (same as backtest_simulation.py)
    all_ts = btc_ts_sorted
    if not all_ts:
        return [], [], [], [], [], []

    # BTC normalization baseline
    btc_start = btc_prices.get(all_ts[0], 1.0)

    nav = 1.0
    cash = 1.0
    positions: Dict[str, dict] = {}
    peak_nav = 1.0
    vol_history: List[float] = []
    r6h_history: Dict[str, List[float]] = {p: [] for p in active_pairs}
    last_rebalance_ts = 0
    fees_paid = 0.0

    timestamps: List[int] = []
    nav_series: List[float] = []
    nav_gross_series: List[float] = []
    btc_series: List[float] = []
    regime_series: List[str] = []
    dd_series: List[float] = []

    for ts in all_ts:
        # Update position P&L
        pos_value = 0.0
        for pair, pos in list(positions.items()):
            price = get_price(all_prices[pair], ts)
            if price is None:
                continue
            pos_value += pos["qty_usd"] * (price / pos["entry_price"])

        nav = cash + pos_value
        peak_nav = max(peak_nav, nav)
        dd = (nav - peak_nav) / peak_nav

        # Stop-loss check
        for pair in list(positions.keys()):
            price = get_price(all_prices[pair], ts)
            entry = positions[pair]["entry_price"]
            if price is None or entry is None:
                continue
            ret_from_entry = (price / entry) - 1.0
            if ret_from_entry <= STOP_LOSS_PCT:
                usd_value = positions[pair]["qty_usd"] * (price / entry)
                cash += usd_value * (1 - FEE_PER_TRADE)
                fees_paid += usd_value * FEE_PER_TRADE
                del positions[pair]

        # Only record at rebalance points
        if ts - last_rebalance_ts < REBALANCE_HOURS * 3_600_000:
            continue
        last_rebalance_ts = ts

        regime = classify_regime(btc_prices, ts, vol_history)
        params = REGIME_PARAMS[regime]

        # Compute C1
        r6h_raw: Dict[str, float] = {}
        for pair in active_pairs:
            r6h = compute_return(all_prices[pair], ts, 6)
            if r6h is not None:
                r6h_raw[pair] = r6h
        if len(r6h_raw) < 3:
            continue
        c1_scores = cross_sectional_z(r6h_raw)

        for pair, r6h in r6h_raw.items():
            r6h_history[pair].append(r6h)
            if len(r6h_history[pair]) > 100:
                r6h_history[pair] = r6h_history[pair][-100:]

        # Signal exits
        for pair in list(positions.keys()):
            c1 = c1_scores.get(pair, 0.0)
            mt = pct_rank(r6h_raw.get(pair, 0.0), r6h_history[pair][:-1])
            if c1 < C1_EXIT_THRESHOLD or mt > MT_BLOCK_PCT_RANK:
                price = get_price(all_prices[pair], ts)
                if price:
                    usd_value = positions[pair]["qty_usd"] * (price / positions[pair]["entry_price"])
                    cash += usd_value * (1 - FEE_PER_TRADE)
                    fees_paid += usd_value * FEE_PER_TRADE
                    del positions[pair]

        # New entries
        if params["max_pos"] > 0:
            eligible = []
            for pair, c1 in c1_scores.items():
                if c1 < params["c1_threshold"]:
                    continue
                mt = pct_rank(r6h_raw.get(pair, 0.0), r6h_history[pair][:-1])
                if mt > MT_BLOCK_PCT_RANK or pair in positions:
                    continue
                eligible.append((pair, c1))
            eligible.sort(key=lambda x: -x[1])
            eligible = eligible[:params["max_pos"] - len(positions)]

            pos_value = sum(
                pos["qty_usd"] * (get_price(all_prices[pair], ts) or pos["entry_price"]) / pos["entry_price"]
                for pair, pos in positions.items()
            )
            nav = cash + pos_value

            if eligible:
                total_pos_usd = nav * params["gross_cap"]
                per_position_usd = total_pos_usd / (len(positions) + len(eligible))
                for pair, c1 in eligible:
                    price = get_price(all_prices[pair], ts)
                    if price is None:
                        continue
                    if per_position_usd > cash * 0.99:
                        per_position_usd = cash * 0.99
                    if per_position_usd < 0.001:
                        continue
                    actual_usd = per_position_usd * (1 - FEE_PER_TRADE)
                    cash -= per_position_usd
                    fees_paid += per_position_usd * FEE_PER_TRADE
                    positions[pair] = {
                        "qty_usd": actual_usd,
                        "entry_price": price,
                        "entry_ts": ts,
                    }

        # Record time-series at this rebalance
        pos_value = sum(
            pos["qty_usd"] * (get_price(all_prices[pair], ts) or pos["entry_price"]) / pos["entry_price"]
            for pair, pos in positions.items()
        )
        nav = cash + pos_value
        btc_price_now = btc_prices.get(ts, btc_start)
        btc_norm = btc_price_now / btc_start if btc_start > 0 else 1.0

        timestamps.append(ts)
        nav_series.append(nav)
        nav_gross_series.append(nav + fees_paid)  # pre-fee: add back cumulative fee drag
        btc_series.append(btc_norm)
        regime_series.append(regime)
        dd_series.append(dd)

    return timestamps, nav_series, nav_gross_series, btc_series, regime_series, dd_series


# ── Chart generation ──────────────────────────────────────────────────────────

def generate_charts(
    timestamps: List[int],
    nav_series: List[float],
    nav_gross_series: List[float],
    btc_series: List[float],
    regime_series: List[str],
    dd_series: List[float],
) -> None:
    """Generate and save equity curve and drawdown charts."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.dates import DateFormatter
    except ImportError:
        print("ERROR: matplotlib not installed. Run: pip install matplotlib")
        return

    os.makedirs(CHARTS_DIR, exist_ok=True)

    # Convert timestamps to dates
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    from datetime import timedelta
    dates = [(epoch + timedelta(milliseconds=ts)).replace(tzinfo=None) for ts in timestamps]

    n = len(dates)
    if n < 2:
        print("Not enough data points to generate charts.")
        return

    # ── Chart 1: Equity Curve ──────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 6))

    # Shade HAZARD_DEFENSIVE periods
    in_defensive = False
    def_start = None
    for i, regime in enumerate(regime_series):
        if regime == "DEFENSIVE" and not in_defensive:
            in_defensive = True
            def_start = dates[i]
        elif regime != "DEFENSIVE" and in_defensive:
            ax.axvspan(def_start, dates[i], alpha=0.15, color="#e74c3c", zorder=0)
            in_defensive = False
    if in_defensive:
        ax.axvspan(def_start, dates[-1], alpha=0.15, color="#e74c3c", zorder=0)

    ax.plot(dates, nav_series, color="#2980b9", linewidth=2, label="Strategy (net of fees)", zorder=2)
    ax.plot(dates, nav_gross_series, color="#9b59b6", linewidth=1.5, linestyle="-.",
            label="Strategy (pre-fee: signal performance)", zorder=2)
    ax.plot(dates, btc_series, color="#f39c12", linewidth=1.5, linestyle="--", label="BTC Buy-and-Hold", zorder=2)
    ax.axhline(1.0, color="gray", linewidth=0.8, linestyle=":", alpha=0.6)

    final_nav = nav_series[-1]
    final_nav_gross = nav_gross_series[-1]
    final_btc = btc_series[-1]
    net_return = (final_nav - 1.0) * 100
    gross_return = (final_nav_gross - 1.0) * 100
    ax.annotate(f"{net_return:+.1f}% net", xy=(dates[-1], final_nav),
                xytext=(8, 0), textcoords="offset points",
                color="#2980b9", fontsize=9, va="center")
    ax.annotate(f"{gross_return:+.1f}% pre-fee", xy=(dates[-1], final_nav_gross),
                xytext=(8, 0), textcoords="offset points",
                color="#9b59b6", fontsize=9, va="center")
    btc_return = (final_btc - 1.0) * 100
    ax.annotate(f"{btc_return:+.1f}%", xy=(dates[-1], final_btc),
                xytext=(8, 0), textcoords="offset points",
                color="#f39c12", fontsize=9, va="center")

    # Legend with regime shading explanation
    def_patch = mpatches.Patch(color="#e74c3c", alpha=0.3, label="HAZARD_DEFENSIVE (in cash)")
    handles, labels_list = ax.get_legend_handles_labels()
    ax.legend(handles + [def_patch], labels_list + ["HAZARD_DEFENSIVE (in cash)"],
              loc="upper left", fontsize=9)

    pct_def = sum(1 for r in regime_series if r == "DEFENSIVE") / len(regime_series) * 100
    ax.set_title(
        f"Equity Curve: Transitional-Drift Momentum vs BTC Buy-and-Hold\n"
        f"Oct 2024 – Jan 2025  |  {pct_def:.0f}% of time in HAZARD_DEFENSIVE (cash)",
        fontsize=11, fontweight="bold"
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized NAV (start = 1.0)")
    ax.xaxis.set_major_formatter(DateFormatter("%b %Y"))
    fig.autofmt_xdate()
    plt.tight_layout()

    equity_path = os.path.join(CHARTS_DIR, "deprecated", "equity_curve.png")
    plt.savefig(equity_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Equity curve saved to {equity_path}")

    # ── Chart 2: Drawdown ──────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(14, 5))

    dd_pct = [d * 100 for d in dd_series]
    ax.fill_between(dates, dd_pct, 0, color="#e74c3c", alpha=0.5, label="Drawdown")
    ax.plot(dates, dd_pct, color="#c0392b", linewidth=1)

    # Risk threshold lines
    thresholds = [(-5, "#f39c12", "Caution (-5%)"),
                  (-8, "#e67e22", "Defensive (-8%)"),
                  (-12, "#c0392b", "Kill switch (-12%)")]
    for level, color, label_text in thresholds:
        ax.axhline(level, color=color, linewidth=1.2, linestyle="--", label=label_text)

    max_dd = min(dd_pct)
    ax.annotate(f"Max DD: {max_dd:.1f}%", xy=(dates[dd_pct.index(max_dd)], max_dd),
                xytext=(0, -15), textcoords="offset points",
                ha="center", fontsize=9, color="#c0392b",
                arrowprops=dict(arrowstyle="->", color="#c0392b"))

    ax.set_title(
        "Portfolio Drawdown from Peak\n"
        "Threshold lines: Caution (-5%), Defensive (-8%), Kill switch (-12%)",
        fontsize=11, fontweight="bold"
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown (%)")
    ax.legend(loc="lower left", fontsize=9)
    ax.xaxis.set_major_formatter(DateFormatter("%b %Y"))
    ax.set_ylim(min(min(dd_pct) - 3, -15), 2)
    fig.autofmt_xdate()
    plt.tight_layout()

    dd_path = os.path.join(CHARTS_DIR, "06_vector_tests", "drawdown.png")
    plt.savefig(dd_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Drawdown chart saved to {dd_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Chart Generation — Transitional-Drift Momentum Strategy")
    print(f"Period: {BACKTEST_START_YEAR}-{BACKTEST_START_MONTH:02d} to "
          f"{BACKTEST_END_YEAR}-{BACKTEST_END_MONTH:02d}")
    print("=" * 60)

    print("\nFetching tradable pairs from Roostoo...")
    pairs = fetch_roostoo_pairs()
    print(f"Universe: {len(pairs)} pairs")

    print(f"\nDownloading historical klines ({len(pairs)} symbols)...")
    all_prices = load_all_prices_parallel(pairs)

    if not any(all_prices.values()):
        print("ERROR: No price data. Check internet connection.")
        return

    print("\nRunning simulation for chart data...")
    timestamps, nav_series, nav_gross_series, btc_series, regime_series, dd_series = run_simulation_for_charts(all_prices, pairs)

    if not timestamps:
        print("ERROR: No simulation data returned.")
        return

    print(f"Collected {len(timestamps)} rebalance-point observations.")
    print("\nGenerating charts...")
    generate_charts(timestamps, nav_series, nav_gross_series, btc_series, regime_series, dd_series)
    print(f"\nCharts saved to: {CHARTS_DIR}/")


if __name__ == "__main__":
    main()
