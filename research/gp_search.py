"""
research/gp_search.py — Constrained formula combination search (GP Phase 3).

Search space declared in: 04_gp_search/H1_H5_gp.md (FROZEN before this run).

Tests weighted linear combinations of passing terminals:
  Terminals: H1_neg_r1h, H1_neg_r2h, H1_neg_c1, H5_neg_vol
  Operator:  w * T1 + (1-w) * T2   (w in 0.0..1.0 by 0.1)
  Objective: IC Sharpe at 4h forward return (inner training split)
  Holdout:   Dec 2024–Jan 2025 (last 2 months)

Run:
  python research/gp_search.py

Outputs:
  research/04_gp_search/H1_H5_gp_results.md
"""

import math
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from ic_validation_extended import (  # noqa: E402
    load_klines_all_parallel,
    compute_return,
    compute_forward_return,
    cross_sectional_z,
    z_score,
    spearman_ic,
    fetch_roostoo_pairs,
    _month_range,
    C1_WEIGHT_R30M,
    C1_WEIGHT_R2H,
    C1_WEIGHT_R6H,
    C1_WEIGHT_R24H,
    C1_WEIGHT_CS_RS,
)

# ── Configuration ──────────────────────────────────────────────────────────────

FWD_HORIZONS = [1, 2, 4, 6, 12, 24]
OPT_HORIZON  = 4       # optimize GP objective at this horizon (REBALANCE_HOURS)

# Training split: Oct–Nov 2024 (inner train), Dec–Jan (holdout)
TRAIN_START  = (2024, 10)
TRAIN_END    = (2024, 11)
HOLDOUT_START = (2024, 12)
HOLDOUT_END   = (2025,  1)

IC_PROMOTE_MIN = 0.03
TSTAT_PROMOTE  = 1.5

GP_RESULTS_FILE = os.path.join(_here, "04_gp_search", "H1_H5_gp_results.md")

# Terminal signal names in order (declared in H1_H5_gp.md)
TERMINALS = ["H1_neg_r1h", "H1_neg_r2h", "H1_neg_c1", "H5_neg_vol"]

# All pairwise combinations to test
COMBOS = [
    ("H1_neg_r1h", "H5_neg_vol"),
    ("H1_neg_r2h", "H5_neg_vol"),
    ("H1_neg_c1",  "H5_neg_vol"),
    ("H1_neg_r1h", "H1_neg_r2h"),
    ("H1_neg_r1h", "H1_neg_c1"),
    ("H1_neg_r2h", "H1_neg_c1"),
]
WEIGHT_GRID = [round(w * 0.1, 1) for w in range(11)]  # 0.0 to 1.0


# ── Volatility Helper ──────────────────────────────────────────────────────────

def realized_vol(prices: Dict[int, float], ts: int, hours: int = 6) -> Optional[float]:
    rets = []
    for lag in range(1, hours + 1):
        r = compute_return(prices, ts - lag * 3_600_000, 1.0)
        if r is not None:
            rets.append(r)
    if len(rets) < max(3, hours // 2):
        return None
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets)) or 1e-8


def t_stat(ic: float, n: int) -> float:
    if n <= 2 or abs(ic) >= 1.0:
        return 0.0
    return ic * math.sqrt(n - 2) / math.sqrt(1 - ic ** 2 + 1e-12)


def ic_stats(period_ics: List[float]) -> dict:
    n = len(period_ics)
    if n < 3:
        return {"n": n, "mean_ic": None, "ic_sharpe": None, "t_stat": None}
    mean_ic = sum(period_ics) / n
    std_ic = math.sqrt(sum((v - mean_ic) ** 2 for v in period_ics) / n) or 1e-8
    ic_sharpe = mean_ic / std_ic
    t = mean_ic / (std_ic / math.sqrt(n))
    return {"n": n, "mean_ic": mean_ic, "ic_sharpe": ic_sharpe, "t_stat": t}


# ── Signal Computation ─────────────────────────────────────────────────────────

def compute_signals_at_ts(
    all_prices: Dict[str, Dict[int, float]],
    all_open:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts: int,
) -> Tuple[Dict[str, Dict[str, float]], Dict[int, Dict[str, float]]]:
    """Compute all terminal signals and forward returns for one timestamp.

    Returns:
        signals: {signal_name: {pair: z_value}}
        fwd:     {horizon_h: {pair: fwd_return}}
    """
    n_min = max(5, len(active_pairs) // 4)

    r1h_raw:  Dict[str, float] = {}
    r2h_raw:  Dict[str, float] = {}
    r6h_raw:  Dict[str, float] = {}
    r24h_raw: Dict[str, float] = {}

    for pair in active_pairs:
        r1h  = compute_return(all_prices[pair], ts, 1.0)
        r2h  = compute_return(all_prices[pair], ts, 2.0)
        r6h  = compute_return(all_prices[pair], ts, 6.0)
        r24h = compute_return(all_prices[pair], ts, 24.0)
        if None in (r1h, r2h, r6h, r24h):
            continue
        r1h_raw[pair]  = r1h
        r2h_raw[pair]  = r2h
        r6h_raw[pair]  = r6h
        r24h_raw[pair] = r24h

    if len(r6h_raw) < n_min:
        return {}, {}

    # C1 raw for H1_neg_c1
    median_r2h = sorted(r2h_raw.values())[len(r2h_raw) // 2]
    c1_raw = {
        pair: (C1_WEIGHT_R30M * r1h_raw.get(pair, 0.0)
               + C1_WEIGHT_R2H   * r2h_raw.get(pair, 0.0)
               + C1_WEIGHT_R6H   * r6h_raw.get(pair, 0.0)
               + C1_WEIGHT_R24H  * r24h_raw.get(pair, 0.0)
               + C1_WEIGHT_CS_RS * (r2h_raw.get(pair, 0.0) - median_r2h))
        for pair in r6h_raw
    }

    # H5_neg_vol
    neg_vol_raw: Dict[str, float] = {}
    for pair in r6h_raw:
        rv = realized_vol(all_prices[pair], ts, 6)
        if rv is not None:
            neg_vol_raw[pair] = -rv

    # Build signal dicts (CS z-normalized)
    sig: Dict[str, Dict[str, float]] = {}
    sig["H1_neg_r1h"] = cross_sectional_z({p: -v for p, v in r1h_raw.items()})
    sig["H1_neg_r2h"] = cross_sectional_z({p: -v for p, v in r2h_raw.items()})
    sig["H1_neg_c1"]  = cross_sectional_z({p: -v for p, v in c1_raw.items()})
    if len(neg_vol_raw) >= n_min:
        sig["H5_neg_vol"] = cross_sectional_z(neg_vol_raw)

    # Forward returns at all horizons
    fwd: Dict[int, Dict[str, float]] = {h: {} for h in FWD_HORIZONS}
    for pair in r6h_raw:
        for h in FWD_HORIZONS:
            fr = compute_forward_return(all_prices[pair], ts, h)
            if fr is not None:
                fwd[h][pair] = fr

    return sig, fwd


def accumulate_period_ics(
    sig_vals: Dict[str, float],
    fwd_h: Dict[str, float],
) -> Optional[float]:
    """Compute one cross-sectional Spearman IC at one horizon."""
    common = [p for p in sig_vals if p in fwd_h]
    if len(common) < 5:
        return None
    return spearman_ic(
        [sig_vals[p] for p in common],
        [fwd_h[p]    for p in common],
    )


# ── GP Run ─────────────────────────────────────────────────────────────────────

def run_gp(
    all_prices: Dict[str, Dict[int, float]],
    all_open:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    months_list: List[Tuple[int, int]],
    label: str,
) -> Dict[str, Dict[int, List[float]]]:
    """Accumulate per-timestamp ICs for all terminals + combinations.

    Returns {signal_or_combo_name: {horizon: [ic_per_ts, ...]}}
    """
    # Build set of unique timestamps in this split's months
    # (use timestamps from BTC as reference since BTC has complete data)
    btc_ts = set(all_prices.get("BTCUSDT", {}).keys())
    split_start_ts = _months_to_ts_range(months_list[0])
    split_end_ts   = _months_to_ts_range(months_list[-1], end=True)
    split_ts = sorted(
        ts for ts in btc_ts
        if split_start_ts <= ts <= split_end_ts
    )

    print(f"  [{label}] {len(split_ts)} timestamps to process...")

    # All signal/combo names
    combo_names = [
        f"{t1}_x{round(w*10):02d}_{t2}"
        for t1, t2 in COMBOS
        for w in WEIGHT_GRID
    ]
    all_names = TERMINALS + combo_names

    period_ics: Dict[str, Dict[int, List[float]]] = {
        name: {h: [] for h in FWD_HORIZONS} for name in all_names
    }

    for idx, ts in enumerate(split_ts):
        if idx % 200 == 0:
            print(f"    [{idx}/{len(split_ts)}]...", flush=True)

        sig, fwd = compute_signals_at_ts(all_prices, all_open, active_pairs, ts)
        if not sig or not fwd:
            continue

        # Individual terminal ICs
        for name in TERMINALS:
            if name not in sig:
                continue
            for h in FWD_HORIZONS:
                ic = accumulate_period_ics(sig[name], fwd[h])
                if ic is not None:
                    period_ics[name][h].append(ic)

        # Combination ICs
        for t1, t2 in COMBOS:
            if t1 not in sig or t2 not in sig:
                continue
            s1 = sig[t1]
            s2 = sig[t2]
            common_pairs = [p for p in s1 if p in s2]
            if len(common_pairs) < 5:
                continue

            for w in WEIGHT_GRID:
                combo_vals = {p: w * s1[p] + (1 - w) * s2[p] for p in common_pairs}
                combo_name = f"{t1}_x{round(w*10):02d}_{t2}"
                for h in FWD_HORIZONS:
                    ic = accumulate_period_ics(combo_vals, fwd[h])
                    if ic is not None:
                        period_ics[combo_name][h].append(ic)

    return period_ics


def _months_to_ts_range(ym: Tuple[int, int], end: bool = False) -> int:
    """Convert (year, month) to start/end millisecond timestamp."""
    from datetime import datetime, timezone
    y, m = ym
    if end:
        # End of month (approx: start of next month minus 1 hour)
        nm = m + 1
        ny = y
        if nm > 12:
            nm = 1
            ny += 1
        return int(datetime(ny, nm, 1, tzinfo=timezone.utc).timestamp() * 1000) - 3_600_000
    return int(datetime(y, m, 1, tzinfo=timezone.utc).timestamp() * 1000)


# ── Output Formatting ──────────────────────────────────────────────────────────

def select_best_combo(
    train_ics: Dict[str, Dict[int, List[float]]],
    holdout_ics: Dict[str, Dict[int, List[float]]],
    opt_h: int,
) -> Tuple[str, dict, dict]:
    """Select the best formula by IC Sharpe on inner training set at opt_h.

    Returns (best_name, train_stats_at_opt_h, holdout_stats_at_opt_h).
    """
    best_name  = None
    best_sharpe = -999.0

    for name in train_ics:
        s = ic_stats(train_ics[name].get(opt_h, []))
        if s["ic_sharpe"] is not None and s["ic_sharpe"] > best_sharpe:
            if s["mean_ic"] is not None and s["mean_ic"] > 0:
                best_sharpe = s["ic_sharpe"]
                best_name   = name

    if best_name is None:
        return "none", {}, {}

    train_s   = ic_stats(train_ics[best_name].get(opt_h, []))
    holdout_s = ic_stats(holdout_ics.get(best_name, {}).get(opt_h, []))
    return best_name, train_s, holdout_s


def write_results_md(
    train_ics:   Dict[str, Dict[int, List[float]]],
    holdout_ics: Dict[str, Dict[int, List[float]]],
    best_name:   str,
    train_best:  dict,
    holdout_best: dict,
) -> None:
    """Write GP results to 04_gp_search/H1_H5_gp_results.md."""

    def fmt_cell(s: dict) -> str:
        ic = s.get("mean_ic")
        t  = s.get("t_stat")
        if ic is None:
            return "  N/A "
        star = "*" if t is not None and abs(t) > TSTAT_PROMOTE else " "
        return f"{ic:+.3f}{star}"

    lines = [
        "# H1+H5 GP Search Results",
        "",
        f"**Run:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Search space:** `04_gp_search/H1_H5_gp.md` (pre-committed FROZEN)  ",
        f"**Inner train:** Oct–Nov 2024  |  **Holdout:** Dec 2024–Jan 2025  ",
        f"**Optimizing:** IC Sharpe at {OPT_HORIZON}h forward return  ",
        "",
        f"Star `*` = |t| > {TSTAT_PROMOTE}.",
        "",
        "## Individual Terminals — Train vs Holdout IC",
        "",
        f"| Signal | Train_{OPT_HORIZON}h | Holdout_{OPT_HORIZON}h | "
        + " | ".join(f"T{h}h" for h in FWD_HORIZONS if h != OPT_HORIZON) + " |",
        "|--------|---------|---------|" + "|------|" * (len(FWD_HORIZONS) - 1),
    ]

    for t in TERMINALS:
        ts = ic_stats(train_ics.get(t, {}).get(OPT_HORIZON, []))
        hs = ic_stats(holdout_ics.get(t, {}).get(OPT_HORIZON, []))
        other_cols = [
            fmt_cell(ic_stats(train_ics.get(t, {}).get(h, [])))
            for h in FWD_HORIZONS if h != OPT_HORIZON
        ]
        lines.append(
            f"| `{t}` | {fmt_cell(ts)} | {fmt_cell(hs)} | "
            + " | ".join(other_cols) + " |"
        )

    lines += ["", "## Top Combinations by IC Sharpe at {OPT_HORIZON}h (inner train)", ""]
    lines[-1] = lines[-1].format(OPT_HORIZON=OPT_HORIZON)

    # Collect all combos, sort by IC Sharpe on train at OPT_HORIZON
    combo_results = []
    for t1, t2 in COMBOS:
        for w in WEIGHT_GRID:
            if w == 0.0 or w == 1.0:
                continue  # pure terminal — already shown above
            name = f"{t1}_x{round(w*10):02d}_{t2}"
            ts_  = ic_stats(train_ics.get(name, {}).get(OPT_HORIZON, []))
            hs_  = ic_stats(holdout_ics.get(name, {}).get(OPT_HORIZON, []))
            if ts_["ic_sharpe"] is not None:
                combo_results.append((ts_["ic_sharpe"], w, t1, t2, name, ts_, hs_))

    combo_results.sort(reverse=True)

    lines += [
        f"| Formula | w | Train IC | Train IC-Sharpe | Holdout IC | Holdout t |",
        "|---------|---|----------|----------------|-----------|---------|",
    ]
    for sharpe, w, t1, t2, name, ts_, hs_ in combo_results[:20]:
        formula = f"{w:.1f}×{t1} + {1-w:.1f}×{t2}"
        h_ic  = f"{hs_['mean_ic']:+.3f}" if hs_["mean_ic"] is not None else "N/A"
        h_t   = f"{hs_['t_stat']:+.2f}"  if hs_["t_stat"]  is not None else "N/A"
        lines.append(
            f"| {formula} | {w:.1f} | {fmt_cell(ts_)} | {sharpe:+.3f} "
            f"| {h_ic} | {h_t} |"
        )

    # Best formula section
    lines += [
        "",
        "## Selected Formula",
        "",
        f"**Best by IC Sharpe on inner train (4h):** `{best_name}`  ",
    ]
    if train_best.get("mean_ic") is not None:
        lines += [
            f"- Train IC at {OPT_HORIZON}h: {train_best['mean_ic']:+.4f} "
            f"(IC-Sharpe: {train_best['ic_sharpe']:+.3f}, t={train_best['t_stat']:+.2f})  ",
            f"- Holdout IC at {OPT_HORIZON}h: "
            + (f"{holdout_best['mean_ic']:+.4f} (t={holdout_best['t_stat']:+.2f})"
               if holdout_best.get("mean_ic") is not None else "N/A"),
        ]

    holdout_pass = (
        holdout_best.get("mean_ic") is not None
        and holdout_best["mean_ic"] > 0
        and holdout_best.get("t_stat") is not None
        and abs(holdout_best["t_stat"]) > 1.0
    )

    lines += [
        "",
        "**Holdout gate (IC>0, t>1.0):** " + ("PASS" if holdout_pass else "FAIL"),
        "",
        "## Promotion Decision",
        "",
    ]

    # Parse best_name to get formula
    if "_x" in best_name:
        parts = best_name.split("_x")
        t1_name = parts[0]
        rest    = "_x".join(parts[1:])
        w_str, t2_name = rest.split("_", 1)
        w_val = int(w_str) / 10.0
        formula_str = (
            f"CS_z({w_val:.1f} × ({t1_name}) + {1-w_val:.1f} × ({t2_name}))"
        )
        economic_desc = (
            f"{w_val:.0%} short-term reversal ({t1_name}) + "
            f"{1-w_val:.0%} low-volatility stability ({t2_name})"
        )
    else:
        formula_str = f"CS_z({best_name})"
        economic_desc = best_name

    if holdout_pass and train_best.get("mean_ic", 0) > IC_PROMOTE_MIN:
        lines += [
            f"**PROMOTED:** `{best_name}`  ",
            f"Formula: `{formula_str}`  ",
            f"Economic description: {economic_desc}  ",
            "",
            "See `09_robustness/` for block-resampling and parameter perturbation tests.",
        ]
    else:
        lines += [
            "**NOT PROMOTED:** Formula fails holdout gate or IC < 0.03.  ",
            "Fall back to best individual terminal (H5_neg_vol or H1_neg_r1h).  ",
            "See `09_robustness/` for robustness of individual terminal.",
        ]

    os.makedirs(os.path.dirname(GP_RESULTS_FILE), exist_ok=True)
    with open(GP_RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written: {GP_RESULTS_FILE}")


# ── Entry Point ────────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 72)
    print("gp_search.py -- Constrained combination search (H1 + H5)")
    print("=" * 72)

    print("\nFetching Roostoo universe...")
    pairs = fetch_roostoo_pairs()
    print(f"  {len(pairs)} pairs")

    # Download full trending period (needed for both splits)
    all_months = _month_range((2024, 10), (2025, 1))
    print(f"\nDownloading Oct 2024–Jan 2025 ({len(pairs)} pairs × {len(all_months)} months)...")
    (all_prices, _bvol, _qvol, _ntrades, _tbvol,
     all_open, all_high, all_low) = load_klines_all_parallel(
        pairs, all_months, max_workers=8,
    )

    active_pairs = [sym for sym, p in all_prices.items() if len(p) > 100]
    print(f"  {len(active_pairs)}/{len(pairs)} pairs have sufficient data")

    # Inner training split: Oct–Nov 2024
    print("\nRunning INNER TRAINING split (Oct–Nov 2024)...")
    train_months = _month_range(TRAIN_START, TRAIN_END)
    train_ics = run_gp(all_prices, all_open, active_pairs, train_months, "TRAIN")

    # Holdout split: Dec 2024–Jan 2025
    print("\nRunning HOLDOUT split (Dec 2024–Jan 2025)...")
    holdout_months = _month_range(HOLDOUT_START, HOLDOUT_END)
    holdout_ics = run_gp(all_prices, all_open, active_pairs, holdout_months, "HOLDOUT")

    # Select best formula on training IC Sharpe
    best_name, train_best, holdout_best = select_best_combo(
        train_ics, holdout_ics, OPT_HORIZON
    )
    print(f"\nBest formula (training IC Sharpe at {OPT_HORIZON}h): {best_name}")
    if train_best.get("mean_ic") is not None:
        print(f"  Train IC:   {train_best['mean_ic']:+.4f} "
              f"(IC-Sharpe={train_best['ic_sharpe']:+.3f}, t={train_best['t_stat']:+.2f})")
    if holdout_best.get("mean_ic") is not None:
        print(f"  Holdout IC: {holdout_best['mean_ic']:+.4f} "
              f"(t={holdout_best['t_stat']:+.2f})")

    # Print terminal comparison at opt_h
    print(f"\nIndividual terminals at {OPT_HORIZON}h (train | holdout):")
    for t in TERMINALS:
        ts_ = ic_stats(train_ics.get(t, {}).get(OPT_HORIZON, []))
        hs_ = ic_stats(holdout_ics.get(t, {}).get(OPT_HORIZON, []))
        t_ic  = f"{ts_['mean_ic']:+.4f}" if ts_["mean_ic"] is not None else " N/A  "
        h_ic  = f"{hs_['mean_ic']:+.4f}" if hs_["mean_ic"] is not None else " N/A  "
        t_shr = f"{ts_['ic_sharpe']:+.3f}" if ts_["ic_sharpe"] is not None else " N/A  "
        print(f"  {t:<20}  train={t_ic} (IC-Sharpe={t_shr})  holdout={h_ic}")

    write_results_md(train_ics, holdout_ics, best_name, train_best, holdout_best)

    sys.stdout.flush()


if __name__ == "__main__":
    main()
