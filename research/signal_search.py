"""
research/signal_search.py — Multi-hypothesis, multi-horizon IC validation.

Tests all pre-committed proxy families across three conditions:
  C1 Alpha:   H1 CS reversal, H1 TS reversal, H2a/H2c/H2d BTC-diffusion,
              H5 vol-adjusted stability, H6 candle persistence
  C2 Hazard:  tested separately in modifier_screen.py
  C3 Maturity: tested separately in modifier_screen.py

Each proxy is tested at 6 forward horizons: 1h, 2h, 4h, 6h, 12h, 24h.
IC decay profile (IC vs horizon) reveals optimal holding period.

Decision gate:
  IC > 0  AND  t > 1.0  at ANY horizon  →  PASS
  IC > 0.03  AND  t > 1.5              →  promotion-quality

Run:
  python -X utf8 research/signal_search.py

Outputs:
  research/H1_reversal/03_results/01_ic_results.md       (H1 CS family)
  research/H1_reversal/03_results/02_stability_screen.md (H5 family)
  research/H1_reversal/03_results/03_rejected_proxies.md (H6 family)
  research/H1_reversal/03_results/05_ts_variant_search.md (TS + H2c/H2d new proxies)
  research/H2_transitional_drift/03_results/01_ic_results.md (H2a collapse + H2b)
  research/charts/03_validation/ic_heatmap.png           (signal × horizon heatmap)
  research/charts/03_validation/ic_decay.png             (IC decay line chart)
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
TS_LOOKBACK     = 48                      # bars for TS z-score history
TS_MIN_BARS     = 6                       # minimum bars to compute TS z-score
BETA_LOOKBACK   = 48                      # bars for rolling beta estimation
BETA_MIN_BARS   = 10                      # minimum pairs for valid beta

IC_GATE_MIN     = 0.0                     # minimum IC to pass gate
TSTAT_GATE_MIN  = 1.0                     # minimum |t| to pass gate
IC_PROMOTE_MIN  = 0.03                    # IC for promotion-quality
TSTAT_PROMOTE   = 1.5                     # t for promotion-quality

# Output directories
H1_RESULTS_DIR   = os.path.join(_here, "H1_reversal", "03_results")
H2_RESULTS_DIR   = os.path.join(_here, "H2_transitional_drift", "03_results")
CHARTS_VAL_DIR   = os.path.join(_here, "charts", "03_validation")
os.makedirs(H1_RESULTS_DIR, exist_ok=True)
os.makedirs(H2_RESULTS_DIR, exist_ok=True)
os.makedirs(CHARTS_VAL_DIR, exist_ok=True)


# ── Signal universe (all CS-normalized outputs) ────────────────────────────────

CS_SIGNALS = [
    # ── H1: Cross-sectional reversal (existing PROMOTED signals) ─────────────
    "H1_neg_r1h", "H1_neg_r2h", "H1_neg_r6h", "H1_neg_r24h", "H1_neg_c1",
    # ── H2a: BTC catch-up, CS-framed (collapses to H1) ───────────────────────
    "H2a_neg_rel_btc_r1h", "H2a_neg_rel_btc_r2h", "H2a_neg_rel_btc_r6h",
    # ── H2c: beta-adjusted divergence (NEW — non-collapsed H2 proxy) ─────────
    "H2c_beta_adj_gap",
    # ── H2d: BTC-gated H1 (NEW — operationalises mechanism test finding) ─────
    "H2d_btcgated_h1",
    # ── H5: vol-adjusted stability filter ────────────────────────────────────
    "H5_sharpe_6h", "H5_sharpe_24h", "H5_sortino_6h", "H5_neg_vol",
    # ── H6: candle persistence (expected to fail) ────────────────────────────
    "H6_up_pct_6h", "H6_streak_ts", "H6_body_mean_6h",
    # ── H1_TS: time-series overshoot (NEW — TS variants of H1 mechanism) ─────
    "TS_zscore_neg_r6h", "TS_zscore_neg_r2h", "TS_bb_dist", "CS_TS_blend_r6h",
]

H2B_SIGNALS = ["H2b_btc_lag1h", "H2b_btc_lag2h"]


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


# ── Time-Series and Beta Helpers ───────────────────────────────────────────────

def ts_zscore(value: float, history: List[float], min_bars: int = TS_MIN_BARS) -> Optional[float]:
    """Time-series z-score of value relative to accumulated history.

    Returns None if insufficient observations. History should NOT include
    the current value (call this BEFORE appending value to history).
    """
    if len(history) < min_bars:
        return None
    mean = sum(history) / len(history)
    std  = math.sqrt(sum((v - mean) ** 2 for v in history) / len(history)) or 1e-8
    return (value - mean) / std


def rolling_beta(
    pair_r1h_hist: List[Tuple[float, float]],
    min_obs: int = BETA_MIN_BARS,
) -> Optional[float]:
    """Rolling OLS beta: slope of asset_r1h on btc_r1h.

    pair_r1h_hist: list of (btc_r1h, asset_r1h) tuples from past observations.
    Returns beta = Cov(r_i, r_btc) / Var(r_btc). None if insufficient data.
    """
    if len(pair_r1h_hist) < min_obs:
        return None
    btc_vals = [p[0] for p in pair_r1h_hist]
    ast_vals = [p[1] for p in pair_r1h_hist]
    n = len(btc_vals)
    btc_mean = sum(btc_vals) / n
    ast_mean = sum(ast_vals) / n
    var_btc  = sum((v - btc_mean) ** 2 for v in btc_vals) / n
    if var_btc < 1e-12:
        return None
    cov = sum((btc_vals[i] - btc_mean) * (ast_vals[i] - ast_mean) for i in range(n)) / n
    return cov / var_btc


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
    std_ic  = math.sqrt(sum((v - mean_ic) ** 2 for v in period_ics) / n) or 1e-8
    hit_rate = sum(1 for v in period_ics if v > 0) / n
    t = mean_ic / (std_ic / math.sqrt(n))
    return {"n": n, "mean_ic": mean_ic, "t_stat": t, "hit_rate": hit_rate}


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
    Compute per-timestamp Spearman IC for all signal families at all horizons.

    New in this version:
      H2c_beta_adj_gap  — rolling-beta-adjusted BTC gap (non-collapsed H2 proxy)
      H2d_btcgated_h1   — H1 signal masked to 0 when BTC flat (|r_BTC,2h| < 0.5%)
      TS_zscore_neg_r6h — time-series z-score of 6h return vs own 48h history
      TS_zscore_neg_r2h — time-series z-score of 2h return vs own 48h history
      TS_bb_dist        — negative Bollinger band distance (price vs rolling SMA/std)
      CS_TS_blend_r6h   — 0.5×CS_z(−r_6h) + 0.5×TS_z(−r_6h)

    Returns:
        cs_period_ics:  {signal: {horizon_h: [ic_at_ts, ...]}}
        h2b_pairs:      {signal: {horizon_h: [(btc_lag_ret, mean_fwd_ret), ...]}}
    """
    active_pairs = [sym for sym, p in all_prices.items() if len(p) > 100]
    if not active_pairs:
        return {}, {}

    all_ts_union: set = set()
    for sym in active_pairs:
        all_ts_union.update(all_prices[sym].keys())
    common_ts  = sorted(all_ts_union)
    btc_prices = all_prices.get("BTCUSDT", {})
    n_min      = max(5, len(active_pairs) // 4)

    print(f"  Active pairs: {len(active_pairs)}, timestamps: {len(common_ts)}")

    cs_period_ics: Dict[str, Dict[int, List[float]]] = {
        s: {h: [] for h in FWD_HORIZONS} for s in CS_SIGNALS
    }
    h2b_pairs: Dict[str, Dict[int, List[Tuple[float, float]]]] = {
        s: {h: [] for h in FWD_HORIZONS} for s in H2B_SIGNALS
    }

    # ── Per-asset TS history dicts (updated at END of each ts — no look-ahead) ─
    h6_up_pct_hist:  Dict[str, List[float]] = {p: [] for p in active_pairs}
    ts_r6h_hist:     Dict[str, List[float]] = {p: [] for p in active_pairs}
    ts_r2h_hist:     Dict[str, List[float]] = {p: [] for p in active_pairs}
    ts_price_hist:   Dict[str, List[float]] = {p: [] for p in active_pairs}
    # beta_hist: per asset, list of (btc_r1h, asset_r1h) pairs from PAST observations
    beta_hist: Dict[str, List[Tuple[float, float]]] = {p: [] for p in active_pairs}

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
            # Still update histories to avoid data gaps
            for pair in r6h_raw:
                if all_prices[pair].get(ts) is not None:
                    ts_price_hist[pair].append(all_prices[pair][ts])
                    if len(ts_price_hist[pair]) > TS_LOOKBACK:
                        ts_price_hist[pair] = ts_price_hist[pair][-TS_LOOKBACK:]
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

        # ── H1: Cross-sectional reversal ────────────────────────────────────────
        h1_signals: Dict[str, Dict[str, float]] = {
            "H1_neg_r1h":  cross_sectional_z({p: -v for p, v in r1h_raw.items()}),
            "H1_neg_r2h":  cross_sectional_z({p: -v for p, v in r2h_raw.items()}),
            "H1_neg_r6h":  cross_sectional_z({p: -v for p, v in r6h_raw.items()}),
            "H1_neg_r24h": cross_sectional_z({p: -v for p, v in r24h_raw.items()}),
            "H1_neg_c1":   cross_sectional_z({p: -v for p, v in c1_raw.items()}),
        }

        # ── H2a: BTC catch-up (CS-framed — mathematically collapses to H1) ─────
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

        # ── H2c: Beta-adjusted divergence (NEW non-collapsed H2 proxy) ──────────
        # beta_i × r_BTC,2h − r_i,2h — selects alts that underperformed their
        # expected BTC-correlated return. Survives CS normalization because beta_i
        # varies across assets (unlike H2a which uses unit beta implicitly).
        h2c_raw: Dict[str, float] = {}
        if btc_r2h is not None:
            for pair in r2h_raw:
                beta = rolling_beta(beta_hist.get(pair, []))
                if beta is not None:
                    # gap > 0 means alt underperformed its BTC-implied return → buy signal
                    h2c_raw[pair] = beta * btc_r2h - r2h_raw[pair]
        h2c_signals: Dict[str, Dict[str, float]] = {}
        if len(h2c_raw) >= n_min:
            h2c_signals["H2c_beta_adj_gap"] = cross_sectional_z(h2c_raw)

        # ── H2d: BTC-gated H1 (NEW — conditional on BTC having moved) ───────────
        # H1 signal fires only when |r_BTC,2h| >= 0.5%. When BTC is flat, both
        # signals are zeroed. Operationalises the mechanism test finding
        # (IC uplift +0.087 when BTC moves).
        h2d_signals: Dict[str, Dict[str, float]] = {}
        if btc_r2h is not None and abs(btc_r2h) >= 0.005:
            # BTC has moved — H1 signal is valid
            h2d_signals["H2d_btcgated_h1"] = cross_sectional_z(
                {p: -v for p, v in r2h_raw.items()}
            )
        else:
            # BTC flat — zero out signal (no expected diffusion)
            h2d_signals["H2d_btcgated_h1"] = {p: 0.0 for p in r2h_raw}

        # ── H5: Volatility-adjusted stability filter ────────────────────────────
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

        # ── H1_TS: Time-series overshoot variants (NEW) ─────────────────────────
        # Each asset normalized against its own 48h return/price history.
        # Complementary to CS variants: CS selects cross-sectional laggards;
        # TS selects assets whose return is low vs their OWN recent baseline.
        ts_z_r6h_raw: Dict[str, float] = {}
        ts_z_r2h_raw: Dict[str, float] = {}
        ts_bb_raw:    Dict[str, float] = {}

        for pair in r6h_raw:
            # TS_zscore_neg_r6h: negate first (laggard = below own mean = positive after negate)
            z6 = ts_zscore(r6h_raw[pair], ts_r6h_hist.get(pair, []))
            if z6 is not None:
                ts_z_r6h_raw[pair] = -z6  # negated: below own history → positive

            # TS_zscore_neg_r2h
            z2 = ts_zscore(r2h_raw[pair], ts_r2h_hist.get(pair, []))
            if z2 is not None:
                ts_z_r2h_raw[pair] = -z2

            # TS_bb_dist: (SMA_6h - price_now) / (2 × std_price_24h)
            price_hist = ts_price_hist.get(pair, [])
            price_now  = all_prices[pair].get(ts)
            if price_now is not None and len(price_hist) >= 24:
                sma6_prices = price_hist[-6:] if len(price_hist) >= 6 else price_hist
                sma6    = sum(sma6_prices) / len(sma6_prices)
                p24     = price_hist[-24:]
                mean24  = sum(p24) / len(p24)
                std24   = math.sqrt(sum((p - mean24) ** 2 for p in p24) / len(p24)) or 1e-8
                ts_bb_raw[pair] = (sma6 - price_now) / (2.0 * std24)

        ts_signals: Dict[str, Dict[str, float]] = {}
        if len(ts_z_r6h_raw) >= n_min:
            ts_signals["TS_zscore_neg_r6h"] = cross_sectional_z(ts_z_r6h_raw)
        if len(ts_z_r2h_raw) >= n_min:
            ts_signals["TS_zscore_neg_r2h"] = cross_sectional_z(ts_z_r2h_raw)
        if len(ts_bb_raw) >= n_min:
            ts_signals["TS_bb_dist"] = cross_sectional_z(ts_bb_raw)

        # CS_TS_blend_r6h: average of CS_z(−r_6h) and TS_z(−r_6h)
        cs_neg_r6h = h1_signals.get("H1_neg_r6h", {})
        ts_neg_r6h = ts_signals.get("TS_zscore_neg_r6h", {})
        blend_pairs = [p for p in cs_neg_r6h if p in ts_neg_r6h]
        if len(blend_pairs) >= n_min:
            blend_raw = {p: 0.5 * cs_neg_r6h[p] + 0.5 * ts_neg_r6h[p] for p in blend_pairs}
            ts_signals["CS_TS_blend_r6h"] = cross_sectional_z(blend_raw)

        # ── Accumulate per-timestamp IC for all CS signals × horizons ──────────
        all_cs_at_ts: Dict[str, Dict[str, float]] = {}
        all_cs_at_ts.update(h1_signals)
        all_cs_at_ts.update(h2a_signals)
        all_cs_at_ts.update(h2c_signals)
        all_cs_at_ts.update(h2d_signals)
        all_cs_at_ts.update(h5_signals)
        all_cs_at_ts.update(h6_signals)
        all_cs_at_ts.update(ts_signals)

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

        # ── Update per-asset histories (AFTER signal computation — no look-ahead) ─
        for pair in r6h_raw:
            # TS return histories
            ts_r6h_hist[pair].append(r6h_raw[pair])
            if len(ts_r6h_hist[pair]) > TS_LOOKBACK:
                ts_r6h_hist[pair] = ts_r6h_hist[pair][-TS_LOOKBACK:]

            ts_r2h_hist[pair].append(r2h_raw[pair])
            if len(ts_r2h_hist[pair]) > TS_LOOKBACK:
                ts_r2h_hist[pair] = ts_r2h_hist[pair][-TS_LOOKBACK:]

            # Price history for BB
            price_now = all_prices[pair].get(ts)
            if price_now is not None:
                ts_price_hist[pair].append(price_now)
                if len(ts_price_hist[pair]) > TS_LOOKBACK:
                    ts_price_hist[pair] = ts_price_hist[pair][-TS_LOOKBACK:]

            # Beta history: accumulate (btc_r1h, asset_r1h) pairs
            if btc_r1h is not None and pair in r1h_raw:
                beta_hist[pair].append((btc_r1h, r1h_raw[pair]))
                if len(beta_hist[pair]) > BETA_LOOKBACK:
                    beta_hist[pair] = beta_hist[pair][-BETA_LOOKBACK:]

        # H6 TS history update
        for pair in h6_up_pct:
            h6_up_pct_hist[pair].append(h6_up_pct[pair])
            if len(h6_up_pct_hist[pair]) > H6_TS_LOOKBACK:
                h6_up_pct_hist[pair] = h6_up_pct_hist[pair][-H6_TS_LOOKBACK:]

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
    output_path: str,
    h2b_pairs: Optional[Dict[str, Dict[int, List[Tuple[float, float]]]]] = None,
) -> None:
    """Write IC decay profile table for one hypothesis family to output_path."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

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
        "**Proxy universe:** pre-committed before IC data observed (frozen)  ",
        "**Test period:** Oct 2024–Jan 2025 (trending, BTC +61% bull run)  ",
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

        cells    = [_fmt_cell(s_by_h[h].get("mean_ic"), s_by_h[h].get("t_stat"))
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
            "Market-level signals (same value for all pairs at each timestamp).  ",
            "Tested as time-series Pearson r: does btc_lag_ret predict mean altcoin return?  ",
            "Gate: Pearson r > 0.05 AND t > 1.0.",
            "",
            "| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |",
            "|--------|----|----|----|----|----|-----|------|------|",
        ]
        for sig in H2B_SIGNALS:
            if sig not in h2b_pairs:
                continue
            cells     = []
            best_h    = None
            best_r    = -999.0
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

    # Sample sizes
    lines += ["", "## Sample Sizes", ""]
    lines.append("| Signal | Obs (4h horizon) | Obs (6h horizon) |")
    lines.append("|--------|-----------------|-----------------|")
    for sig in cs_signals:
        n4 = all_stats[sig][4].get("n", 0)
        n6 = all_stats[sig][6].get("n", 0)
        lines.append(f"| `{sig}` | {n4} | {n6} |")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"  Written: {output_path}")


# ── Console Summary ────────────────────────────────────────────────────────────

def print_summary_table(
    cs_period_ics: Dict[str, Dict[int, List[float]]],
    h2b_pairs: Dict[str, Dict[int, List[Tuple[float, float]]]],
) -> bool:
    """Print best-IC summary for all signals. Returns True if any signal passes gate."""
    print("\n" + "=" * 72)
    print("SIGNAL SEARCH RESULTS — Best IC across all horizons (trending period)")
    print("=" * 72)
    print(f"{'Signal':<35} {'BestIC':>8} {'BestH':>6} {'t-stat':>7} {'Gate':>10}")
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
            print(f"  {sig:<35} {'N/A':>8} {'—':>6} {'—':>7} {'fail':>10}")
            continue

        gate = (best_ic > IC_GATE_MIN
                and best_t is not None and abs(best_t) > TSTAT_GATE_MIN)
        if gate:
            any_pass = True
        promo = (best_ic > IC_PROMOTE_MIN
                 and best_t is not None and abs(best_t) > TSTAT_PROMOTE)
        gate_str = "PROMOTE" if promo else ("PASS" if gate else "fail")
        print(f"  {sig:<35} {best_ic:+8.4f} {str(best_h)+'h':>6} "
              f"{best_t:+7.2f} {gate_str:>10}")

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
            tt = t_stat(r, len(pts))
            if best_r is None or r > best_r:
                best_r = r
                best_t = tt
                best_h = h

        if best_r is None:
            print(f"  {sig:<35} {'N/A':>8} {'—':>6} {'—':>7} {'fail':>10}")
            continue

        gate = (best_r > 0.05 and best_t is not None and abs(best_t) > TSTAT_GATE_MIN)
        if gate:
            any_pass = True
        gate_str = "PASS" if gate else "fail"
        print(f"  {sig:<35} {best_r:+8.4f} {str(best_h)+'h':>6} "
              f"{best_t:+7.2f} {gate_str:>10}  [Pearson r]")

    print("=" * 72)
    return any_pass


# ── Charts ─────────────────────────────────────────────────────────────────────

def generate_heatmap(cs_period_ics: Dict[str, Dict[int, List[float]]]) -> None:
    """IC heatmap: all signals × forward horizons, colored by IC magnitude.

    Families separated by horizontal lines; new TS and H2c/H2d in own sections.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  [WARN] matplotlib not available — skipping heatmap")
        return

    all_sigs = CS_SIGNALS  # 21 signals in defined order
    ic_matrix = []
    t_matrix  = []
    for sig in all_sigs:
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

    n_sigs = len(all_sigs)
    fig_h  = max(8, n_sigs * 0.45)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    im = ax.imshow(ic_arr, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(FWD_HORIZONS)))
    ax.set_xticklabels([f"{h}h" for h in FWD_HORIZONS])
    ax.set_yticks(range(n_sigs))
    ax.set_yticklabels(all_sigs, fontsize=8)

    for i in range(n_sigs):
        for j in range(len(FWD_HORIZONS)):
            star = "*" if abs(t_arr[i, j]) > TSTAT_GATE_MIN else ""
            ax.text(j, i, f"{ic_arr[i, j]:+.3f}{star}",
                    ha="center", va="center", fontsize=7, color="black")

    # Family separators (between groups in CS_SIGNALS order)
    # H1(0-4), H2a(5-7), H2c(8), H2d(9), H5(10-13), H6(14-16), TS(17-20)
    for y in [4.5, 7.5, 9.5, 13.5, 16.5]:
        ax.axhline(y, color="white", linewidth=2)

    # Family labels (right margin)
    family_labels = [
        ("H1 CS Reversal", 2.0),
        ("H2a BTC-laggard\n(collapses)", 6.0),
        ("H2c Beta-adj", 8.0),
        ("H2d BTC-gated", 9.0),
        ("H5 Vol-adj", 11.5),
        ("H6 Streak", 15.0),
        ("H1 TS Overshoot\n(new)", 18.5),
    ]
    for label, y in family_labels:
        ax.text(len(FWD_HORIZONS) + 0.05, y, label, va="center",
                fontsize=7.5, color="#333", transform=ax.transData)

    plt.colorbar(im, ax=ax, label="Mean Spearman IC", shrink=0.7)
    ax.set_title(
        "Signal IC Decay Profile — All Families\n"
        "Oct 2024–Jan 2025 (trending period)  |  * = |t| > 1.0",
        fontsize=11,
    )
    ax.set_xlabel("Forward Return Horizon")
    ax.set_ylabel("Signal")
    plt.tight_layout()

    out = os.path.join(CHARTS_VAL_DIR, "ic_heatmap.png")
    plt.savefig(out, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {out}")


def generate_ic_decay(cs_period_ics: Dict[str, Dict[int, List[float]]]) -> None:
    """IC decay line chart: IC vs horizon for each signal family.

    Shows how IC changes across 1h–24h horizons. Helps identify optimal
    holding period. One line per signal, grouped by family colour.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [WARN] matplotlib not available — skipping decay chart")
        return

    # Group families with colours
    families = [
        ("H1 CS Reversal",    ["H1_neg_r1h", "H1_neg_r2h", "H1_neg_r6h", "H1_neg_c1"],
         "steelblue",   "-"),
        ("H2c/H2d BTC proxy", ["H2c_beta_adj_gap", "H2d_btcgated_h1"],
         "darkorange",  "--"),
        ("H5 Vol Stability",  ["H5_neg_vol"],
         "forestgreen", "-"),
        ("H1 TS Overshoot",   ["TS_zscore_neg_r6h", "TS_zscore_neg_r2h",
                                "TS_bb_dist", "CS_TS_blend_r6h"],
         "mediumpurple", "-."),
        ("H6 Streak (fail)",  ["H6_up_pct_6h", "H6_streak_ts"],
         "lightcoral",  ":"),
    ]

    fig, ax = plt.subplots(figsize=(10, 6))
    x_vals = FWD_HORIZONS

    for family_name, sigs, color, ls in families:
        for sig in sigs:
            ic_vals = [
                ic_stats(cs_period_ics.get(sig, {}).get(h, [])).get("mean_ic") or 0.0
                for h in x_vals
            ]
            ax.plot(x_vals, ic_vals, color=color, linestyle=ls,
                    linewidth=1.5, marker="o", markersize=4, alpha=0.8,
                    label=f"{sig}")

    ax.axhline(0, color="black", linewidth=0.8, linestyle=":")
    ax.axhline(IC_PROMOTE_MIN, color="gray", linewidth=0.8, linestyle="--",
               label=f"Promotion threshold (IC={IC_PROMOTE_MIN})")
    ax.set_xticks(x_vals)
    ax.set_xticklabels([f"{h}h" for h in x_vals])
    ax.set_xlabel("Forward Return Horizon")
    ax.set_ylabel("Mean Spearman IC")
    ax.set_title(
        "IC Decay Profile by Signal Family\n"
        "Oct 2024–Jan 2025  |  - - = promotion threshold (IC=0.03)",
        fontsize=11,
    )
    ax.legend(fontsize=7, ncol=2, loc="upper right")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    out = os.path.join(CHARTS_VAL_DIR, "ic_decay.png")
    plt.savefig(out, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {out}")


# ── Entry Point ────────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 72)
    print("signal_search.py -- All proxy families, multi-horizon IC validation")
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

    print("\nRunning signal search (all families × 6 horizons)...")
    cs_period_ics, h2b_pairs = run_signal_search(
        all_prices, all_open, all_high, all_low,
    )

    print("\nWriting IC results to new canonical locations...")

    # H1 CS reversal family
    write_hypothesis_md(
        "H1_reversal",
        "Short-Term CS Reversal (H1 Family)",
        ["H1_neg_r1h", "H1_neg_r2h", "H1_neg_r6h", "H1_neg_r24h", "H1_neg_c1"],
        cs_period_ics,
        output_path=os.path.join(H1_RESULTS_DIR, "01_ic_results.md"),
    )

    # H5 vol-adjusted stability
    write_hypothesis_md(
        "H5_voladj_momentum",
        "Volatility-Adjusted Stability Filter (H5 Family)",
        ["H5_sharpe_6h", "H5_sharpe_24h", "H5_sortino_6h", "H5_neg_vol"],
        cs_period_ics,
        output_path=os.path.join(H1_RESULTS_DIR, "02_stability_screen.md"),
    )

    # H6 candle persistence (rejected)
    write_hypothesis_md(
        "H6_streak_persistence",
        "Candle Persistence / Streak (H6 Family — Expected to Fail)",
        ["H6_up_pct_6h", "H6_streak_ts", "H6_body_mean_6h"],
        cs_period_ics,
        output_path=os.path.join(H1_RESULTS_DIR, "03_rejected_proxies.md"),
    )

    # H2a collapsed + H2b no-lag
    write_hypothesis_md(
        "H2_btc_laggard",
        "BTC Leader-Laggard (H2a Collapsed, H2b No Lag)",
        ["H2a_neg_rel_btc_r1h", "H2a_neg_rel_btc_r2h", "H2a_neg_rel_btc_r6h"],
        cs_period_ics,
        output_path=os.path.join(H2_RESULTS_DIR, "01_ic_results.md"),
        h2b_pairs=h2b_pairs,
    )

    # TS variants + H2c/H2d (new proxies)
    write_hypothesis_md(
        "H1_TS_and_H2_new",
        "TS Overshoot Variants (H1_TS) + Non-Collapsed H2 Proxies (H2c/H2d)",
        ["TS_zscore_neg_r6h", "TS_zscore_neg_r2h", "TS_bb_dist", "CS_TS_blend_r6h",
         "H2c_beta_adj_gap", "H2d_btcgated_h1"],
        cs_period_ics,
        output_path=os.path.join(H1_RESULTS_DIR, "05_ts_variant_search.md"),
    )

    any_pass = print_summary_table(cs_period_ics, h2b_pairs)

    print("\nGenerating charts...")
    generate_heatmap(cs_period_ics)
    generate_ic_decay(cs_period_ics)

    if any_pass:
        print("\nNEXT STEP: Run gp_search.py with expanded terminal set (includes TS variants).")
    else:
        print("\nNEXT STEP: Document failures in limitations files.")
        print("           Strategy deploys with regime gating only.")

    sys.stdout.flush()


if __name__ == "__main__":
    main()
