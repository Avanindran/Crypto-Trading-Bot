"""
research/h2_mechanism_test.py — Proper H2 BTC-diffusion mechanism test.

The H2 hypothesis: BTC is the information leader; secondary altcoins that have
NOT yet responded to a BTC move are in a temporary divergence state that closes
within 1–6h (expectation diffusion lag).

PROBLEM: H2a (CS_z(alt_r - btc_r)) mathematically collapses to CS_z(-alt_r)
because btc_r is a cross-sectional constant, removed by z-normalization.
H2a and H1 (plain reversal) are provably identical in CS z-score space.

PROPER TEST: The only empirically distinguishable difference between H1 and H2
is whether the IC of the laggard signal is conditioned on BTC having moved:
  - H2 predicts: IC increases when |btc_r_2h| is large (BTC actually moved)
  - H1 predicts: IC is stable regardless of BTC move magnitude (pure reversal)

Additionally test the non-z-scored diffusion gap as a signal:
  - Raw H2 signal: btc_r_2h - alt_r_2h  (raw absolute gap, NOT z-scored)
  - If ranking by raw H2 gives HIGHER IC than ranking by raw H1 (-alt_r_2h)
    → the BTC contribution adds information beyond the cross-sectional rank

Run:
  python -X utf8 research/H2_transitional_drift/tools/h2_mechanism_test.py

Outputs:
  research/05_h2_mechanism_test.md
  research/charts/05_h2_mechanism/ic_btc_conditioned.png
"""

import math
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, '..', '..')  # research/ root
sys.path.insert(0, _root)
os.makedirs(os.path.join(_root, "charts"), exist_ok=True)

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

# ── Configuration ──────────────────────────────────────────────────────────────

FWD_HORIZONS   = [2, 4]   # Test both 2h and 4h forward returns
BTC_SYM        = "BTCUSDT"

# BTC 2h return bucketing thresholds
BTC_FLAT_THRESH     = 0.005   # |btc_r_2h| < 0.5%  → BTC flat
BTC_MODERATE_THRESH = 0.015   # 0.5% ≤ |btc_r_2h| < 1.5% → moderate
# Anything ≥ 1.5% → BTC large move

OUTPUT_FILE  = os.path.join(_root, "H2_transitional_drift", "03_results", "02_mechanism_test.md")
CHART_FILE   = os.path.join(_root, "charts", "05_h2_mechanism", "ic_btc_conditioned.png")

MIN_BUCKET_N = 20  # Minimum per-timestamp count in bucket for t-stat to be meaningful


# ── Helpers ────────────────────────────────────────────────────────────────────

def ic_stats(period_ics: List[float]) -> dict:
    n = len(period_ics)
    if n < 3:
        return {"n": n, "mean_ic": None, "t_stat": None, "std_ic": None}
    mean_ic = sum(period_ics) / n
    std_ic  = math.sqrt(sum((v - mean_ic) ** 2 for v in period_ics) / n) or 1e-8
    return {
        "n":       n,
        "mean_ic": mean_ic,
        "t_stat":  mean_ic / (std_ic / math.sqrt(n)),
        "std_ic":  std_ic,
    }


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


# ── Signal computation at one timestamp ────────────────────────────────────────

def compute_signals_at_ts(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts:           int,
    btc_r_2h:     Optional[float],
) -> Tuple[Optional[Dict[str, float]], Optional[Dict[str, float]], Optional[Dict[str, float]]]:
    """Compute three signals for all valid alts at one timestamp.

    Returns:
        h1_neg_r2h_z  — CS_z(-alt_r_2h)              [H1: cross-sect. reversal]
        promoted_z    — 0.70*CS_z(-C1_raw) + 0.30*CS_z(-realized_vol_6h)
        raw_h2_diff   — btc_r_2h - alt_r_2h (raw, NOT z-scored) [H2: absolute gap]
    Each is a dict {pair: signal_value} or None if insufficient data.
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
        return None, None, None

    # H1: CS_z(-r_2h) — standard cross-sectional reversal
    h1_neg_r2h_z = cross_sectional_z({p: -v for p, v in r2h_raw.items()})

    # Promoted C1 signal: 0.70 × CS_z(-C1_raw) + 0.30 × CS_z(-realized_vol_6h)
    median_r2h = sorted(r2h_raw.values())[len(r2h_raw) // 2]
    c1_raw = {
        pair: (C1_WEIGHT_R30M * r1h_raw.get(pair, 0.0)
               + C1_WEIGHT_R2H   * r2h_raw.get(pair, 0.0)
               + C1_WEIGHT_R6H   * r6h_raw.get(pair, 0.0)
               + C1_WEIGHT_R24H  * r24h_raw.get(pair, 0.0)
               + C1_WEIGHT_CS_RS * (r2h_raw.get(pair, 0.0) - median_r2h))
        for pair in r6h_raw
    }
    neg_c1_z = cross_sectional_z({p: -v for p, v in c1_raw.items()})
    neg_vol_raw = {
        p: -realized_vol(all_prices[p], ts, 6)
        for p in r6h_raw
        if realized_vol(all_prices[p], ts, 6) is not None
    }
    neg_vol_z = cross_sectional_z(neg_vol_raw) if len(neg_vol_raw) >= 2 else {}
    promoted_z = {
        p: 0.70 * neg_c1_z.get(p, 0.0) + 0.30 * neg_vol_z.get(p, 0.0)
        for p in neg_c1_z
    }

    # H2: raw absolute diffusion gap (btc_r_2h - alt_r_2h), NOT z-scored
    # Only meaningful when BTC has moved (btc_r_2h not None)
    raw_h2_diff: Optional[Dict[str, float]] = None
    if btc_r_2h is not None:
        raw_h2_diff = {p: btc_r_2h - r2h_raw[p] for p in r2h_raw}

    return h1_neg_r2h_z, promoted_z, raw_h2_diff


# ── BTC-conditioned IC accumulation ────────────────────────────────────────────

def run_h2_test(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
) -> dict:
    """Accumulate per-timestamp ICs by BTC move bucket.

    Returns nested dict: {bucket: {signal: {fwd_h: [ic, ic, ...]}}}
    """
    print(f"  Computing ICs across {len(timestamps)} timestamps ...")

    buckets = ["btc_flat", "btc_moderate", "btc_large_up", "btc_large_dn", "all"]
    signals  = ["h1_neg_r2h", "promoted", "h2_raw_diff"]
    ics: Dict[str, Dict[str, Dict[int, List[float]]]] = {
        b: {s: {h: [] for h in FWD_HORIZONS} for s in signals}
        for b in buckets
    }

    btc_prices = all_prices.get(BTC_SYM, {})
    alts = [p for p in active_pairs if p != BTC_SYM]

    for ts in timestamps:
        btc_r2h = compute_return(btc_prices, ts, 2.0)

        # Classify BTC bucket
        if btc_r2h is None:
            continue
        abs_btc = abs(btc_r2h)
        if abs_btc < BTC_FLAT_THRESH:
            btc_bucket = "btc_flat"
        elif abs_btc < BTC_MODERATE_THRESH:
            btc_bucket = "btc_moderate"
        else:
            btc_bucket = "btc_large_up" if btc_r2h > 0 else "btc_large_dn"

        h1_z, prom_z, h2_raw = compute_signals_at_ts(all_prices, alts, ts, btc_r2h)
        if h1_z is None:
            continue

        for fwd_h in FWD_HORIZONS:
            fwd: Dict[str, float] = {}
            for pair in h1_z:
                f = compute_forward_return(all_prices[pair], ts, fwd_h)
                if f is not None:
                    fwd[pair] = f

            common_pairs = [p for p in h1_z if p in fwd]
            if len(common_pairs) < 5:
                continue

            # IC for each signal in both buckets (btc_bucket and "all")
            for bucket in [btc_bucket, "all"]:
                for sig_name, sig_dict in [
                    ("h1_neg_r2h", h1_z),
                    ("promoted",   prom_z),
                    ("h2_raw_diff", h2_raw),
                ]:
                    if sig_dict is None:
                        continue
                    vals = [(sig_dict[p], fwd[p]) for p in common_pairs if p in sig_dict]
                    if len(vals) < 5:
                        continue
                    ic = spearman_ic([v[0] for v in vals], [v[1] for v in vals])
                    if ic is not None:
                        ics[bucket][sig_name][fwd_h].append(ic)

    return ics


# ── Reporting ──────────────────────────────────────────────────────────────────

def write_report(ics: dict) -> None:
    def fmt(s: dict) -> str:
        if s["mean_ic"] is None:
            return "N/A"
        sign = "+" if s["mean_ic"] >= 0 else ""
        t = s["t_stat"]
        star = "*" if t is not None and abs(t) > 1.5 else ""
        return f"{sign}{s['mean_ic']:.4f}{star} (t={t:.1f}, n={s['n']})"

    buckets_in_order = ["btc_flat", "btc_moderate", "btc_large_up", "btc_large_dn", "all"]
    bucket_labels = {
        "btc_flat":     f"BTC flat (|btc_r_2h| < {BTC_FLAT_THRESH*100:.1f}%)",
        "btc_moderate": f"BTC moderate ({BTC_FLAT_THRESH*100:.1f}%–{BTC_MODERATE_THRESH*100:.1f}%)",
        "btc_large_up": f"BTC large UP (|btc_r_2h| >= {BTC_MODERATE_THRESH*100:.1f}%, positive)",
        "btc_large_dn": f"BTC large DOWN (|btc_r_2h| >= {BTC_MODERATE_THRESH*100:.1f}%, negative)",
        "all":          "Unconditional (all timestamps)",
    }

    lines = [
        "# H2 BTC-Diffusion Mechanism Test",
        "",
        f"**Run:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        "**Period:** Oct 2024 – Jan 2025 (trending period)",
        "",
        "## Research Question",
        "",
        "H2 hypothesis: BTC reprices new information first; alts that lagged BTC's move",
        "should catch up within 1–6h (expectation diffusion lag).",
        "",
        "**The H2a collapse:** CS_z(alt_r - btc_r) = CS_z(-alt_r) [mathematical identity].",
        "BTC return is a cross-sectional constant removed by z-normalization.",
        "H2a provides zero independent information beyond H1 (reversal) in CS z-score space.",
        "",
        "**Proper test:** If H2 is the mechanism, IC of the laggard signal should be",
        "**HIGHER** when BTC has moved significantly vs when BTC is flat.",
        "If H1 is the mechanism (generic reversal), IC should be stable regardless of BTC move.",
        "",
        "**Additionally:** Does the raw BTC gap (btc_r_2h - alt_r_2h, NOT z-scored)",
        "have HIGHER IC than plain H1 (-alt_r_2h)? This would confirm the BTC contribution adds info.",
        "",
        "## IC by BTC Regime — H1_neg_r2h Signal",
        "",
        "| BTC Regime | IC at 2h | IC at 4h |",
        "|------------|----------|----------|",
    ]
    for b in buckets_in_order:
        stats_2h = ic_stats(ics[b]["h1_neg_r2h"][2])
        stats_4h = ic_stats(ics[b]["h1_neg_r2h"][4])
        lines.append(f"| {bucket_labels[b]} | {fmt(stats_2h)} | {fmt(stats_4h)} |")

    lines += [
        "",
        "## IC by BTC Regime — Promoted Signal (0.70×H1 + 0.30×H5_neg_vol)",
        "",
        "| BTC Regime | IC at 2h | IC at 4h |",
        "|------------|----------|----------|",
    ]
    for b in buckets_in_order:
        stats_2h = ic_stats(ics[b]["promoted"][2])
        stats_4h = ic_stats(ics[b]["promoted"][4])
        lines.append(f"| {bucket_labels[b]} | {fmt(stats_2h)} | {fmt(stats_4h)} |")

    lines += [
        "",
        "## IC by BTC Regime — Raw H2 Diffusion Gap (btc_r_2h - alt_r_2h, NOT z-scored)",
        "",
        "| BTC Regime | IC at 2h | IC at 4h |",
        "|------------|----------|----------|",
    ]
    for b in buckets_in_order:
        stats_2h = ic_stats(ics[b]["h2_raw_diff"][2])
        stats_4h = ic_stats(ics[b]["h2_raw_diff"][4])
        lines.append(f"| {bucket_labels[b]} | {fmt(stats_2h)} | {fmt(stats_4h)} |")

    # Interpretation
    h1_flat = ic_stats(ics["btc_flat"]["h1_neg_r2h"][4])
    h1_large_up = ic_stats(ics["btc_large_up"]["h1_neg_r2h"][4])
    h1_all   = ic_stats(ics["all"]["h1_neg_r2h"][4])
    h1_diff  = (h1_large_up["mean_ic"] or 0.0) - (h1_flat["mean_ic"] or 0.0)

    h2_raw_all = ic_stats(ics["all"]["h2_raw_diff"][4])
    h1_raw_all = ic_stats(ics["all"]["h1_neg_r2h"][4])
    raw_lift   = (h2_raw_all["mean_ic"] or 0.0) - (h1_raw_all["mean_ic"] or 0.0)

    lines += [
        "",
        "## Interpretation",
        "",
        "### Gate: Does H2 add over H1?",
        "",
        "**BTC-conditioning test (IC uplift = IC_large_move - IC_flat at 4h):**",
        f"  H1_neg_r2h: IC_large_up = {h1_large_up['mean_ic']:.4f}, IC_flat = {h1_flat['mean_ic']:.4f}, uplift = {h1_diff:+.4f}",
        "",
    ]

    if h1_diff > 0.010:
        lines += [
            "**Result: H2 MECHANISM CONFIRMED** (uplift > 0.010)",
            "IC of the laggard signal is meaningfully higher when BTC has moved.",
            "The signal exploits BTC-diffusion lag, not just generic cross-sectional reversal.",
            "Implication: C2 regime filter should key on BTC move direction/magnitude.",
        ]
    elif h1_diff > 0.003:
        lines += [
            "**Result: H2 PARTIALLY SUPPORTED** (uplift 0.003–0.010)",
            "IC is modestly higher when BTC moves, consistent with H2 as a partial driver.",
            "Cannot rule out H1 as co-mechanism. Both likely contribute.",
        ]
    else:
        lines += [
            "**Result: H1 IS THE MECHANISM** (uplift ≤ 0.003)",
            "IC is not meaningfully higher when BTC moves.",
            "The signal works as generic cross-sectional reversal, independent of BTC.",
            "The H2 (BTC-diffusion) mechanism is not empirically confirmed in this universe.",
            "The promoted signal should be documented as a statistical regularity (H1),",
            "not as a BTC-leader-laggard diffusion signal.",
        ]

    lines += [
        "",
        "**Raw diffusion gap test (does keeping BTC's contribution improve IC?):**",
        f"  H2_raw IC at 4h = {h2_raw_all['mean_ic']:.4f}, H1_raw IC at 4h = {h1_raw_all['mean_ic']:.4f}, lift = {raw_lift:+.4f}",
        "",
    ]

    if raw_lift > 0.005:
        lines.append("Raw H2 gap has HIGHER IC than H1 reversal — BTC absolute return adds predictive info.")
    elif raw_lift > 0:
        lines.append("Raw H2 gap marginally better than H1 — effect is small and may not be robust.")
    else:
        lines.append("Raw H2 gap IC <= H1 IC — confirming the BTC contribution does not add information.")

    lines += [
        "",
        "## Connection to Existing Research",
        "",
        "**Why H2a collapsed:** In cross-sectional z-score space, CS_z(alt_r - btc_r) = CS_z(alt_r - constant) = CS_z(alt_r).",
        "BTC return is a cross-sectional constant. Z-normalization removes it. H2a = H1 in CS z-score space.",
        "This was documented in 08_limitations_and_rejections.md. This test confirms whether the",
        "BTC contribution adds information in NON-z-scored space.",
        "",
        "**Previous H2b test:** Lagged BTC return as a market-level predictor (same value for all alts).",
        "Result: Pearson r = -0.003. No diffusion lag at 1h aggregation.",
        "",
        "**Current test:** BTC-conditioned IC of the laggard signal (H1). This is the only",
        "test that can distinguish H2 from H1 empirically.",
        "",
        f"See `research/charts/05_h2_mechanism/ic_btc_conditioned.png` for visual IC profiles by BTC regime.",
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_FILE}")


def write_chart(ics: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  [SKIP] matplotlib not available — skipping chart")
        return

    buckets_plot = ["btc_flat", "btc_moderate", "btc_large_up", "btc_large_dn"]
    bucket_short = {
        "btc_flat":     "BTC flat\n(<0.5%)",
        "btc_moderate": "BTC mod\n(0.5-1.5%)",
        "btc_large_up": "BTC up\n(>1.5%)",
        "btc_large_dn": "BTC down\n(>1.5%)",
    }
    signals_plot = ["h1_neg_r2h", "promoted"]
    sig_labels   = {"h1_neg_r2h": "H1 reversal (CS_z(-r_2h))", "promoted": "Promoted (0.70×H1 + 0.30×H5_vol)"}
    colors       = {"h1_neg_r2h": "#2196F3", "promoted": "#FF5722"}
    x = np.arange(len(buckets_plot))
    width = 0.35

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax_idx, fwd_h in enumerate(FWD_HORIZONS):
        ax = axes[ax_idx]
        for sig_idx, sig_name in enumerate(signals_plot):
            means = []
            errs  = []
            for b in buckets_plot:
                s = ic_stats(ics[b][sig_name][fwd_h])
                means.append(s["mean_ic"] or 0.0)
                std = s["std_ic"] or 0.0
                n   = s["n"] or 1
                errs.append(std / math.sqrt(n))  # SE of mean IC
            offset = (sig_idx - 0.5) * width
            bars = ax.bar(x + offset, means, width, label=sig_labels[sig_name],
                          color=colors[sig_name], alpha=0.85,
                          yerr=errs, capsize=4, error_kw={"elinewidth": 1.5})
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_title(f"IC at {fwd_h}h forward return by BTC move bucket")
        ax.set_ylabel("Mean Spearman IC")
        ax.set_xticks(x)
        ax.set_xticklabels([bucket_short[b] for b in buckets_plot], fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "H2 Mechanism Test: Is IC conditioned on BTC having moved?\n"
        "H2 predicts: IC(BTC large) >> IC(BTC flat)",
        fontsize=11,
    )
    plt.tight_layout()
    plt.savefig(CHART_FILE, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Wrote chart: {CHART_FILE}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 70)
    print("research/h2_mechanism_test.py — H2 BTC-diffusion mechanism test")
    print("=" * 70)

    print("\nLoading klines data (Oct 2024 – Jan 2025) ...")
    months       = list(_month_range(TRENDING_START, TRENDING_END))
    active_pairs = fetch_roostoo_pairs()
    (all_prices, *_) = load_klines_all_parallel(active_pairs, months)

    active_pairs = [p for p in active_pairs if p in all_prices and len(all_prices[p]) > 100]
    print(f"Active pairs: {len(active_pairs)}")

    # Build 1h timestamps (union of all pairs)
    all_ts_union: set = set()
    for sym in active_pairs:
        all_ts_union.update(all_prices[sym].keys())
    timestamps_sorted = sorted(all_ts_union)

    # Down-sample to 1h intervals
    step_ms = 3_600_000
    timestamps_1h: List[int] = []
    prev = None
    for ts in timestamps_sorted:
        if prev is None or ts - prev >= step_ms:
            timestamps_1h.append(ts)
            prev = ts
    print(f"Timestamps (1h): {len(timestamps_1h)}")

    ics = run_h2_test(all_prices, active_pairs, timestamps_1h)

    # Summary
    for b in ["btc_flat", "btc_large_up", "all"]:
        s = ic_stats(ics[b]["h1_neg_r2h"][4])
        print(f"  H1 IC@4h | {b}: mean={s['mean_ic']:.4f}, t={s['t_stat']:.2f}, n={s['n']}")

    write_report(ics)
    write_chart(ics)

    print("\nDone.")


if __name__ == "__main__":
    main()
