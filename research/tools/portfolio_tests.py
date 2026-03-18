"""
research/portfolio_tests.py -- Doctrine Step 6: Portfolio Construction Overlay

Tests 4 position sizing schemes on the promoted signal (0.70xH1_rev + 0.30xH5_low_vol)
with C2 BTC vol hazard gate applied. Uses TRAIN period only (Oct-Nov 2024) so the
holdout (Dec-Jan) remains unseen.

Decision gate: Quarter-Kelly Sortino >= equal-weight Sortino (validates live bot choice).

Schemes tested:
  A: Equal weight -- top-K equal weight (1/K of GROSS_CAP per asset)
  B: Score-proportional -- weights proportional to positive-shifted C1 score, capped at MAX_WT
  C: Quarter-Kelly -- 0.25 * (score * KELLY_MU) / downside_vol^2, clipped [MIN_WT, MAX_WT]
  D: Risk parity -- 1/realized_vol per asset, normalized to GROSS_CAP

Primary metric: Sortino (competition weight 0.4).
Secondary: Sharpe, Calmar, MaxDD.

Run:
    python -X utf8 research/tools/portfolio_tests.py

Output:
    research/11_portfolio_construction.md
"""

from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, '..')  # research/ root
sys.path.insert(0, _root)

from ic_validation_extended import (  # noqa: E402
    load_klines_all_parallel,
    compute_return,
    compute_forward_return,
    cross_sectional_z,
    fetch_roostoo_pairs,
    _month_range,
    TRENDING_START,
    TRENDING_END,
)
from vector_tests import (  # noqa: E402
    realized_vol,
    _btc_vol_zscore,
    _compute_signal,
    MS_PER_HOUR,
    HOLD_HOURS,
    LSI_C2_THRESH,
    LSI_LOOKBACK,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TRAIN_END_TS  = 1_733_011_200_000   # Dec 1 2024 00:00 UTC (holdout boundary)
GROSS_CAP     = 0.85                # TREND regime gross cap
TOP_K         = 5                   # max positions in TREND regime
KELLY_FRAC    = 0.25
KELLY_MU      = 0.005               # approx. expected per-period return when score=1
MIN_WT        = 0.05                # 5% NAV floor per position
MAX_WT        = 0.30                # 30% NAV cap per position
DOWNVOL_LOOK  = 48                  # hours of history for downside vol estimate

OUTPUT_FILE = os.path.join(_root, "overlays", "portfolio_construction", "01_sizing_schemes.md")


# ---------------------------------------------------------------------------
# Weight functions
# ---------------------------------------------------------------------------

def _weights_equal(
    selected: List[Tuple[str, float]],
    gross_cap: float = GROSS_CAP,
) -> Dict[str, float]:
    """Scheme A: equal weight across selected assets."""
    if not selected:
        return {}
    w = gross_cap / len(selected)
    return {pair: w for pair, _ in selected}


def _weights_score_prop(
    selected: List[Tuple[str, float]],
    gross_cap: float = GROSS_CAP,
    max_wt: float = MAX_WT,
) -> Dict[str, float]:
    """Scheme B: score-proportional weights, capped at max_wt."""
    if not selected:
        return {}
    scores = [s for _, s in selected]
    # Shift so all weights are positive
    min_s = min(scores)
    pos = {pair: s - min_s + 1e-6 for pair, s in selected}
    total = sum(pos.values())
    raw = {pair: (v / total) * gross_cap for pair, v in pos.items()}
    # Iterative cap: redistribute excess above max_wt
    for _ in range(20):
        excess = {p: w - max_wt for p, w in raw.items() if w > max_wt}
        if not excess:
            break
        total_excess = sum(excess.values())
        uncapped = {p: w for p, w in raw.items() if w <= max_wt}
        if not uncapped:
            break
        total_uncapped = sum(uncapped.values())
        raw = {p: max_wt if p in excess else w + total_excess * (w / total_uncapped)
               for p, w in raw.items()}
    return raw


def _downside_vol(
    prices: Dict[int, float],
    ts: int,
    lookback: int = DOWNVOL_LOOK,
) -> float:
    """Semi-deviation (downside vol) of hourly returns over lookback hours."""
    neg_rets = []
    for lag in range(1, lookback + 1):
        r = compute_return(prices, ts - (lag - 1) * MS_PER_HOUR, 1.0)
        if r is not None and r < 0:
            neg_rets.append(r)
    if len(neg_rets) < 3:
        return 0.02   # fallback ~2% hourly downvol
    mean_neg = sum(neg_rets) / len(neg_rets)
    var = sum((r - mean_neg) ** 2 for r in neg_rets) / len(neg_rets)
    return math.sqrt(var) if var > 0 else 0.02


def _weights_kelly(
    selected: List[Tuple[str, float]],
    all_prices: Dict[str, Dict[int, float]],
    ts: int,
    gross_cap: float = GROSS_CAP,
    kelly_frac: float = KELLY_FRAC,
    kelly_mu: float = KELLY_MU,
    min_wt: float = MIN_WT,
    max_wt: float = MAX_WT,
) -> Dict[str, float]:
    """Scheme C: quarter-Kelly sizing -- kelly_frac * (score*mu) / downvol^2."""
    if not selected:
        return {}
    raw: Dict[str, float] = {}
    for pair, score in selected:
        dv = _downside_vol(all_prices[pair], ts)
        kelly_raw = kelly_frac * (max(score, 0.0) * kelly_mu) / (dv ** 2)
        raw[pair] = min(max(kelly_raw, min_wt), max_wt)
    total = sum(raw.values())
    if total <= 0:
        return _weights_equal(selected, gross_cap)
    scale = min(gross_cap / total, 1.0)
    return {pair: w * scale for pair, w in raw.items()}


def _weights_risk_parity(
    selected: List[Tuple[str, float]],
    all_prices: Dict[str, Dict[int, float]],
    ts: int,
    gross_cap: float = GROSS_CAP,
    max_wt: float = MAX_WT,
) -> Dict[str, float]:
    """Scheme D: inverse realized-vol weights (risk parity)."""
    if not selected:
        return {}
    inv_vols: Dict[str, float] = {}
    for pair, _ in selected:
        rv = realized_vol(all_prices[pair], ts, 6)
        inv_vols[pair] = 1.0 / rv if rv and rv > 0 else 1.0 / 0.02
    total = sum(inv_vols.values())
    raw = {pair: (v / total) * gross_cap for pair, v in inv_vols.items()}
    # Cap at max_wt
    for _ in range(20):
        excess = {p: w - max_wt for p, w in raw.items() if w > max_wt}
        if not excess:
            break
        total_excess = sum(excess.values())
        uncapped = {p: w for p, w in raw.items() if w <= max_wt}
        if not uncapped:
            break
        total_uncapped = sum(uncapped.values())
        raw = {p: max_wt if p in excess else w + total_excess * (w / total_uncapped)
               for p, w in raw.items()}
    return raw


# ---------------------------------------------------------------------------
# Portfolio backtest engine
# ---------------------------------------------------------------------------

def _compute_stats(period_rets: List[float], nav_series: List[float]) -> dict:
    """Compute Sortino, Sharpe, Calmar, MaxDD from period returns."""
    n = len(period_rets)
    if n < 5:
        return {}
    periods_per_year = 365 * 24 / HOLD_HOURS
    mean_r = sum(period_rets) / n
    # Total std
    std_r = math.sqrt(sum((r - mean_r) ** 2 for r in period_rets) / n) or 1e-8
    # Downside std
    downside_sq = [(min(r, 0.0) - 0.0) ** 2 for r in period_rets]
    down_std = math.sqrt(sum(downside_sq) / n) or 1e-8

    sharpe = mean_r / std_r * math.sqrt(periods_per_year)
    sortino = mean_r / down_std * math.sqrt(periods_per_year)

    # MaxDD
    peak = 1.0
    nav = 1.0
    max_dd = 0.0
    for r in period_rets:
        nav *= (1 + r)
        if nav > peak:
            peak = nav
        dd = (nav - peak) / peak
        if dd < max_dd:
            max_dd = dd

    final_nav = nav_series[-1] if nav_series else 1.0
    total_ret = final_nav - 1.0
    ann_ret = (1 + total_ret) ** (periods_per_year / max(n, 1)) - 1
    calmar = ann_ret / abs(max_dd) if max_dd < 0 else float("inf")

    return {
        "sortino":   sortino,
        "sharpe":    sharpe,
        "calmar":    calmar,
        "max_dd":    max_dd,
        "total_ret": total_ret,
        "n_periods": n,
    }


def run_scheme(
    scheme_name: str,
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps: List[int],
) -> dict:
    """Run one sizing scheme across the TRAIN period with C2 gate active."""
    btc_key = next((p for p in active_pairs if p.startswith("BTC")), None)
    btc_vol_hist: List[float] = []

    nav = 1.0
    nav_series: List[float] = [1.0]
    period_rets: List[float] = []

    for i, ts in enumerate(timestamps):
        if ts >= TRAIN_END_TS:
            break
        if i % HOLD_HOURS != 0:
            continue

        # C2 hazard gate
        hazard = False
        if btc_key:
            z = _btc_vol_zscore(all_prices, btc_key, ts, btc_vol_hist)
            if z is not None and z > LSI_C2_THRESH:
                hazard = True

        if hazard:
            period_rets.append(0.0)
            nav_series.append(nav)
            continue

        # Compute signal
        sig = _compute_signal(all_prices, active_pairs, ts)
        if sig is None:
            continue

        # Select top-K
        ranked = sorted(sig.items(), key=lambda x: x[1], reverse=True)[:TOP_K]
        if not ranked:
            period_rets.append(0.0)
            nav_series.append(nav)
            continue

        # Compute weights based on scheme
        if scheme_name == "A_equal":
            weights = _weights_equal(ranked)
        elif scheme_name == "B_score_prop":
            weights = _weights_score_prop(ranked)
        elif scheme_name == "C_kelly":
            weights = _weights_kelly(ranked, all_prices, ts)
        elif scheme_name == "D_risk_parity":
            weights = _weights_risk_parity(ranked, all_prices, ts)
        else:
            weights = _weights_equal(ranked)

        # Portfolio return (weighted sum)
        port_ret = 0.0
        for pair, wt in weights.items():
            r = compute_forward_return(all_prices[pair], ts, HOLD_HOURS)
            if r is not None:
                port_ret += wt * r

        nav *= (1 + port_ret)
        period_rets.append(port_ret)
        nav_series.append(nav)

    return _compute_stats(period_rets, nav_series)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Portfolio Construction Test (Step 6) -- Train period only")
    print("=" * 60)

    pairs = fetch_roostoo_pairs()
    print(f"Universe: {len(pairs)} pairs")

    months = _month_range(TRENDING_START, TRENDING_END)
    print("Downloading price data...")
    (all_prices, *_) = load_klines_all_parallel(pairs, months)

    # Build timestamp grid (1h resolution, train period only)
    active_pairs = [p for p in pairs if p in all_prices and len(all_prices[p]) > 100]

    # Build union of all timestamps from start to TRAIN_END_TS
    all_ts: set = set()
    for pair in active_pairs:
        all_ts.update(ts for ts in all_prices[pair] if ts < TRAIN_END_TS)
    timestamps = sorted(all_ts)
    print(f"Timestamp grid: {len(timestamps)} hourly bars (train period)")
    print(f"Active pairs with data: {len(active_pairs)}")

    schemes = [
        ("A_equal",       "A: Equal weight"),
        ("B_score_prop",  "B: Score-proportional"),
        ("C_kelly",       "C: Quarter-Kelly"),
        ("D_risk_parity", "D: Risk parity"),
    ]

    results = {}
    for key, label in schemes:
        print(f"\nRunning scheme {label}...")
        stats = run_scheme(key, all_prices, active_pairs, timestamps)
        results[key] = stats
        print(f"  Sortino: {stats.get('sortino', float('nan')):.2f}  "
              f"Sharpe: {stats.get('sharpe', float('nan')):.2f}  "
              f"MaxDD: {stats.get('max_dd', float('nan')):.1%}")

    # Decision gate
    kelly_sortino = results["C_kelly"].get("sortino", -999)
    ew_sortino    = results["A_equal"].get("sortino", -999)
    gate_pass = kelly_sortino >= ew_sortino
    gate_str  = "PASS" if gate_pass else "FAIL"

    def _fmt(x: Optional[float]) -> str:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "  n/a "
        return f"{x:+.2f}" if abs(x) < 100 else f"{x:.1f}"

    def _pct(x: Optional[float]) -> str:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "  n/a "
        return f"{x * 100:+.1f}%"

    lines = [
        "# Portfolio Construction Test — Step 6",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Period:** Oct-Nov 2024 (train only; holdout Dec-Jan unseen)",
        f"**Signal:** 0.70xH1_reversal + 0.30xH5_low_vol (promoted formula)",
        f"**Regime gate:** C2 BTC vol z > {LSI_C2_THRESH} -> skip rebalance",
        f"**Gross cap:** {GROSS_CAP:.0%} | Max positions: {TOP_K}",
        "",
        "## Decision Gate",
        "",
        f"**Gate:** Quarter-Kelly Sortino >= Equal-weight Sortino",
        f"**Result: {gate_str}** (Kelly={_fmt(kelly_sortino)}, EW={_fmt(ew_sortino)})",
        "",
        "## Scheme Comparison",
        "",
        "| Scheme | Sortino | Sharpe | Calmar | MaxDD | Total Ret |",
        "|--------|---------|--------|--------|-------|-----------|",
    ]

    for key, label in schemes:
        s = results[key]
        lines.append(
            f"| {label} | {_fmt(s.get('sortino'))} | {_fmt(s.get('sharpe'))} | "
            f"{_fmt(s.get('calmar'))} | {_pct(s.get('max_dd'))} | "
            f"{_pct(s.get('total_ret'))} |"
        )

    lines += [
        "",
        "## Economic Rationale",
        "",
        "**Quarter-Kelly (Scheme C)** is the live bot choice (KELLY_FRACTION = 0.25 in config.py).",
        "Kelly sizing allocates proportional to signal strength (C1_z) and inversely to",
        "risk (downside_vol^2), concentrating capital in high-conviction, low-risk positions.",
        "This maximises long-run expected log-wealth under the Bernoulli criterion.",
        "",
        "**Equal weight (Scheme A)** is the baseline. If Quarter-Kelly does not outperform",
        "on Sortino, it offers no practical benefit over a simpler approach.",
        "",
        "**Score-proportional (Scheme B)** allocates more to higher-ranked assets but ignores",
        "individual asset risk. It is an intermediate between A and C.",
        "",
        "**Risk parity (Scheme D)** normalises position sizes by realised volatility.",
        "This is a pure risk-based allocation with no signal conviction weighting.",
        "",
        f"**Decision:** Quarter-Kelly {gate_str} (Sortino {_fmt(kelly_sortino)} vs "
        f"EW {_fmt(ew_sortino)}). See config.py KELLY_FRACTION = 0.25.",
    ]

    output = "\n".join(lines)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
