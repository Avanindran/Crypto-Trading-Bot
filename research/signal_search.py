"""
research/signal_search.py — Multi-hypothesis, multi-horizon IC validation.

Tests H1 (short-term reversal), H2 (BTC leader-laggard), H5 (vol-adjusted
momentum), and H6 (candle persistence) signal families declared in:
  01_mechanism_universe.md   — mechanism reasoning
  02_proxy_universe.md       — pre-committed proxy inventory (FROZEN)

Each proxy is tested at 6 forward horizons: 1h, 2h, 4h, 6h, 12h, 24h.
The IC decay profile (IC vs horizon) reveals the optimal holding period for
any signal that passes the gate.

Decision gate (from 02_proxy_universe.md):
  IC > 0  AND  t > 1.0  at ANY of the 6 forward horizons  →  PASS
  IC > 0.03  AND  t > 1.5  →  promotion-quality

Run:
  python research/signal_search.py

Outputs:
  research/03_validation/H1_reversal.md
  research/03_validation/H2_btc_laggard.md
  research/03_validation/H5_voladj_momentum.md
  research/03_validation/H6_streak_persistence.md
  research/charts/04_gp_search/ic_signal_search.png
"""

import math
import os
import sys
from typing import Dict, List, Optional, Tuple

# ── Import shared utilities from ic_validation_extended ────────────────────────
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
    TRENDING_START,
    TRENDING_END,
    C1_WEIGHT_R30M,
    C1_WEIGHT_R2H,
    C1_WEIGHT_R6H,
    C1_WEIGHT_R24H,
    C1_WEIGHT_CS_RS,
)

# ── Configuration ──────────────────────────────────────────────────────────────

FWD_HORIZONS    = [1, 2, 4, 6, 12, 24]   # forward return windows (hours)
STREAK_WINDOW   = 6                       # bars for H6 candle persistence
H6_TS_LOOKBACK  = 48                      # bars for H6 TS z-score baseline
VOL_MIN_BARS    = 3                       # minimum bars to compute realized vol

IC_GATE_MIN     = 0.0                     # minimum IC to pass gate
TSTAT_GATE_MIN  = 1.0                     # minimum |t| to pass gate
IC_PROMOTE_MIN  = 0.03                    # IC for promotion-quality
TSTAT_PROMOTE   = 1.5                     # t for promotion-quality

VALIDATION_DIR = os.path.join(_here, "03_validation")
CHARTS_DIR     = os.path.join(_here, "charts", "04_gp_search")
os.makedirs(VALIDATION_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR,     exist_ok=True)


# ── Volatility Helpers ─────────────────────────────────────────────────────────

def realized_vol(prices: Dict[int, float], ts: int, hours: int = 6) -> Optional[float]:
    """Std of `hours` 1h returns from bars at ts-1h through ts-hours.

    Excludes the current bar (no look-ahead bias). Returns None if
    insufficient history.
    """
    rets = []
    for lag in range(1, hours + 1):
        r = compute_return(prices, ts - lag * 3_600_000, 1.0)
        if r is not None:
            rets.append(r)
    if len(rets) < max(VOL_MIN_BARS, hours // 2):
        return None
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets)) or 1e-8


def downside_vol(prices: Dict[int, float], ts: int, hours: int = 6) -> float:
    """Downside deviation (negative returns only) over last `hours` bars.

    Returns 1e-6 if no negative returns observed (pure up-trend).
    """
    neg_rets = []
    for lag in range(1, hours + 1):
        r = compute_return(prices, ts - lag * 3_600_000, 1.0)
        if r is not None and r < 0:
            neg_rets.append(r)
    if len(neg_rets) < 2:
        return 1e-6
    return math.sqrt(sum(r ** 2 for r in neg_rets) / len(neg_rets)) or 1e-6


# ── Statistical Helpers ────────────────────────────────────────────────────────

def pearson_r(xs: List[float], ys: List[float]) -> Optional[float]:
    """Pearson correlation between xs and ys."""
    n = len(xs)
    if n < 5:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / n
    sx = math.sqrt(sum((v - mx) ** 2 for v in xs) / n)
    sy = math.sqrt(sum((v - my) ** 2 for v in ys) / n)
    if sx < 1e-9 or sy < 1e-9:
        return None
    return cov / (sx * sy)


def t_stat(ic: float, n: int) -> float:
    """t-statistic for IC: ic * sqrt(n-2) / sqrt(1 - ic^2)."""
    if n <= 2 or abs(ic) >= 1.0:
        return 0.0
    return ic * math.sqrt(n - 2) / math.sqrt(1 - ic ** 2 + 1e-12)


def ic_stats(period_ics: List[float]) -> dict:
    """Summary statistics from a list of per-period ICs.

    Returns dict with keys: n, mean_ic, t_stat, hit_rate.
    Uses t = mean_ic / (std_ic / sqrt(n)) — IC information ratio.
    """
    n = len(period_ics)
    if n < 3:
        return {"n": n, "mean_ic": None, "t_stat": None, "hit_rate": None}
    mean_ic = sum(period_ics) / n
    std_ic = math.sqrt(sum((v - mean_ic) ** 2 for v in period_ics) / n) or 1e-8
    hit_rate = sum(1 for v in period_ics if v > 0) / n
    t = mean_ic / (std_ic / math.sqrt(n))
    return {"n": n, "mean_ic": mean_ic, "t_stat": t, "hit_rate": hit_rate}


# ── Cross-sectional signal names ───────────────────────────────────────────────

CS_SIGNALS = [
    # H1: short-term reversal
    "H1_neg_r1h", "H1_neg_r2h", "H1_neg_r6h", "H1_neg_r24h", "H1_neg_c1",
    # H2a: BTC catch-up
    "H2a_neg_rel_btc_r1h", "H2a_neg_rel_btc_r2h", "H2a_neg_rel_btc_r6h",
    # H5: vol-adjusted momentum
    "H5_sharpe_6h", "H5_sharpe_24h", "H5_sortino_6h", "H5_neg_vol",
    # H6: candle persistence
    "H6_up_pct_6h", "H6_streak_ts", "H6_body_mean_6h",
]

H2B_SIGNALS = ["H2b_btc_lag1h", "H2b_btc_lag2h"]


# ── Main Analysis ──────────────────────────────────────────────────────────────

def run_signal_search(
    all_prices: Dict[str, Dict[int, float]],
    all_open:   Dict[str, Dict[int, float]],
    all_high:   Dict[str, Dict[int, float]],
    all_low:    Dict[str, Dict[int, float]],
) -> Tuple[
    Dict[str, Dict[int, List[float]]],          # cs_period_ics
    Dict[str, Dict[int, List[Tuple[float, float]]]],  # h2b_pairs
]:
    """
    Compute per-timestamp Spearman IC for H1/H2a/H5/H6 signals at all horizons.

    For H2b (lagged BTC predictor), accumulate (btc_lag_ret, mean_fwd_ret)
    pairs for Pearson correlation at analysis time.

    Returns:
        cs_period_ics:  {signal: {horizon_h: [ic_at_ts, ...]}}
        h2b_pairs:      {signal: {horizon_h: [(btc_lag_ret, mean_fwd_ret), ...]}}
    """
    active_pairs = [sym for sym, p in all_prices.items() if len(p) > 100]
    if not active_pairs:
        return {}, {}

    # Use UNION of all timestamps (not intersection) so that pairs listed partway
    # through the test period contribute their full available history.
    # Per-pair data access via compute_return() already handles missing timestamps
    # gracefully (returns None), so the inner loop skips missing pairs per ts.
    all_ts_union: set = set()
    for sym in active_pairs:
        all_ts_union.update(all_prices[sym].keys())
    common_ts  = sorted(all_ts_union)
    btc_prices = all_prices.get("BTCUSDT", {})
    n_min      = max(5, len(active_pairs) // 4)

    print(f"  Active pairs: {len(active_pairs)}, common timestamps: {len(common_ts)}")

    cs_period_ics: Dict[str, Dict[int, List[float]]] = {
        s: {h: [] for h in FWD_HORIZONS} for s in CS_SIGNALS
    }
    h2b_pairs: Dict[str, Dict[int, List[Tuple[float, float]]]] = {
        s: {h: [] for h in FWD_HORIZONS} for s in H2B_SIGNALS
    }

    # H6 TS z-score history per pair (up_pct_6h vs own baseline)
    h6_up_pct_hist: Dict[str, List[float]] = {p: [] for p in active_pairs}

    for idx, ts in enumerate(common_ts):
        if idx % 500 == 0:
            print(f"  [{idx}/{len(common_ts)}] processing...", flush=True)

        # ── Base returns for all pairs ──────────────────────────────────────────
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
            continue

        # ── Forward returns at all horizons ────────────────────────────────────
        fwd_raw: Dict[int, Dict[str, float]] = {h: {} for h in FWD_HORIZONS}
        for pair in r6h_raw:
            for h in FWD_HORIZONS:
                fwd = compute_forward_return(all_prices[pair], ts, h)
                if fwd is not None:
                    fwd_raw[h][pair] = fwd

        # ── C1 raw composite (for H1_neg_c1) ───────────────────────────────────
        median_r2h_vals = sorted(r2h_raw.values())
        median_r2h      = median_r2h_vals[len(median_r2h_vals) // 2]
        c1_raw: Dict[str, float] = {}
        for pair in r6h_raw:
            c1_raw[pair] = (
                C1_WEIGHT_R30M  * r1h_raw.get(pair, 0.0)
                + C1_WEIGHT_R2H   * r2h_raw.get(pair, 0.0)
                + C1_WEIGHT_R6H   * r6h_raw.get(pair, 0.0)
                + C1_WEIGHT_R24H  * r24h_raw.get(pair, 0.0)
                + C1_WEIGHT_CS_RS * (r2h_raw.get(pair, 0.0) - median_r2h)
            )

        # ── H1: Cross-sectional reversal (CS z-score of negative return) ───────
        h1_signals: Dict[str, Dict[str, float]] = {
            "H1_neg_r1h":  cross_sectional_z({p: -v for p, v in r1h_raw.items()}),
            "H1_neg_r2h":  cross_sectional_z({p: -v for p, v in r2h_raw.items()}),
            "H1_neg_r6h":  cross_sectional_z({p: -v for p, v in r6h_raw.items()}),
            "H1_neg_r24h": cross_sectional_z({p: -v for p, v in r24h_raw.items()}),
            "H1_neg_c1":   cross_sectional_z({p: -v for p, v in c1_raw.items()}),
        }

        # ── H2a: BTC catch-up (altcoins that underperformed BTC) ───────────────
        btc_r1h = compute_return(btc_prices, ts, 1.0)
        btc_r2h = compute_return(btc_prices, ts, 2.0)
        btc_r6h = compute_return(btc_prices, ts, 6.0)

        h2a_signals: Dict[str, Dict[str, float]] = {}
        if btc_r1h is not None and len(r1h_raw) >= n_min:
            h2a_signals["H2a_neg_rel_btc_r1h"] = cross_sectional_z(
                {p: btc_r1h - r1h_raw[p] for p in r1h_raw}
            )
        if btc_r2h is not None and len(r2h_raw) >= n_min:
            h2a_signals["H2a_neg_rel_btc_r2h"] = cross_sectional_z(
                {p: btc_r2h - r2h_raw[p] for p in r2h_raw}
            )
        if btc_r6h is not None and len(r6h_raw) >= n_min:
            h2a_signals["H2a_neg_rel_btc_r6h"] = cross_sectional_z(
                {p: btc_r6h - r6h_raw[p] for p in r6h_raw}
            )

        # ── H2b: Lagged BTC predictor (market-level, not cross-sectional) ──────
        # btc_lag1h: BTC 1h return ending at ts-1h  (= BTC 1h ago)
        # btc_lag2h: BTC 2h return ending at ts-2h  (= BTC 2h ago)
        btc_lag1h = compute_return(btc_prices, ts - 3_600_000, 1.0)
        btc_lag2h = compute_return(btc_prices, ts - 7_200_000, 2.0)

        for h in FWD_HORIZONS:
            if len(fwd_raw[h]) < n_min:
                continue
            mean_fwd = sum(fwd_raw[h].values()) / len(fwd_raw[h])
            if btc_lag1h is not None:
                h2b_pairs["H2b_btc_lag1h"][h].append((btc_lag1h, mean_fwd))
            if btc_lag2h is not None:
                h2b_pairs["H2b_btc_lag2h"][h].append((btc_lag2h, mean_fwd))

        # ── H5: Volatility-adjusted momentum ───────────────────────────────────
        h5_raw: Dict[str, Dict[str, float]] = {
            "H5_sharpe_6h": {}, "H5_sharpe_24h": {},
            "H5_sortino_6h": {}, "H5_neg_vol": {},
        }
        for pair in r6h_raw:
            rv6  = realized_vol(all_prices[pair], ts, 6)
            rv24 = realized_vol(all_prices[pair], ts, 24)
            dv6  = downside_vol(all_prices[pair], ts, 6)

            if rv6 is not None:
                h5_raw["H5_sharpe_6h"][pair]  = r6h_raw[pair]  / rv6
                h5_raw["H5_neg_vol"][pair]    = -rv6

            if rv24 is not None and pair in r24h_raw:
                h5_raw["H5_sharpe_24h"][pair] = r24h_raw[pair] / rv24

            h5_raw["H5_sortino_6h"][pair] = r6h_raw[pair] / dv6

        h5_signals: Dict[str, Dict[str, float]] = {
            sig: cross_sectional_z(raw)
            for sig, raw in h5_raw.items()
            if len(raw) >= n_min
        }

        # ── H6: Candle persistence / streak ────────────────────────────────────
        h6_up_pct:   Dict[str, float] = {}
        h6_body_mean: Dict[str, float] = {}

        for pair in r6h_raw:
            up_count = body_sum = body_cnt = total = 0

            for lag in range(STREAK_WINDOW):
                t_lag = ts - lag * 3_600_000
                op = (all_open.get(pair) or {}).get(t_lag)
                cl = all_prices[pair].get(t_lag)
                hi = (all_high.get(pair) or {}).get(t_lag)
                lo = (all_low.get(pair)  or {}).get(t_lag)
                if op is None or cl is None:
                    continue
                up_count += 1 if cl > op else 0
                total    += 1
                if hi is not None and lo is not None:
                    hl = hi - lo
                    if hl > 0:
                        body_sum += abs(cl - op) / hl
                        body_cnt += 1

            if total > 0:
                h6_up_pct[pair] = up_count / total
            if body_cnt > 0:
                h6_body_mean[pair] = body_sum / body_cnt

        # H6_streak_ts: TS z-score of up_pct_6h vs own 48-bar history → CS z
        h6_streak_ts_raw: Dict[str, float] = {
            pair: z_score(h6_up_pct[pair], h6_up_pct_hist.get(pair, []))
            for pair in h6_up_pct
        }

        h6_signals: Dict[str, Dict[str, float]] = {}
        if len(h6_up_pct) >= n_min:
            h6_signals["H6_up_pct_6h"]   = cross_sectional_z(h6_up_pct)
        if len(h6_streak_ts_raw) >= n_min:
            h6_signals["H6_streak_ts"]    = cross_sectional_z(h6_streak_ts_raw)
        if len(h6_body_mean) >= n_min:
            h6_signals["H6_body_mean_6h"] = cross_sectional_z(h6_body_mean)

        # Update H6 TS histories after computing signal (no look-ahead)
        for pair in h6_up_pct:
            h6_up_pct_hist[pair].append(h6_up_pct[pair])
            if len(h6_up_pct_hist[pair]) > H6_TS_LOOKBACK:
                h6_up_pct_hist[pair] = h6_up_pct_hist[pair][-H6_TS_LOOKBACK:]

        # ── Accumulate per-timestamp IC for all CS signals × horizons ──────────
        all_cs_at_ts: Dict[str, Dict[str, float]] = {}
        all_cs_at_ts.update(h1_signals)
        all_cs_at_ts.update(h2a_signals)
        all_cs_at_ts.update(h5_signals)
        all_cs_at_ts.update(h6_signals)

        for sig_name, sig_vals in all_cs_at_ts.items():
            if sig_name not in cs_period_ics:
                continue
            for h in FWD_HORIZONS:
                common_p = [p for p in sig_vals if p in fwd_raw[h]]
                if len(common_p) < 5:
                    continue
                ic = spearman_ic(
                    [sig_vals[p] for p in common_p],
                    [fwd_raw[h][p] for p in common_p],
                )
                if ic is not None:
                    cs_period_ics[sig_name][h].append(ic)

    return cs_period_ics, h2b_pairs


# ── Output Formatting ──────────────────────────────────────────────────────────

def _fmt_cell(mean_ic: Optional[float], t: Optional[float]) -> str:
    """Format one IC table cell: '+0.024*' or '  N/A '."""
    if mean_ic is None:
        return "  N/A "
    sig = "*" if (t is not None and abs(t) > TSTAT_GATE_MIN) else " "
    return f"{mean_ic:+.3f}{sig}"


def _gate_check(stats_by_h: Dict[int, dict]) -> Tuple[bool, bool, Optional[int]]:
    """Return (passes_gate, promotion_quality, best_horizon)."""
    gate = promote = False
    best_h, best_ic = None, -999.0
    for h, s in stats_by_h.items():
        ic = s.get("mean_ic")
        t  = s.get("t_stat")
        if ic is None:
            continue
        if ic > best_ic:
            best_ic = ic
            best_h  = h
        if ic > IC_GATE_MIN and t is not None and abs(t) > TSTAT_GATE_MIN:
            gate = True
        if ic > IC_PROMOTE_MIN and t is not None and abs(t) > TSTAT_PROMOTE:
            promote = True
    return gate, promote, best_h


def write_hypothesis_md(
    hyp_id: str,
    hyp_title: str,
    cs_signals: List[str],
    cs_period_ics: Dict[str, Dict[int, List[float]]],
    h2b_pairs: Optional[Dict[str, Dict[int, List[Tuple[float, float]]]]] = None,
) -> None:
    """Write IC decay profile table for one hypothesis family."""
    filename = os.path.join(VALIDATION_DIR, f"{hyp_id}.md")

    # Pre-compute stats for all signals
    all_stats: Dict[str, Dict[int, dict]] = {}
    for sig in cs_signals:
        all_stats[sig] = {
            h: ic_stats(cs_period_ics.get(sig, {}).get(h, []))
            for h in FWD_HORIZONS
        }

    lines = [
        f"# {hyp_id} — {hyp_title}",
        "",
        "**Proxy universe:** `research/02_proxy_universe.md` (pre-committed, FROZEN)  ",
        "**Test period:** Oct 2024–Jan 2025 (trending period, BTC +61% bull run)  ",
        "**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  ",
        "**Promotion gate:** IC > 0.03 AND t > 1.5  ",
        "",
        f"Star `*` = |t| > {TSTAT_GATE_MIN}. All ICs are Spearman rank correlation.",
        "",
        "## IC Decay Profile",
        "",
        "| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |",
        "|--------|----|----|----|----|----|-----|------|------|",
    ]

    passing: List[str] = []
    promote_quality: List[str] = []

    for sig in cs_signals:
        s_by_h = all_stats[sig]
        gate, promo, best_h = _gate_check(s_by_h)

        cells   = [_fmt_cell(s_by_h[h].get("mean_ic"), s_by_h[h].get("t_stat"))
                   for h in FWD_HORIZONS]
        best_str = f"{best_h}h" if best_h is not None else "—"
        gate_str = "**PASS**" if gate else "fail"

        lines.append(f"| `{sig}` | {' | '.join(cells)} | {best_str} | {gate_str} |")

        if gate:
            passing.append(sig)
        if promo:
            promote_quality.append(sig)

    # H2b section (Pearson r, market-level signal)
    if h2b_pairs:
        lines += [
            "",
            "## H2b: Lagged BTC Predictor — Pearson Correlation",
            "",
            "These are market-level signals (same value for all pairs at each timestamp).  ",
            "Cannot use cross-sectional Spearman IC. Tested as time-series Pearson r:  ",
            "does btc_lag_ret correlate with mean cross-sectional altcoin forward return?  ",
            "Gate: Pearson r > 0.05 AND t > 1.0.",
            "",
            "| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |",
            "|--------|----|----|----|----|----|-----|------|------|",
        ]
        for sig in H2B_SIGNALS:
            if sig not in h2b_pairs:
                continue
            cells    = []
            best_h   = None
            best_r   = -999.0
            gate_pass = False
            for h in FWD_HORIZONS:
                pts = h2b_pairs[sig].get(h, [])
                if len(pts) < 10:
                    cells.append("  N/A ")
                    continue
                r = pearson_r([p[0] for p in pts], [p[1] for p in pts])
                if r is None:
                    cells.append("  N/A ")
                    continue
                t = t_stat(r, len(pts))
                if r > best_r:
                    best_r = r
                    best_h = h
                if r > 0.05 and abs(t) > TSTAT_GATE_MIN:
                    gate_pass = True
                sig_str = "*" if abs(t) > TSTAT_GATE_MIN else " "
                cells.append(f"{r:+.3f}{sig_str}")

            best_str = f"{best_h}h" if best_h is not None else "—"
            gate_str = "**PASS**" if gate_pass else "fail"
            lines.append(f"| `{sig}` | {' | '.join(cells)} | {best_str} | {gate_str} |")
            if gate_pass:
                passing.append(sig)

    # Decision gate summary
    lines += ["", "## Decision Gate Summary", ""]
    if passing:
        lines.append(f"**Passes gate (IC>0, t>1.0):** {', '.join(f'`{s}`' for s in passing)}")
    if promote_quality:
        lines.append(
            f"**Promotion-quality (IC>{IC_PROMOTE_MIN}, t>{TSTAT_PROMOTE}):** "
            f"{', '.join(f'`{s}`' for s in promote_quality)}"
        )
    if not passing:
        lines.append(
            "**No signals pass the IC gate** (IC>0 AND t>1.0) at any forward horizon.  "
        )

    # n-observation counts for primary signals
    lines += ["", "## Sample Sizes", ""]
    lines.append("| Signal | Obs (6h horizon) |")
    lines.append("|--------|-----------------|")
    for sig in cs_signals:
        n = all_stats[sig][6].get("n", 0)
        lines.append(f"| `{sig}` | {n} |")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"  Written: {filename}")


# ── Console Summary ────────────────────────────────────────────────────────────

def print_summary_table(
    cs_period_ics: Dict[str, Dict[int, List[float]]],
    h2b_pairs: Dict[str, Dict[int, List[Tuple[float, float]]]],
) -> bool:
    """Print best-IC summary for all signals. Returns True if any signal passes gate."""
    print("\n" + "=" * 72)
    print("SIGNAL SEARCH RESULTS — Best IC across all horizons (trending period)")
    print("=" * 72)
    print(f"{'Signal':<30} {'BestIC':>8} {'BestH':>6} {'t-stat':>7} {'Gate':>10}")
    print("-" * 72)

    any_pass = False

    for sig in CS_SIGNALS:
        best_ic = best_t = best_h = None
        for h in FWD_HORIZONS:
            s = ic_stats(cs_period_ics.get(sig, {}).get(h, []))
            if s["mean_ic"] is not None:
                if best_ic is None or s["mean_ic"] > best_ic:
                    best_ic = s["mean_ic"]
                    best_t  = s["t_stat"]
                    best_h  = h

        if best_ic is None:
            print(f"  {sig:<30} {'N/A':>8} {'—':>6} {'—':>7} {'fail':>10}")
            continue

        gate = (best_ic > IC_GATE_MIN
                and best_t is not None and abs(best_t) > TSTAT_GATE_MIN)
        if gate:
            any_pass = True
        promo = (best_ic > IC_PROMOTE_MIN
                 and best_t is not None and abs(best_t) > TSTAT_PROMOTE)
        gate_str = "PROMOTE" if promo else ("PASS" if gate else "fail")
        print(f"  {sig:<30} {best_ic:+8.4f} {str(best_h)+'h':>6} "
              f"{best_t:+7.2f} {gate_str:>10}")

    # H2b
    print("")
    for sig in H2B_SIGNALS:
        best_r = best_t = best_h = None
        for h in FWD_HORIZONS:
            pts = h2b_pairs.get(sig, {}).get(h, [])
            if len(pts) < 10:
                continue
            r = pearson_r([p[0] for p in pts], [p[1] for p in pts])
            if r is None:
                continue
            t = t_stat(r, len(pts))
            if best_r is None or r > best_r:
                best_r = r
                best_t = t
                best_h = h

        if best_r is None:
            print(f"  {sig:<30} {'N/A':>8} {'—':>6} {'—':>7} {'fail':>10}")
            continue

        gate = (best_r > 0.05 and best_t is not None and abs(best_t) > TSTAT_GATE_MIN)
        if gate:
            any_pass = True
        gate_str = "PASS" if gate else "fail"
        print(f"  {sig:<30} {best_r:+8.4f} {str(best_h)+'h':>6} "
              f"{best_t:+7.2f} {gate_str:>10}  [Pearson r]")

    print("=" * 72)
    if any_pass:
        print(">> Signal(s) pass IC gate. Proceed to Phase 3 (GP refinement).")
        print("   Write research/04_gp_search/<H>_gp.md BEFORE running GP.")
    else:
        print(">> No signals pass the IC gate at any horizon.")
        print("   Write research/08_limitations_and_rejections.md.")
    print("=" * 72)
    return any_pass


# ── Heatmap Chart ──────────────────────────────────────────────────────────────

def generate_heatmap(cs_period_ics: Dict[str, Dict[int, List[float]]]) -> None:
    """IC heatmap: signals × forward horizons, colored by IC magnitude."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  [WARN] matplotlib not available — skipping heatmap")
        return

    ic_matrix = []
    t_matrix  = []
    for sig in CS_SIGNALS:
        row_ic = []
        row_t  = []
        for h in FWD_HORIZONS:
            s = ic_stats(cs_period_ics.get(sig, {}).get(h, []))
            row_ic.append(s["mean_ic"] if s["mean_ic"] is not None else 0.0)
            row_t.append(s["t_stat"]   if s["t_stat"]  is not None else 0.0)
        ic_matrix.append(row_ic)
        t_matrix.append(row_t)

    ic_arr = np.array(ic_matrix)
    t_arr  = np.array(t_matrix)
    vmax   = max(0.06, float(np.abs(ic_arr).max()))

    fig, ax = plt.subplots(figsize=(11, 8))
    im = ax.imshow(ic_arr, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(FWD_HORIZONS)))
    ax.set_xticklabels([f"{h}h" for h in FWD_HORIZONS])
    ax.set_yticks(range(len(CS_SIGNALS)))
    ax.set_yticklabels(CS_SIGNALS, fontsize=8)

    # Annotate cells: IC value + star for |t| > 1.0
    for i in range(len(CS_SIGNALS)):
        for j in range(len(FWD_HORIZONS)):
            star = "*" if abs(t_arr[i, j]) > TSTAT_GATE_MIN else ""
            ax.text(j, i, f"{ic_arr[i, j]:+.3f}{star}",
                    ha="center", va="center", fontsize=7.5, color="black")

    # Horizontal separators between hypothesis families
    for y in [4.5, 7.5, 11.5]:
        ax.axhline(y, color="white", linewidth=2)

    # Family labels on right
    for label, y in [("H1 Reversal", 2), ("H2a BTC-laggard", 6),
                     ("H5 Vol-adj.", 9.5), ("H6 Streak", 13)]:
        ax.text(len(FWD_HORIZONS) + 0.05, y, label, va="center",
                fontsize=8, color="#444", transform=ax.transData)

    plt.colorbar(im, ax=ax, label="Mean Spearman IC", shrink=0.8)
    ax.set_title(
        "Signal IC Decay Profile — H1/H2a/H5/H6\n"
        "Trending Period Oct 2024–Jan 2025  |  * = |t| > 1.0",
        fontsize=11,
    )
    ax.set_xlabel("Forward Return Horizon")
    ax.set_ylabel("Signal")
    plt.tight_layout()

    out = os.path.join(CHARTS_DIR, "ic_signal_search.png")
    plt.savefig(out, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {out}")


# ── Entry Point ────────────────────────────────────────────────────────────────

def main() -> None:
    # Ensure UTF-8 output on Windows (avoids UnicodeEncodeError for arrow chars)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 72)
    print("signal_search.py -- H1/H2/H5/H6 multi-horizon IC validation")
    print("=" * 72)

    print("\nFetching Roostoo universe...")
    pairs = fetch_roostoo_pairs()
    print(f"  {len(pairs)} pairs")

    trending_months = _month_range(TRENDING_START, TRENDING_END)
    print(f"\nDownloading {len(pairs)} pairs × {len(trending_months)} months "
          f"(Oct 2024–Jan 2025)...")
    (all_prices, _bvol, _qvol, _ntrades, _tbvol,
     all_open, all_high, all_low) = load_klines_all_parallel(
        pairs, trending_months, max_workers=8,
    )

    covered = sum(1 for p in all_prices.values() if len(p) > 100)
    print(f"  {covered}/{len(pairs)} pairs have sufficient data")

    print("\nRunning signal search (H1, H2, H5, H6 × 6 horizons)...")
    cs_period_ics, h2b_pairs = run_signal_search(
        all_prices, all_open, all_high, all_low,
    )

    print("\nWriting validation results...")
    write_hypothesis_md(
        "H1_reversal",
        "Short-Term Cross-Sectional Reversal",
        ["H1_neg_r1h", "H1_neg_r2h", "H1_neg_r6h", "H1_neg_r24h", "H1_neg_c1"],
        cs_period_ics,
    )
    write_hypothesis_md(
        "H2_btc_laggard",
        "BTC Leader-Laggard Catch-Up",
        ["H2a_neg_rel_btc_r1h", "H2a_neg_rel_btc_r2h", "H2a_neg_rel_btc_r6h"],
        cs_period_ics,
        h2b_pairs=h2b_pairs,
    )
    write_hypothesis_md(
        "H5_voladj_momentum",
        "Volatility-Adjusted Momentum (Sharpe Ranking)",
        ["H5_sharpe_6h", "H5_sharpe_24h", "H5_sortino_6h", "H5_neg_vol"],
        cs_period_ics,
    )
    write_hypothesis_md(
        "H6_streak_persistence",
        "Candle Persistence (Streak Consistency)",
        ["H6_up_pct_6h", "H6_streak_ts", "H6_body_mean_6h"],
        cs_period_ics,
    )

    any_pass = print_summary_table(cs_period_ics, h2b_pairs)

    print("\nGenerating heatmap...")
    generate_heatmap(cs_period_ics)

    if any_pass:
        print("\nNEXT STEP: Write 04_gp_search/<H>_gp.md declaring GP search space,")
        print("           then run constrained formula grid search.")
    else:
        print("\nNEXT STEP: Write 08_limitations_and_rejections.md.")
        print("           Strategy deploys with regime gating only.")

    sys.stdout.flush()


if __name__ == "__main__":
    main()
