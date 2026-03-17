"""
research/vector_tests.py — Doctrine Steps 3C, 4A, 4B, 5

Part A (Step 3C) — Bare signal vector backtest
  Fixed 4h hold, no modifiers, long-only equal-weight top-3.
  Sanity bars: Gross Sharpe > 0, MaxDD ≥ −40%, annual hit rate > 50%.

Part B (Step 4A) — C2 regime/hazard modifier screen
  LSI proxy (BTC vol z-score) gates new entries.
  Must reduce MaxDD ≥ 10% relative AND improve worst 30-day period ≥ 5pp.

Part C (Step 4B) — C3 maturity M_t modifier screen
  Proxy: pct_rank of r_6h in 48h rolling history.
  Gate criterion: IC in low-maturity bucket > unconditional IC.

Part D (Step 5) — Full signal vector: sequential improvement table
  Bare C1 → +C2 → +C2+C3

Run:
  python -X utf8 research/vector_tests.py

Outputs:
  research/06_vector_tests.md
  research/charts/06_vector_tests/equity_curves.png
"""

from __future__ import annotations

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
    spearman_ic,
    fetch_roostoo_pairs,
    _month_range,
    C1_WEIGHT_R30M,
    C1_WEIGHT_R2H,
    C1_WEIGHT_R6H,
    C1_WEIGHT_R24H,
    C1_WEIGHT_CS_RS,
    TRENDING_START,
    TRENDING_END,
)

os.makedirs(os.path.join(_here, "charts"), exist_ok=True)

# ── Configuration ─────────────────────────────────────────────────────────────

HOLD_HOURS     = 4      # fixed rebalance cadence
TOP_N          = 3      # long-only top-N (equal weight 33% each)
W_REV          = 0.70   # promoted signal: reversal weight
W_STAB         = 0.30   # promoted signal: stability weight
LSI_LOOKBACK   = 48     # BTC vol z-score window (hours)
LSI_C2_THRESH  = 1.50   # z-score above which C2 blocks entries
MT_C3_MAX      = 0.70   # maturity proxy above which C3 blocks entry
MT_LOOKBACK    = 48     # pct_rank lookback (hours)
PERIOD_DAYS    = 30     # subperiod for worst-period analysis
MS_PER_HOUR    = 3_600_000
MS_PER_DAY     = 86_400_000


# ── Helper functions ───────────────────────────────────────────────────────────

def realized_vol(prices: Dict[int, float], ts: int, hours: int = 6) -> Optional[float]:
    rets = []
    for lag in range(1, hours + 1):
        r = compute_return(prices, ts - lag * MS_PER_HOUR, 1.0)
        if r is not None:
            rets.append(r)
    if len(rets) < max(3, hours // 2):
        return None
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets)) or 1e-8


def _btc_vol_zscore(
    all_prices: Dict[str, Dict[int, float]],
    btc_key: str,
    ts: int,
    vol_history: List[float],
    lookback: int = LSI_LOOKBACK,
) -> Optional[float]:
    """BTC realized-vol z-score over rolling lookback window."""
    rv = realized_vol(all_prices[btc_key], ts, hours=6)
    if rv is None:
        return None
    vol_history.append(rv)
    if len(vol_history) < lookback:
        return None
    window = vol_history[-lookback:]
    mean_v = sum(window) / len(window)
    std_v  = math.sqrt(sum((x - mean_v) ** 2 for x in window) / len(window)) or 1e-8
    return (rv - mean_v) / std_v


def _maturity_proxy(
    all_prices: Dict[str, Dict[int, float]],
    pair: str,
    ts: int,
    r6h_history: List[float],
    lookback: int = MT_LOOKBACK,
) -> Optional[float]:
    """Pct-rank of current r_6h in rolling lookback window (0=fresh, 1=extended)."""
    r6h = compute_return(all_prices[pair], ts, 6.0)
    if r6h is None:
        return None
    r6h_history.append(r6h)
    if len(r6h_history) < max(10, lookback // 4):
        return None
    window = r6h_history[-lookback:]
    rank = sum(1 for v in window if v <= r6h) / len(window)
    return rank


def _compute_signal(
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts: int,
    w_rev: float = W_REV,
    w_stab: float = W_STAB,
) -> Optional[Dict[str, float]]:
    """Compute promoted signal at one timestamp. Returns {pair: score} or None."""
    n_min = max(5, len(active_pairs) // 4)

    r1h_raw: Dict[str, float] = {}
    r2h_raw: Dict[str, float] = {}
    r6h_raw: Dict[str, float] = {}
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
        return None

    median_r2h = sorted(r2h_raw.values())[len(r2h_raw) // 2]
    c1_raw = {
        pair: (C1_WEIGHT_R30M  * r1h_raw.get(pair, 0.0)
             + C1_WEIGHT_R2H   * r2h_raw.get(pair, 0.0)
             + C1_WEIGHT_R6H   * r6h_raw.get(pair, 0.0)
             + C1_WEIGHT_R24H  * r24h_raw.get(pair, 0.0)
             + C1_WEIGHT_CS_RS * (r2h_raw.get(pair, 0.0) - median_r2h))
        for pair in r6h_raw
    }

    neg_c1_z = cross_sectional_z({p: -v for p, v in c1_raw.items()})

    neg_vol_raw: Dict[str, float] = {}
    for pair in r6h_raw:
        rv = realized_vol(all_prices[pair], ts, 6)
        if rv is not None:
            neg_vol_raw[pair] = -rv
    neg_vol_z = cross_sectional_z(neg_vol_raw) if len(neg_vol_raw) >= 2 else {}

    result: Dict[str, float] = {}
    for pair in neg_c1_z:
        rev  = neg_c1_z.get(pair, 0.0)
        stab = neg_vol_z.get(pair, 0.0)
        result[pair] = w_rev * rev + w_stab * stab
    return result if len(result) >= n_min else None


# ── NAV backtest engine ────────────────────────────────────────────────────────

def run_backtest(
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps: List[int],        # 1h grid
    use_c2: bool = False,
    use_c3: bool = False,
    label: str = "bare",
) -> Tuple[List[Tuple[int, float]], dict]:
    """
    Simulate a long-only equal-weight portfolio rebalanced every HOLD_HOURS.

    Returns:
        nav_series: list of (timestamp_ms, nav_value)
        stats: dict with Sharpe, MaxDD, hit_rate, n_periods, mean_return, ic_mean
    """
    btc_key = next((p for p in active_pairs if p.startswith("BTC")), None)

    # State
    nav        = 1.0
    nav_series: List[Tuple[int, float]] = [(timestamps[0], 1.0)]
    period_rets: List[float] = []

    # Running histories for C2 / C3
    btc_vol_hist:    List[float] = []
    maturity_hists:  Dict[str, List[float]] = {p: [] for p in active_pairs}

    # IC accumulation (bare signal vs 4h forward return)
    period_ics: List[float] = []

    # Only rebalance every HOLD_HOURS steps (1h resolution)
    step = 0
    for i, ts in enumerate(timestamps):
        if i % HOLD_HOURS != 0:
            continue

        # ── Compute signal ────────────────────────────────────────────────────
        sig = _compute_signal(all_prices, active_pairs, ts)
        if sig is None:
            step += 1
            continue

        # ── Accumulate IC (always, regardless of modifiers) ───────────────────
        fwd_for_ic: Dict[str, float] = {}
        for pair in sig:
            f = compute_forward_return(all_prices[pair], ts, HOLD_HOURS)
            if f is not None:
                fwd_for_ic[pair] = f
        if len(fwd_for_ic) >= 5:
            ic = spearman_ic(
                [sig[p] for p in fwd_for_ic],
                [fwd_for_ic[p] for p in fwd_for_ic],
            )
            if ic is not None:
                period_ics.append(ic)

        # ── C2: regime hazard gate ────────────────────────────────────────────
        hazard = False
        if use_c2 and btc_key is not None:
            z = _btc_vol_zscore(all_prices, btc_key, ts, btc_vol_hist)
            if z is not None and z > LSI_C2_THRESH:
                hazard = True

        # ── C3: maturity filter — remove extended assets ──────────────────────
        if use_c3 and not hazard:
            filtered_sig: Dict[str, float] = {}
            for pair, score in sig.items():
                mat = _maturity_proxy(
                    all_prices, pair, ts, maturity_hists[pair]
                )
                if mat is None or mat <= MT_C3_MAX:
                    filtered_sig[pair] = score
            sig = filtered_sig if len(filtered_sig) >= 2 else sig
        elif not use_c3:
            # Still update maturity histories for C3 when not used
            for pair in sig:
                _maturity_proxy(all_prices, pair, ts, maturity_hists[pair])

        # ── Select top-N ──────────────────────────────────────────────────────
        if hazard:
            period_rets.append(0.0)
            nav_series.append((ts + HOLD_HOURS * MS_PER_HOUR, nav))
            step += 1
            continue

        ranked = sorted(sig.items(), key=lambda x: x[1], reverse=True)
        selected = [p for p, _ in ranked[:TOP_N]]
        if not selected:
            period_rets.append(0.0)
            nav_series.append((ts + HOLD_HOURS * MS_PER_HOUR, nav))
            step += 1
            continue

        # ── Compute portfolio return ──────────────────────────────────────────
        rets = []
        for pair in selected:
            r = compute_forward_return(all_prices[pair], ts, HOLD_HOURS)
            if r is not None:
                rets.append(r)

        if rets:
            port_ret = sum(rets) / len(rets)
            nav *= (1 + port_ret)
            period_rets.append(port_ret)
        else:
            period_rets.append(0.0)

        nav_series.append((ts + HOLD_HOURS * MS_PER_HOUR, nav))
        step += 1

    # ── Compute statistics ────────────────────────────────────────────────────
    stats = _compute_backtest_stats(period_rets, nav_series, period_ics, label)
    return nav_series, stats


def _compute_backtest_stats(
    period_rets: List[float],
    nav_series: List[Tuple[int, float]],
    period_ics: List[float],
    label: str,
) -> dict:
    n = len(period_rets)
    if n < 2:
        return {"label": label, "n_periods": n}

    mean_ret  = sum(period_rets) / n
    std_ret   = math.sqrt(sum((r - mean_ret) ** 2 for r in period_rets) / n) or 1e-8
    sharpe    = mean_ret / std_ret * math.sqrt(365 * 24 / HOLD_HOURS)

    # Max drawdown
    peak = 1.0
    max_dd = 0.0
    running = 1.0
    for r in period_rets:
        running *= (1 + r)
        if running > peak:
            peak = running
        dd = (running - peak) / peak
        if dd < max_dd:
            max_dd = dd

    # Hit rate (fraction of periods with positive return)
    hit_rate = sum(1 for r in period_rets if r > 0) / n

    # Worst 30-day window NAV drop
    period_steps = PERIOD_DAYS * 24 // HOLD_HOURS
    worst_period_dd = 0.0
    for i in range(len(nav_series) - period_steps):
        start_nav = nav_series[i][1]
        end_nav   = nav_series[i + period_steps][1]
        pdd = (end_nav - start_nav) / start_nav
        if pdd < worst_period_dd:
            worst_period_dd = pdd

    # IC stats
    ic_mean = sum(period_ics) / len(period_ics) if period_ics else 0.0

    final_nav = nav_series[-1][1] if nav_series else 1.0
    total_ret = final_nav - 1.0

    return {
        "label":           label,
        "n_periods":       n,
        "mean_ret_4h":     mean_ret,
        "sharpe_ann":      sharpe,
        "max_dd":          max_dd,
        "hit_rate":        hit_rate,
        "worst_period_dd": worst_period_dd,
        "total_return":    total_ret,
        "ic_mean":         ic_mean,
        "final_nav":       final_nav,
    }


# ── Part C: IC by maturity bucket (Step 4B) ────────────────────────────────────

def run_maturity_ic_test(
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps: List[int],
) -> dict:
    """
    Compute IC of promoted signal conditioned on maturity proxy bucket.

    Buckets:
      fresh:  pct_rank < 0.30  (signal not yet extended)
      mid:    0.30 ≤ pct_rank < 0.70
      stale:  pct_rank ≥ 0.70  (signal already extended)

    C3 criterion: IC(fresh) > IC(unconditional).
    """
    maturity_hists: Dict[str, List[float]] = {p: [] for p in active_pairs}

    fresh_ics: List[float] = []
    mid_ics:   List[float] = []
    stale_ics: List[float] = []
    all_ics:   List[float] = []

    for i, ts in enumerate(timestamps):
        if i % HOLD_HOURS != 0:
            continue

        sig = _compute_signal(all_prices, active_pairs, ts)
        if sig is None:
            # Still update maturity histories
            for pair in active_pairs:
                _maturity_proxy(all_prices, pair, ts, maturity_hists[pair])
            continue

        # Compute forward returns
        fwd: Dict[str, float] = {}
        for pair in sig:
            f = compute_forward_return(all_prices[pair], ts, HOLD_HOURS)
            if f is not None:
                fwd[pair] = f

        # Update maturity histories and classify
        fresh_pairs: List[str] = []
        mid_pairs:   List[str] = []
        stale_pairs: List[str] = []

        for pair in sig:
            r6h = compute_return(all_prices[pair], ts, 6.0)
            if r6h is not None:
                maturity_hists[pair].append(r6h)
            if len(maturity_hists[pair]) < 10:
                continue
            window = maturity_hists[pair][-MT_LOOKBACK:]
            r6h_now = maturity_hists[pair][-1]
            rank = sum(1 for v in window if v <= r6h_now) / len(window)

            if rank < 0.30:
                fresh_pairs.append(pair)
            elif rank < 0.70:
                mid_pairs.append(pair)
            else:
                stale_pairs.append(pair)

        def _bucket_ic(pairs: List[str]) -> Optional[float]:
            common = {p: (sig[p], fwd[p]) for p in pairs if p in sig and p in fwd}
            if len(common) < 4:
                return None
            return spearman_ic(
                [v[0] for v in common.values()],
                [v[1] for v in common.values()],
            )

        ic_f = _bucket_ic(fresh_pairs)
        ic_m = _bucket_ic(mid_pairs)
        ic_s = _bucket_ic(stale_pairs)

        common_all = {p: (sig[p], fwd[p]) for p in sig if p in fwd}
        if len(common_all) >= 5:
            ic_a = spearman_ic(
                [v[0] for v in common_all.values()],
                [v[1] for v in common_all.values()],
            )
            if ic_a is not None:
                all_ics.append(ic_a)

        if ic_f is not None:
            fresh_ics.append(ic_f)
        if ic_m is not None:
            mid_ics.append(ic_m)
        if ic_s is not None:
            stale_ics.append(ic_s)

    def _ic_stat(ics: List[float]) -> dict:
        n = len(ics)
        if n < 3:
            return {"n": n, "mean": None, "t": None}
        mean = sum(ics) / n
        std  = math.sqrt(sum((v - mean) ** 2 for v in ics) / n) or 1e-8
        return {"n": n, "mean": mean, "t": mean / (std / math.sqrt(n))}

    return {
        "fresh":         _ic_stat(fresh_ics),
        "mid":           _ic_stat(mid_ics),
        "stale":         _ic_stat(stale_ics),
        "unconditional": _ic_stat(all_ics),
    }


# ── Report writer ──────────────────────────────────────────────────────────────

def _fmt(v: Optional[float], pct: bool = False, dec: int = 4) -> str:
    if v is None:
        return "N/A"
    if pct:
        return f"{v * 100:.2f}%"
    return f"{v:.{dec}f}"


def _pass_fail(cond: bool) -> str:
    return "PASS" if cond else "FAIL"


def write_report(
    stats_bare:   dict,
    stats_c2:     dict,
    stats_c2c3:   dict,
    mat_result:   dict,
    nav_bare:     List[Tuple[int, float]],
    nav_c2:       List[Tuple[int, float]],
    nav_c2c3:     List[Tuple[int, float]],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    b = stats_bare
    c2 = stats_c2
    c3 = stats_c2c3
    mt = mat_result

    # ── Step 3C sanity gates ──────────────────────────────────────────────────
    sharpe_pass  = (b.get("sharpe_ann", -999) or 0) > 0
    dd_pass      = (b.get("max_dd", -999)     or 0) >= -0.40
    hit_pass     = (b.get("hit_rate", 0)      or 0) > 0.50

    # ── Step 4A gates ─────────────────────────────────────────────────────────
    bare_dd   = b.get("max_dd",          0) or 0
    c2_dd     = c2.get("max_dd",         0) or 0
    bare_wp   = b.get("worst_period_dd", 0) or 0
    c2_wp     = c2.get("worst_period_dd",0) or 0

    dd_improv = (c2_dd - bare_dd) / abs(bare_dd) if bare_dd != 0 else 0  # positive = improvement (c2_dd is less negative)
    wp_improv = c2_wp - bare_wp                                           # positive = improvement

    c2_dd_pass = dd_improv >= 0.10
    c2_wp_pass = wp_improv >= 0.05
    c2_pass    = c2_dd_pass and c2_wp_pass

    # ── Step 4B gate ──────────────────────────────────────────────────────────
    ic_fresh = mt["fresh"]["mean"]
    ic_uncond = mt["unconditional"]["mean"]
    c3_pass = (ic_fresh or 0) > (ic_uncond or 0)

    # ── Final verdict ─────────────────────────────────────────────────────────
    signal_passes  = sharpe_pass and dd_pass and hit_pass
    full_signal_ok = signal_passes and c2_pass and c3_pass

    lines: List[str] = []
    lines.append(f"# Vector Tests — Steps 3C, 4A, 4B, 5\n")
    lines.append(f"**Run:** {now}  ")
    lines.append(f"**Period:** Oct 2024 – Jan 2025 (trending period)  ")
    lines.append(f"**Hold horizon:** {HOLD_HOURS}h | Top-N: {TOP_N} | Equal weight\n")

    # ── Part A ────────────────────────────────────────────────────────────────
    lines.append("## Part A — Step 3C: Bare Signal Vector\n")
    lines.append("Fixed-horizon hold, no C2/C3 modifiers.\n")
    lines.append(f"| Metric | Value | Sanity Bar | Result |")
    lines.append(f"|--------|-------|------------|--------|")
    lines.append(f"| Gross Sharpe (ann) | {_fmt(b.get('sharpe_ann'), dec=3)} | > 0 | {_pass_fail(sharpe_pass)} |")
    lines.append(f"| Max Drawdown | {_fmt(b.get('max_dd'), pct=True)} | ≥ −40% | {_pass_fail(dd_pass)} |")
    lines.append(f"| Period Hit Rate | {_fmt(b.get('hit_rate'), pct=True)} | > 50% | {_pass_fail(hit_pass)} |")
    lines.append(f"| Total Return (4m) | {_fmt(b.get('total_return'), pct=True)} | — | — |")
    lines.append(f"| Mean IC@4h | {_fmt(b.get('ic_mean'))} | — | — |")
    lines.append(f"| N periods | {b.get('n_periods', 'N/A')} | — | — |\n")
    lines.append(f"**Step 3C verdict: {'PASS — proceed to modifier screens' if signal_passes else 'FAIL — signal does not clear sanity bars'}**\n")

    # ── Part B ────────────────────────────────────────────────────────────────
    lines.append("## Part B — Step 4A: C2 Regime Modifier Screen\n")
    lines.append(f"C2 gate: BTC realized-vol z-score (48h) > {LSI_C2_THRESH} → skip all new entries (hold cash).\n")
    lines.append(f"| Metric | Bare C1 | + C2 gate | Improvement | Bar | Result |")
    lines.append(f"|--------|---------|-----------|-------------|-----|--------|")
    lines.append(f"| Max Drawdown | {_fmt(bare_dd, pct=True)} | {_fmt(c2_dd, pct=True)} | {_fmt(dd_improv, pct=True)} | ≥ 10% | {_pass_fail(c2_dd_pass)} |")
    lines.append(f"| Worst 30d DD | {_fmt(bare_wp, pct=True)} | {_fmt(c2_wp, pct=True)} | {_fmt(wp_improv, pct=True)} | ≥ 5pp | {_pass_fail(c2_wp_pass)} |")
    lines.append(f"| Sharpe (ann) | {_fmt(b.get('sharpe_ann'), dec=3)} | {_fmt(c2.get('sharpe_ann'), dec=3)} | — | — | — |")
    lines.append(f"| Total Return | {_fmt(b.get('total_return'), pct=True)} | {_fmt(c2.get('total_return'), pct=True)} | — | — | — |\n")
    lines.append(f"**Step 4A verdict: {'APPROVED — C2 clears both improvement gates' if c2_pass else 'REJECTED — C2 does not meet improvement thresholds'}**\n")

    # ── Part C ────────────────────────────────────────────────────────────────
    lines.append("## Part C — Step 4B: C3 Maturity Modifier Screen\n")
    lines.append(f"Maturity proxy: pct_rank of r_6h in {MT_LOOKBACK}h rolling history.  ")
    lines.append(f"Gate: IC(fresh, pct_rank < 30%) > IC(unconditional).\n")
    lines.append(f"| Maturity Bucket | Mean IC | t-stat | N |")
    lines.append(f"|-----------------|---------|--------|---|")
    for bucket in ("fresh", "mid", "stale", "unconditional"):
        s = mt[bucket]
        lines.append(
            f"| {bucket.capitalize()} | "
            f"{_fmt(s['mean'])} | "
            f"{_fmt(s.get('t'), dec=2)} | "
            f"{s['n']} |"
        )
    uplift = (ic_fresh or 0) - (ic_uncond or 0)
    lines.append(f"\nIC uplift (fresh vs unconditional): {_fmt(uplift)} ({_fmt(uplift, pct=True)})")
    lines.append(f"\n**Step 4B verdict: {'APPROVED — fresh signals outperform; C3 adds value' if c3_pass else 'REJECTED — fresh signals do not outperform unconditional IC'}**\n")

    # ── Part D ────────────────────────────────────────────────────────────────
    lines.append("## Part D — Step 5: Full Signal Vector (Sequential Improvement)\n")
    lines.append(f"| Configuration | Sharpe | MaxDD | Hit Rate | Total Return | IC@4h |")
    lines.append(f"|---------------|--------|-------|----------|--------------|-------|")
    for s in (b, c2, c3):
        lines.append(
            f"| {s['label']} | "
            f"{_fmt(s.get('sharpe_ann'), dec=3)} | "
            f"{_fmt(s.get('max_dd'), pct=True)} | "
            f"{_fmt(s.get('hit_rate'), pct=True)} | "
            f"{_fmt(s.get('total_return'), pct=True)} | "
            f"{_fmt(s.get('ic_mean'))} |"
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    lines.append(f"\n## Summary\n")
    lines.append(f"| Step | Test | Result |")
    lines.append(f"|------|------|--------|")
    lines.append(f"| 3C | Bare signal sanity bars | {_pass_fail(signal_passes)} |")
    lines.append(f"| 4A | C2 regime modifier approved | {_pass_fail(c2_pass)} |")
    lines.append(f"| 4B | C3 maturity modifier approved | {_pass_fail(c3_pass)} |")
    lines.append(f"| 5  | Full signal vector produces best Sharpe | {_pass_fail((c3.get('sharpe_ann') or 0) >= (b.get('sharpe_ann') or 0))} |")
    lines.append(f"\n**Overall: {'ALL STEPS PASSED — promoted signal + C2 + C3 form a coherent strategy' if full_signal_ok else 'ONE OR MORE STEPS FAILED — review individual sections above'}**\n")
    lines.append(f"*Equity curves: see `research/charts/06_vector_tests/equity_curves.png`*\n")

    return "\n".join(lines)


# ── Chart ──────────────────────────────────────────────────────────────────────

def write_chart(
    nav_bare:  List[Tuple[int, float]],
    nav_c2:    List[Tuple[int, float]],
    nav_c2c3:  List[Tuple[int, float]],
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime, timezone

        def to_dt(ms: int) -> datetime:
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

        fig, ax = plt.subplots(figsize=(12, 6))

        for nav_series, color, lw, label in [
            (nav_bare,  "#1f77b4", 1.5, "Bare C1 (no modifiers)"),
            (nav_c2,    "#ff7f0e", 1.5, "+ C2 regime gate"),
            (nav_c2c3,  "#2ca02c", 2.0, "+ C2 + C3 maturity filter"),
        ]:
            if nav_series:
                xs = [to_dt(t) for t, _ in nav_series]
                ys = [v for _, v in nav_series]
                ax.plot(xs, ys, color=color, linewidth=lw, label=label)

        ax.axhline(1.0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        fig.autofmt_xdate()
        ax.set_title("Equity Curves: Bare C1 vs +C2 vs +C2+C3\nOct 2024 – Jan 2025, 4h hold, Top-3 equal-weight")
        ax.set_ylabel("NAV (start = 1.0)")
        ax.set_xlabel("Date")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)

        out = os.path.join(_here, "charts", "06_vector_tests", "equity_curves.png")
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Wrote chart: {out}")
    except ImportError:
        print("  [SKIP] matplotlib not available — skipping equity curve chart")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("research/vector_tests.py — Steps 3C, 4A, 4B, 5")
    print("=" * 70)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("\nLoading klines data (Oct 2024 – Jan 2025) ...")
    months = _month_range(TRENDING_START, TRENDING_END)
    all_syms = fetch_roostoo_pairs()
    (all_prices, _bvol, _qvol, _ntrades, _tbvol, _open, _high, _low) = \
        load_klines_all_parallel(all_syms, months)

    active_pairs = [p for p in all_syms if p in all_prices and len(all_prices[p]) > 100]
    print(f"Active pairs: {len(active_pairs)}")

    # Build 1h timestamp grid from active pairs only
    all_ts: set = set()
    for p in active_pairs:
        all_ts.update(all_prices[p].keys())
    timestamps = sorted(all_ts)
    print(f"Timestamps (1h): {len(timestamps)}")

    # ── Part A: Bare signal ───────────────────────────────────────────────────
    print("\nPart A — bare signal vector ...")
    nav_bare, stats_bare = run_backtest(
        all_prices, active_pairs, timestamps,
        use_c2=False, use_c3=False, label="Bare C1"
    )
    print(f"  Sharpe={stats_bare.get('sharpe_ann', 0):.3f}  "
          f"MaxDD={stats_bare.get('max_dd', 0):.2%}  "
          f"HitRate={stats_bare.get('hit_rate', 0):.2%}")

    # ── Part B: + C2 ──────────────────────────────────────────────────────────
    print("\nPart B — + C2 regime gate ...")
    nav_c2, stats_c2 = run_backtest(
        all_prices, active_pairs, timestamps,
        use_c2=True, use_c3=False, label="+ C2 regime gate"
    )
    print(f"  Sharpe={stats_c2.get('sharpe_ann', 0):.3f}  "
          f"MaxDD={stats_c2.get('max_dd', 0):.2%}  "
          f"HitRate={stats_c2.get('hit_rate', 0):.2%}")

    # ── Part C: C3 IC by maturity ─────────────────────────────────────────────
    print("\nPart C — C3 maturity IC test ...")
    mat_result = run_maturity_ic_test(all_prices, active_pairs, timestamps)
    ic_f = mat_result["fresh"]["mean"]
    ic_u = mat_result["unconditional"]["mean"]
    ic_f_str = f"{ic_f:.4f}" if ic_f is not None else "N/A"
    ic_u_str = f"{ic_u:.4f}" if ic_u is not None else "N/A"
    t_fresh  = mat_result['fresh'].get('t') or 0
    print(f"  IC fresh={ic_f_str} (t={t_fresh:.2f})  IC uncond={ic_u_str}")

    # ── + C2+C3 backtest ──────────────────────────────────────────────────────
    print("\nPart D — + C2 + C3 combined ...")
    nav_c2c3, stats_c2c3 = run_backtest(
        all_prices, active_pairs, timestamps,
        use_c2=True, use_c3=True, label="+ C2 + C3"
    )
    print(f"  Sharpe={stats_c2c3.get('sharpe_ann', 0):.3f}  "
          f"MaxDD={stats_c2c3.get('max_dd', 0):.2%}  "
          f"HitRate={stats_c2c3.get('hit_rate', 0):.2%}")

    # ── Write report ──────────────────────────────────────────────────────────
    report = write_report(
        stats_bare, stats_c2, stats_c2c3,
        mat_result,
        nav_bare, nav_c2, nav_c2c3,
    )
    out_md = os.path.join(_here, "H1_reversal", "03_results", "05_vector_tests.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Wrote {out_md}")

    # ── Write chart ───────────────────────────────────────────────────────────
    write_chart(nav_bare, nav_c2, nav_c2c3)

    print("\nDone.")


if __name__ == "__main__":
    main()
