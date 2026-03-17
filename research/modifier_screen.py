"""
research/modifier_screen.py — Individual C2 hazard + C3 maturity modifier screens.

For each C2 proxy: run bare C1 backtest vs C1+gate backtest.
  Gate: MaxDD relative improvement ≥ 10% AND worst 30d DD improvement ≥ 5pp → APPROVED

For each C3 proxy: compute IC(fresh) vs IC(unconditional).
  Gate: IC(fresh, proxy below threshold) > IC(unconditional) → APPROVED

C2 proxies tested (6):
  HAZ_BTC_VOL_Z      BTC 6h realized-vol z-score (48h) > 1.50      [existing APPROVED]
  HAZ_CS_DISPERSION  Cross-sectional r_1h dispersion < threshold    [NEW]
  HAZ_SPREAD_Z       OHLC intrabar range z-score (48h) > 1.50       [NEW, bid-ask proxy]
  HAZ_FNG_EXTREME    Fear & Greed index > 75                         [NEW, external API]
  HAZ_MPI_CHOP       Fraction positive 1h returns < 0.30            [NEW, MPI proxy]
  HAZ_BTC_DRAWDOWN   BTC drawdown from 24h rolling high > 2%        [NEW]

C3 proxies tested (7):
  MAT_PCT_RANK       pct_rank(r_6h, 48h) > 0.72                    [existing REJECTED]
  MAT_SMA_EXT        (price − SMA_12h) / SMA_12h > 0.02            [NEW]
  MAT_RSI_PROXY      fraction up bars in last 14 bars > 0.70        [NEW]
  MAT_FUNDING_RATE   price z-score vs 48h baseline > 1.0 (proxy)    [NEW, price proxy]
  MAT_TS_ZSCORE_R6H  TS z-score of r_6h vs own 48h history > 1.50  [NEW, parametric rank]
  MAT_VOL_RATIO      recent 6h volume vs 48h median volume > 2.0    [NEW]
  MAT_CONSEC_UP      fraction of last 6 bars up (positive ret) > 0.75 [NEW]

Run:
  python -X utf8 research/modifier_screen.py

Outputs:
  research/H1_reversal/01_Proxies/Hazard_C2/<PROXY>/02_modifier_screen.md  (×6)
  research/H1_reversal/01_Proxies/Maturity_C3/<PROXY>/02_modifier_screen.md (×7)
  research/charts/modifier_screens/c2_modifier_comparison.png
  research/charts/modifier_screens/c3_ic_lift.png
"""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.request
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
    TRENDING_START,
    TRENDING_END,
    C1_WEIGHT_R30M,
    C1_WEIGHT_R2H,
    C1_WEIGHT_R6H,
    C1_WEIGHT_R24H,
    C1_WEIGHT_CS_RS,
)

# ── Output directories ─────────────────────────────────────────────────────────

PROXIES_DIR   = os.path.join(_here, "H1_reversal", "01_Proxies")
C2_BASE_DIR   = os.path.join(PROXIES_DIR, "Hazard_C2")
C3_BASE_DIR   = os.path.join(PROXIES_DIR, "Maturity_C3")
CHARTS_DIR    = os.path.join(_here, "charts", "modifier_screens")

os.makedirs(C2_BASE_DIR, exist_ok=True)
os.makedirs(C3_BASE_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# ── Backtest configuration ─────────────────────────────────────────────────────

HOLD_HOURS  = 4      # rebalance cadence (must match vector_tests.py)
TOP_N       = 3      # long-only top-N equal weight
W_REV       = 0.70   # promoted C1: reversal weight
W_STAB      = 0.30   # promoted C1: stability weight
LOOKBACK    = 48     # rolling window (hours) for z-scores and histories
PERIOD_DAYS = 30     # subperiod length for worst-period analysis

MS_PER_HOUR = 3_600_000
MS_PER_DAY  = 86_400_000

# ── C2 gate thresholds ─────────────────────────────────────────────────────────

HAZ_BTC_VOL_Z_THRESH   = 1.50   # z-score of BTC vol (existing threshold)
HAZ_DISPERSION_THRESH  = 0.005  # std(r_1h_cs) below this → chop (empirical: ~0.5% hourly)
HAZ_SPREAD_Z_THRESH    = 1.50   # OHLC range z-score threshold
HAZ_FNG_THRESH         = 75     # Fear & Greed > 75 = extreme greed
HAZ_MPI_THRESH         = 0.30   # fraction positive 1h rets < 0.30 = chop
HAZ_BTC_DD_THRESH      = 0.02   # BTC drawdown from 24h high > 2%

# ── C3 maturity thresholds ─────────────────────────────────────────────────────

MAT_PCT_RANK_THRESH    = 0.72   # pct_rank > 0.72 = stale
MAT_SMA_EXT_THRESH     = 0.02   # (price - SMA12) / SMA12 > 2% = extended
MAT_RSI_THRESH         = 0.70   # fraction of up bars in 14h > 70% = overbought
MAT_FUNDING_Z_THRESH   = 1.00   # price z-score vs 48h > 1σ = extended (proxy)
MAT_TS_Z_THRESH        = 1.50   # TS z-score of r_6h > 1.5σ = extended
MAT_VOL_RATIO_THRESH   = 2.00   # recent 6h vol / 48h median vol > 2 = climax
MAT_CONSEC_UP_THRESH   = 0.75   # fraction of last 6 bars up > 75% = streak

# ── C3 fresh thresholds (below = not extended = entry allowed) ─────────────────

MAT_PCT_RANK_FRESH   = 0.30
MAT_SMA_EXT_FRESH    = 0.0      # price at or below SMA12 = fresh
MAT_RSI_FRESH        = 0.30     # < 30% up bars in 14h = oversold = fresh
MAT_FUNDING_Z_FRESH  = 0.0
MAT_TS_Z_FRESH       = -0.50    # below own avg = fresh
MAT_VOL_RATIO_FRESH  = 0.50     # low recent volume = fresh (no climax)
MAT_CONSEC_UP_FRESH  = 0.33     # < 2/6 bars up = fresh


# ── Helper: realized vol ───────────────────────────────────────────────────────

def _realized_vol(
    prices: Dict[int, float],
    ts: int,
    hours: int = 6,
) -> Optional[float]:
    rets = []
    for lag in range(1, hours + 1):
        r = compute_return(prices, ts - lag * MS_PER_HOUR, 1.0)
        if r is not None:
            rets.append(r)
    if len(rets) < max(3, hours // 2):
        return None
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets)) or 1e-8


# ── Signal: promoted 0.70×H1 + 0.30×H5 ───────────────────────────────────────

def _compute_signal(
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts: int,
) -> Optional[Dict[str, float]]:
    """Promoted C1 formula: 0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−vol_6h)."""
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
        rv = _realized_vol(all_prices[pair], ts, 6)
        if rv is not None:
            neg_vol_raw[pair] = -rv
    neg_vol_z = cross_sectional_z(neg_vol_raw) if len(neg_vol_raw) >= 2 else {}

    result: Dict[str, float] = {}
    for pair in neg_c1_z:
        rev  = neg_c1_z.get(pair, 0.0)
        stab = neg_vol_z.get(pair, 0.0)
        result[pair] = W_REV * rev + W_STAB * stab
    return result if len(result) >= n_min else None


# ── Backtest stats ─────────────────────────────────────────────────────────────

def _compute_stats(
    rets: List[float],
    nav_series: List[Tuple[int, float]],
    label: str,
) -> dict:
    n = len(rets)
    if n < 2:
        return {"label": label, "n_periods": n}
    mean_ret = sum(rets) / n
    std_ret  = math.sqrt(sum((r - mean_ret) ** 2 for r in rets) / n) or 1e-8
    sharpe   = mean_ret / std_ret * math.sqrt(365 * 24 / HOLD_HOURS)

    peak = 1.0; running = 1.0; max_dd = 0.0
    for r in rets:
        running *= (1 + r)
        if running > peak:
            peak = running
        dd = (running - peak) / peak
        if dd < max_dd:
            max_dd = dd

    period_steps = PERIOD_DAYS * 24 // HOLD_HOURS
    worst_dd = 0.0
    for i in range(max(0, len(nav_series) - period_steps)):
        s_nav = nav_series[i][1]
        e_nav = nav_series[i + period_steps][1] if (i + period_steps) < len(nav_series) else nav_series[-1][1]
        pdd = (e_nav - s_nav) / s_nav
        if pdd < worst_dd:
            worst_dd = pdd

    hit_rate  = sum(1 for r in rets if r > 0) / n
    final_nav = nav_series[-1][1] if nav_series else 1.0

    return {
        "label":        label,
        "n_periods":    n,
        "sharpe_ann":   sharpe,
        "max_dd":       max_dd,
        "worst_30d":    worst_dd,
        "hit_rate":     hit_rate,
        "total_return": final_nav - 1.0,
        "final_nav":    final_nav,
    }


def _ic_stat(ics: List[float]) -> dict:
    n = len(ics)
    if n < 3:
        return {"n": n, "mean": None, "t": None}
    mean = sum(ics) / n
    std  = math.sqrt(sum((v - mean) ** 2 for v in ics) / n) or 1e-8
    return {"n": n, "mean": mean, "t": mean / (std / math.sqrt(n))}


# ── Fear & Greed history ───────────────────────────────────────────────────────

def fetch_fng_history() -> Dict[int, int]:
    """Fetch historical Fear & Greed daily values from Alternative.me.
    Returns {day_start_ts_ms: fng_value}.
    """
    try:
        url = "https://api.alternative.me/fng/?limit=500&format=json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        result: Dict[int, int] = {}
        for entry in data.get("data", []):
            ts_s = int(entry["timestamp"])
            day_ms = (ts_s // 86400) * 86400 * 1000
            result[day_ms] = int(entry["value"])
        print(f"  [F&G] Loaded {len(result)} daily F&G values")
        return result
    except Exception as exc:
        print(f"  [WARN] Could not fetch F&G history: {exc}. HAZ_FNG_EXTREME will be N/A.")
        return {}


# ── C2 backtest runner ─────────────────────────────────────────────────────────

def run_c2_backtest(
    proxy_id: str,
    all_prices: Dict[str, Dict[int, float]],
    high:       Dict[str, Dict[int, float]],
    low:        Dict[str, Dict[int, float]],
    volumes:    Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps: List[int],
    fng_history: Dict[int, int],
) -> Tuple[dict, dict]:
    """
    Run bare C1 vs C1+gate backtest for one C2 proxy.
    Returns (bare_stats, gated_stats).
    """
    btc_key = next((p for p in active_pairs if p.startswith("BTC")), None)

    # Shared C2 state (rolling histories)
    btc_vol_hist:   List[float]            = []
    range_hist:     Dict[str, List[float]] = {p: [] for p in active_pairs}
    btc_price_max:  float                  = 0.0

    nav_bare   = 1.0;  nav_gated  = 1.0
    rets_bare: List[float]               = []
    rets_gated: List[float]              = []
    nav_bare_series:  List[Tuple[int, float]] = [(timestamps[0], 1.0)]
    nav_gated_series: List[Tuple[int, float]] = [(timestamps[0], 1.0)]

    for i, ts in enumerate(timestamps):
        if i % HOLD_HOURS != 0:
            continue

        sig = _compute_signal(all_prices, active_pairs, ts)
        if sig is None:
            continue

        # ── Compute gate for this proxy ────────────────────────────────────────
        is_blocked = False

        if proxy_id == "HAZ_BTC_VOL_Z":
            if btc_key is not None:
                rv = _realized_vol(all_prices[btc_key], ts, hours=6)
                if rv is not None:
                    btc_vol_hist.append(rv)
                    if len(btc_vol_hist) >= LOOKBACK:
                        w = btc_vol_hist[-LOOKBACK:]
                        m = sum(w) / len(w)
                        s = math.sqrt(sum((x - m) ** 2 for x in w) / len(w)) or 1e-8
                        z = (rv - m) / s
                        is_blocked = z > HAZ_BTC_VOL_Z_THRESH

        elif proxy_id == "HAZ_CS_DISPERSION":
            # Low cross-sectional dispersion = all assets moving together = chop
            r1h_vals = [compute_return(all_prices[p], ts, 1.0) for p in sig if compute_return(all_prices[p], ts, 1.0) is not None]
            if len(r1h_vals) >= 5:
                mean_r1h = sum(r1h_vals) / len(r1h_vals)
                std_r1h  = math.sqrt(sum((v - mean_r1h) ** 2 for v in r1h_vals) / len(r1h_vals))
                is_blocked = std_r1h < HAZ_DISPERSION_THRESH

        elif proxy_id == "HAZ_SPREAD_Z":
            # Intrabar range (high-low)/close as bid-ask spread proxy; z-score
            range_vals: List[float] = []
            for pair in sig:
                h_t = high.get(pair, {}).get(ts)
                l_t = low.get(pair, {}).get(ts)
                c_t = all_prices.get(pair, {}).get(ts)
                if h_t and l_t and c_t and c_t > 0:
                    range_vals.append((h_t - l_t) / c_t)
            if range_vals:
                mean_range = sum(range_vals) / len(range_vals)
                for pair in active_pairs:
                    h_t = high.get(pair, {}).get(ts)
                    l_t = low.get(pair, {}).get(ts)
                    c_t = all_prices.get(pair, {}).get(ts)
                    if h_t and l_t and c_t and c_t > 0:
                        range_hist[pair].append((h_t - l_t) / c_t)
                        if len(range_hist[pair]) > LOOKBACK:
                            range_hist[pair] = range_hist[pair][-LOOKBACK:]
                # Check if current mean range is elevated
                all_recent = [v for p in active_pairs for v in range_hist[p][-LOOKBACK:]]
                if len(all_recent) >= LOOKBACK:
                    m = sum(all_recent) / len(all_recent)
                    s = math.sqrt(sum((v - m) ** 2 for v in all_recent) / len(all_recent)) or 1e-8
                    z = (mean_range - m) / s
                    is_blocked = z > HAZ_SPREAD_Z_THRESH

        elif proxy_id == "HAZ_FNG_EXTREME":
            if fng_history:
                day_key = (ts // MS_PER_DAY) * MS_PER_DAY
                fng_val = fng_history.get(day_key) or fng_history.get(day_key - MS_PER_DAY)
                if fng_val is not None:
                    is_blocked = fng_val > HAZ_FNG_THRESH

        elif proxy_id == "HAZ_MPI_CHOP":
            # Market Participation Index proxy: fraction of assets with positive 1h return
            pos_count = 0; total = 0
            for pair in active_pairs:
                r1h = compute_return(all_prices[pair], ts, 1.0)
                if r1h is not None:
                    total += 1
                    if r1h > 0:
                        pos_count += 1
            if total >= 5:
                mpi = pos_count / total
                is_blocked = mpi < HAZ_MPI_THRESH

        elif proxy_id == "HAZ_BTC_DRAWDOWN":
            if btc_key is not None:
                cur_price = all_prices[btc_key].get(ts)
                if cur_price is not None:
                    # Rolling 24h max
                    max_24h_price = cur_price
                    for lag in range(1, 25):
                        p = all_prices[btc_key].get(ts - lag * MS_PER_HOUR)
                        if p is not None and p > max_24h_price:
                            max_24h_price = p
                    if max_24h_price > 0:
                        dd = (cur_price - max_24h_price) / max_24h_price
                        is_blocked = dd < -HAZ_BTC_DD_THRESH

        # ── Select top-N ──────────────────────────────────────────────────────
        ranked = sorted(sig.items(), key=lambda x: x[1], reverse=True)
        selected = [p for p, _ in ranked[:TOP_N]] if ranked else []

        # ── Bare return ───────────────────────────────────────────────────────
        if selected:
            bare_rets = [compute_forward_return(all_prices[p], ts, HOLD_HOURS)
                         for p in selected]
            bare_rets = [r for r in bare_rets if r is not None]
            port_ret_bare = sum(bare_rets) / len(bare_rets) if bare_rets else 0.0
        else:
            port_ret_bare = 0.0

        nav_bare *= (1 + port_ret_bare)
        rets_bare.append(port_ret_bare)
        nav_bare_series.append((ts + HOLD_HOURS * MS_PER_HOUR, nav_bare))

        # ── Gated return ──────────────────────────────────────────────────────
        if is_blocked or not selected:
            port_ret_gated = 0.0
        else:
            gated_rets = [compute_forward_return(all_prices[p], ts, HOLD_HOURS)
                          for p in selected]
            gated_rets = [r for r in gated_rets if r is not None]
            port_ret_gated = sum(gated_rets) / len(gated_rets) if gated_rets else 0.0

        nav_gated *= (1 + port_ret_gated)
        rets_gated.append(port_ret_gated)
        nav_gated_series.append((ts + HOLD_HOURS * MS_PER_HOUR, nav_gated))

    bare_stats  = _compute_stats(rets_bare,  nav_bare_series,  "bare")
    gated_stats = _compute_stats(rets_gated, nav_gated_series, proxy_id)
    return bare_stats, gated_stats


# ── C3 IC screen runner ────────────────────────────────────────────────────────

def run_c3_ic_screen(
    proxy_id: str,
    all_prices: Dict[str, Dict[int, float]],
    volumes:    Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps: List[int],
) -> dict:
    """
    IC screen for one C3 proxy.
    Returns {"fresh": ic_stat, "stale": ic_stat, "unconditional": ic_stat}.
    """
    # Per-asset rolling state
    r6h_hist:    Dict[str, List[float]] = {p: [] for p in active_pairs}
    price_hist:  Dict[str, List[float]] = {p: [] for p in active_pairs}
    r1h_hist:    Dict[str, List[bool]]  = {p: [] for p in active_pairs}
    vol_hist:    Dict[str, List[float]] = {p: [] for p in active_pairs}

    fresh_ics:  List[float] = []
    stale_ics:  List[float] = []
    all_ics:    List[float] = []

    for i, ts in enumerate(timestamps):
        if i % HOLD_HOURS != 0:
            continue

        sig = _compute_signal(all_prices, active_pairs, ts)
        if sig is None:
            # Still update histories
            for pair in active_pairs:
                _update_histories(proxy_id, pair, all_prices, volumes, ts,
                                  r6h_hist, price_hist, r1h_hist, vol_hist)
            continue

        # Forward returns
        fwd: Dict[str, float] = {}
        for pair in sig:
            f = compute_forward_return(all_prices[pair], ts, HOLD_HOURS)
            if f is not None:
                fwd[pair] = f

        # Classify each asset by maturity proxy
        fresh_pairs: List[str] = []
        stale_pairs: List[str] = []

        for pair in sig:
            mat = _compute_maturity(proxy_id, pair, all_prices, volumes, ts,
                                    r6h_hist, price_hist, r1h_hist, vol_hist)
            _update_histories(proxy_id, pair, all_prices, volumes, ts,
                              r6h_hist, price_hist, r1h_hist, vol_hist)

            if mat is not None:
                fresh_thr, stale_thr = _fresh_stale_thresholds(proxy_id)
                if mat <= fresh_thr:
                    fresh_pairs.append(pair)
                elif mat >= stale_thr:
                    stale_pairs.append(pair)
            else:
                # Not enough history to classify → treat as unconstrained
                pass

        # Unconditional IC
        common_all = {p: (sig[p], fwd[p]) for p in sig if p in fwd}
        if len(common_all) >= 5:
            ic_a = spearman_ic([v[0] for v in common_all.values()],
                               [v[1] for v in common_all.values()])
            if ic_a is not None:
                all_ics.append(ic_a)

        # Fresh IC
        fresh_common = {p: (sig[p], fwd[p]) for p in fresh_pairs if p in fwd}
        if len(fresh_common) >= 4:
            ic_f = spearman_ic([v[0] for v in fresh_common.values()],
                               [v[1] for v in fresh_common.values()])
            if ic_f is not None:
                fresh_ics.append(ic_f)

        # Stale IC
        stale_common = {p: (sig[p], fwd[p]) for p in stale_pairs if p in fwd}
        if len(stale_common) >= 4:
            ic_s = spearman_ic([v[0] for v in stale_common.values()],
                               [v[1] for v in stale_common.values()])
            if ic_s is not None:
                stale_ics.append(ic_s)

    return {
        "fresh":         _ic_stat(fresh_ics),
        "stale":         _ic_stat(stale_ics),
        "unconditional": _ic_stat(all_ics),
    }


def _update_histories(
    proxy_id: str,
    pair: str,
    all_prices: Dict[str, Dict[int, float]],
    volumes:    Dict[str, Dict[int, float]],
    ts: int,
    r6h_hist:   Dict[str, List[float]],
    price_hist: Dict[str, List[float]],
    r1h_hist:   Dict[str, List[bool]],
    vol_hist:   Dict[str, List[float]],
) -> None:
    """Append current values to per-asset histories (called AFTER signal computation)."""
    r6h = compute_return(all_prices[pair], ts, 6.0)
    if r6h is not None:
        r6h_hist[pair].append(r6h)
        if len(r6h_hist[pair]) > LOOKBACK:
            r6h_hist[pair] = r6h_hist[pair][-LOOKBACK:]

    price = all_prices[pair].get(ts)
    if price is not None:
        price_hist[pair].append(price)
        if len(price_hist[pair]) > LOOKBACK:
            price_hist[pair] = price_hist[pair][-LOOKBACK:]

    r1h = compute_return(all_prices[pair], ts, 1.0)
    if r1h is not None:
        r1h_hist[pair].append(r1h > 0)
        if len(r1h_hist[pair]) > 48:
            r1h_hist[pair] = r1h_hist[pair][-48:]

    vol = volumes.get(pair, {}).get(ts)
    if vol is not None:
        vol_hist[pair].append(vol)
        if len(vol_hist[pair]) > LOOKBACK:
            vol_hist[pair] = vol_hist[pair][-LOOKBACK:]


def _compute_maturity(
    proxy_id: str,
    pair: str,
    all_prices: Dict[str, Dict[int, float]],
    volumes:    Dict[str, Dict[int, float]],
    ts: int,
    r6h_hist:   Dict[str, List[float]],
    price_hist: Dict[str, List[float]],
    r1h_hist:   Dict[str, List[bool]],
    vol_hist:   Dict[str, List[float]],
) -> Optional[float]:
    """Compute maturity proxy value for one asset at one timestamp. Returns None if insufficient data."""

    if proxy_id == "MAT_PCT_RANK":
        r6h = compute_return(all_prices[pair], ts, 6.0)
        if r6h is None or len(r6h_hist[pair]) < 10:
            return None
        window = r6h_hist[pair][-LOOKBACK:]
        return sum(1 for v in window if v <= r6h) / len(window)

    elif proxy_id == "MAT_SMA_EXT":
        price = all_prices[pair].get(ts)
        if price is None or len(price_hist[pair]) < 12:
            return None
        sma12 = sum(price_hist[pair][-12:]) / 12
        if sma12 <= 0:
            return None
        return (price - sma12) / sma12

    elif proxy_id == "MAT_RSI_PROXY":
        if len(r1h_hist[pair]) < 14:
            return None
        window = r1h_hist[pair][-14:]
        return sum(1 for v in window if v) / len(window)

    elif proxy_id == "MAT_FUNDING_RATE":
        # Proxy: price z-score vs 48h rolling baseline (elevated price → likely positive funding)
        price = all_prices[pair].get(ts)
        if price is None or len(price_hist[pair]) < 10:
            return None
        window = price_hist[pair][-LOOKBACK:]
        mean_p = sum(window) / len(window)
        std_p  = math.sqrt(sum((v - mean_p) ** 2 for v in window) / len(window)) or 1e-8
        return (price - mean_p) / std_p

    elif proxy_id == "MAT_TS_ZSCORE_R6H":
        r6h = compute_return(all_prices[pair], ts, 6.0)
        if r6h is None or len(r6h_hist[pair]) < 6:
            return None
        window = r6h_hist[pair][-LOOKBACK:]
        mean_r = sum(window) / len(window)
        std_r  = math.sqrt(sum((v - mean_r) ** 2 for v in window) / len(window)) or 1e-8
        return (r6h - mean_r) / std_r

    elif proxy_id == "MAT_VOL_RATIO":
        # Recent 6h volume vs 48h median volume
        if len(vol_hist[pair]) < 6:
            return None
        recent_vol = sum(vol_hist[pair][-6:]) / 6
        all_vols   = vol_hist[pair][-LOOKBACK:]
        sorted_v   = sorted(all_vols)
        median_v   = sorted_v[len(sorted_v) // 2]
        if median_v <= 0:
            return None
        return recent_vol / median_v

    elif proxy_id == "MAT_CONSEC_UP":
        # Fraction of last 6 bars with positive 1h return
        if len(r1h_hist[pair]) < 6:
            return None
        window = r1h_hist[pair][-6:]
        return sum(1 for v in window if v) / len(window)

    return None


def _fresh_stale_thresholds(proxy_id: str) -> Tuple[float, float]:
    """Return (fresh_threshold, stale_threshold) for a C3 proxy.
    fresh: proxy ≤ fresh_thr → entry allowed (signal not yet extended)
    stale: proxy ≥ stale_thr → entry blocked (signal already extended)
    """
    thresholds = {
        "MAT_PCT_RANK":       (MAT_PCT_RANK_FRESH,  MAT_PCT_RANK_THRESH),
        "MAT_SMA_EXT":        (MAT_SMA_EXT_FRESH,   MAT_SMA_EXT_THRESH),
        "MAT_RSI_PROXY":      (MAT_RSI_FRESH,       MAT_RSI_THRESH),
        "MAT_FUNDING_RATE":   (MAT_FUNDING_Z_FRESH,  MAT_FUNDING_Z_THRESH),
        "MAT_TS_ZSCORE_R6H":  (MAT_TS_Z_FRESH,      MAT_TS_Z_THRESH),
        "MAT_VOL_RATIO":      (MAT_VOL_RATIO_FRESH,  MAT_VOL_RATIO_THRESH),
        "MAT_CONSEC_UP":      (MAT_CONSEC_UP_FRESH,  MAT_CONSEC_UP_THRESH),
    }
    return thresholds.get(proxy_id, (0.30, 0.70))


# ── Markdown writers ───────────────────────────────────────────────────────────

_C2_META = {
    "HAZ_BTC_VOL_Z": {
        "description": "BTC 6h realized-vol z-score (48h window) > 1.50",
        "theory": (
            "Elevated BTC realized volatility indicates a stressed market regime "
            "where reversal timing uncertainty is high. When BTC vol z-score exceeds "
            "1.50σ, the risk-adjusted value of entering new long reversal positions "
            "drops sharply: the IC relationship holds on average but drawdown risk "
            "dominates over the 4h holding window."
        ),
        "threshold": "BTC vol z-score > 1.50",
        "prior": "APPROVED (from vector_tests.py Part B)",
    },
    "HAZ_CS_DISPERSION": {
        "description": "Cross-sectional r_1h dispersion (std) < 0.005",
        "theory": (
            "In normal conditions, assets move heterogeneously — the reversal signal "
            "selects genuine laggards. When cross-sectional dispersion collapses "
            "(all assets moving together), the market is in a correlated panic or "
            "correlated melt-up. In this regime, the CS_z signal loses discriminating "
            "power because the spread between leaders and laggards has compressed: "
            "every asset is doing roughly the same thing, so selecting laggards does "
            "not identify genuine mean-reversion candidates."
        ),
        "threshold": "std(r_1h across assets) < 0.005",
        "prior": "Untested",
    },
    "HAZ_SPREAD_Z": {
        "description": "OHLC intrabar range z-score (48h) > 1.50 (bid-ask spread proxy)",
        "theory": (
            "Elevated intrabar high-low range signals liquidity stress. When spreads "
            "are wide, limit orders face adverse selection: the price moves against "
            "the new entry before the reversal has time to materialize. Wide range "
            "is used as a proxy for elevated bid-ask spread (not directly observable "
            "in Binance Vision 1h klines)."
        ),
        "threshold": "(high - low) / close z-score (48h) > 1.50",
        "prior": "Untested",
    },
    "HAZ_FNG_EXTREME": {
        "description": "Crypto Fear & Greed Index > 75 (extreme greed)",
        "theory": (
            "The Fear & Greed index aggregates sentiment from price momentum, social "
            "media, surveys, dominance, and volatility. 'Extreme Greed' (>75) "
            "historically precedes corrections as over-optimism creates fragile "
            "conditions. Unlike price-based hazard signals, F&G is a leading indicator "
            "that reflects positioning before it shows in realized volatility — it "
            "can identify elevated hazard before BTC vol reacts."
        ),
        "threshold": "F&G > 75 (source: Alternative.me)",
        "prior": "Untested",
    },
    "HAZ_MPI_CHOP": {
        "description": "Market Participation Index < 0.30 (fraction positive 1h returns)",
        "theory": (
            "MPI measures how many assets are participating in the market direction. "
            "When fewer than 30% of assets have positive 1h returns, the market is "
            "in a chop or broad sell-off regime. In this state, the reversal thesis "
            "weakens: there is no identifiable leader group, making the diffusion lag "
            "mechanism unreliable. Low MPI also indicates mean-reversion candidates "
            "may continue falling rather than recovering."
        ),
        "threshold": "fraction(r_1h > 0) < 0.30 across universe",
        "prior": "Untested",
    },
    "HAZ_BTC_DRAWDOWN": {
        "description": "BTC drawdown from 24h rolling high > 2%",
        "theory": (
            "An active BTC sell-off (measured as DD from 24h rolling high) signals "
            "that risk-off is in progress. Altcoins typically lag BTC moves by 1-6h, "
            "meaning entering longs on 'laggard' assets during a BTC sell-off is "
            "selecting into the path of incoming losses rather than genuine recovery "
            "candidates. The 2% threshold captures material drawdowns while ignoring "
            "normal intraday oscillations."
        ),
        "threshold": "(BTC_price - BTC_24h_high) / BTC_24h_high < -2%",
        "prior": "Untested",
    },
}

_C3_META = {
    "MAT_PCT_RANK": {
        "description": "pct_rank(r_6h, 48h rolling history) > 0.72",
        "theory": (
            "If the current 6h return is already in the top 72nd percentile of its "
            "own recent history, the laggard has already recovered most of its "
            "expected reversion. Remaining upside is limited. Non-parametric "
            "percentile rank captures the ordinal position without assuming a "
            "return distribution."
        ),
        "threshold": "pct_rank > 0.72 (stale) | < 0.30 (fresh)",
        "prior": "REJECTED standalone (IC gate fail in vector_tests.py Part C)",
    },
    "MAT_SMA_EXT": {
        "description": "(price − SMA_12h) / SMA_12h > 2% (extended above moving average)",
        "theory": (
            "When price is more than 2% above its 12h simple moving average, it has "
            "already moved significantly relative to its recent trend. The reversal "
            "signal requires an asset to be a laggard — but if it is already extended "
            "above its own trend, it is no longer a laggard. This proxy blocks "
            "momentum continuation trades that have outrun their fair value."
        ),
        "threshold": "(price - SMA_12h) / SMA_12h > 0.02 (stale) | ≤ 0 (fresh)",
        "prior": "Not individually screened (in composite, weight 0.40)",
    },
    "MAT_RSI_PROXY": {
        "description": "Fraction of up bars in last 14h > 70% (RSI-like overbought)",
        "theory": (
            "Classic RSI overbought signal adapted for hourly klines. When more than "
            "70% of the last 14 bars have been up-bars, the asset is in a persistent "
            "uptrend and unlikely to revert further. The RSI proxy uses the fraction "
            "of positive-return bars rather than the traditional formula, which "
            "requires price history not always available in kline data."
        ),
        "threshold": "frac(r_1h > 0) in last 14h > 0.70 (stale) | < 0.30 (fresh)",
        "prior": "Not individually screened (in composite, weight 0.15)",
    },
    "MAT_FUNDING_RATE": {
        "description": "Price z-score vs 48h baseline > 1.0σ (funding rate proxy)",
        "theory": (
            "Positive perpetual funding rates indicate long-biased positioning, which "
            "signals overextension. Direct funding rate data requires live Binance "
            "fapi access; for backtesting, price z-score vs 48h rolling mean is used "
            "as a proxy: persistently elevated price levels correlate with positive "
            "funding rates in crypto perpetuals."
        ),
        "threshold": "(price - mean_price_48h) / std_price_48h > 1.0 (stale) | ≤ 0 (fresh)",
        "prior": "Not individually screened (in composite, weight 0.20). Live proxy used.",
    },
    "MAT_TS_ZSCORE_R6H": {
        "description": "TS z-score of r_6h vs own 48h history > 1.5σ",
        "theory": (
            "Parametric alternative to pct_rank. Computes how many standard deviations "
            "the current 6h return is above the asset's own 48h rolling mean return. "
            "Above +1.5σ means the current return is unusually strong vs the asset's "
            "own historical baseline — unlikely to be a laggard in the CS sense. "
            "More sensitive than pct_rank to the magnitude of the deviation."
        ),
        "threshold": "TS z-score > 1.5 (stale) | < -0.5 (fresh)",
        "prior": "Untested",
    },
    "MAT_VOL_RATIO": {
        "description": "Recent 6h volume vs 48h median volume > 2.0× (climax volume)",
        "theory": (
            "High volume relative to recent norms signals potential exhaustion or "
            "climax: the move has attracted broad participation, suggesting the "
            "impulsive phase is ending. High volume on a recovery already in progress "
            "means the easy recovery money has been made. Classic technical analysis "
            "exhaustion signal adapted for the diffusion lag mechanism."
        ),
        "threshold": "mean(vol_6h) / median(vol_48h) > 2.0 (stale) | < 0.5 (fresh)",
        "prior": "Untested",
    },
    "MAT_CONSEC_UP": {
        "description": "Fraction of last 6 bars with positive 1h return > 75%",
        "theory": (
            "Five or more consecutive up-bars (5/6) indicates persistent positive "
            "momentum. This is orthogonal to the RSI proxy (which looks at 14 bars): "
            "MAT_CONSEC_UP captures very recent streak persistence over a 6h window, "
            "specifically relevant for the 4h holding horizon of the strategy. "
            "A laggard on a recent 6-bar streak is no longer a laggard."
        ),
        "threshold": "frac(up) in last 6 bars > 0.75 (stale) | < 0.33 (fresh)",
        "prior": "Untested",
    },
}


def write_c2_markdown(
    proxy_id: str,
    bare: dict,
    gated: dict,
    run_ts: str,
) -> str:
    """Build markdown content for a C2 proxy modifier screen result."""
    meta = _C2_META.get(proxy_id, {})

    bare_dd = bare.get("max_dd", 0) or 0
    gated_dd = gated.get("max_dd", 0) or 0
    bare_wp = bare.get("worst_30d", 0) or 0
    gated_wp = gated.get("worst_30d", 0) or 0

    dd_improv = (gated_dd - bare_dd) / abs(bare_dd) if bare_dd != 0 else 0.0
    wp_improv = gated_wp - bare_wp

    dd_pass = dd_improv >= 0.10
    wp_pass = wp_improv >= 0.05
    approved = dd_pass and wp_pass

    def _fp(v: Optional[float]) -> str:
        return f"{v * 100:.2f}%" if v is not None else "N/A"

    def _f3(v: Optional[float]) -> str:
        return f"{v:.3f}" if v is not None else "N/A"

    verdict = "APPROVED" if approved else "REJECTED"
    if not dd_pass and not wp_pass:
        reason = "neither MaxDD nor worst-30d gates cleared"
    elif not dd_pass:
        reason = "MaxDD gate not cleared (< 10% relative improvement)"
    elif not wp_pass:
        reason = "worst-30d gate not cleared (< 5pp improvement)"
    else:
        reason = "both MaxDD and worst-30d gates cleared"

    lines = [
        f"# C2 Modifier Screen — {proxy_id}\n",
        f"**Run:** {run_ts}  ",
        f"**Period:** Oct 2024 – Jan 2025 (trending period)  ",
        f"**Hold horizon:** {HOLD_HOURS}h | Top-N: {TOP_N} | Equal weight\n",
        f"## Proxy Definition\n",
        f"**Formula:** {meta.get('description', '')}  ",
        f"**Gate threshold:** {meta.get('threshold', '')}  ",
        f"**Prior status:** {meta.get('prior', 'Untested')}\n",
        f"## Economic Rationale\n",
        f"{meta.get('theory', '')}\n",
        f"## Modifier Screen Results\n",
        f"Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d improvement ≥ 5pp.\n",
        f"| Metric | Bare C1 | + {proxy_id} gate | Improvement | Bar | Result |",
        f"|--------|---------|-----------------|-------------|-----|--------|",
        f"| Max Drawdown | {_fp(bare_dd)} | {_fp(gated_dd)} | {_fp(dd_improv)} | ≥ 10% rel | {'PASS' if dd_pass else 'FAIL'} |",
        f"| Worst 30d DD | {_fp(bare_wp)} | {_fp(gated_wp)} | {_fp(wp_improv)} | ≥ 5pp | {'PASS' if wp_pass else 'FAIL'} |",
        f"| Sharpe (ann) | {_f3(bare.get('sharpe_ann'))} | {_f3(gated.get('sharpe_ann'))} | — | — | — |",
        f"| Total Return | {_fp(bare.get('total_return'))} | {_fp(gated.get('total_return'))} | — | — | — |",
        f"| N periods | {bare.get('n_periods', 'N/A')} | {gated.get('n_periods', 'N/A')} | — | — | — |\n",
        f"## Verdict\n",
        f"**{verdict}** — {reason}.\n",
    ]
    return "\n".join(lines)


def write_c3_markdown(
    proxy_id: str,
    result: dict,
    run_ts: str,
) -> str:
    """Build markdown content for a C3 proxy IC screen result."""
    meta = _C3_META.get(proxy_id, {})

    ic_fresh = result["fresh"]["mean"]
    ic_uncond = result["unconditional"]["mean"]
    approved = (ic_fresh or 0) > (ic_uncond or 0)
    uplift = (ic_fresh or 0) - (ic_uncond or 0)

    def _f4(v: Optional[float]) -> str:
        return f"{v:.4f}" if v is not None else "N/A"

    def _f2(v: Optional[float]) -> str:
        return f"{v:.2f}" if v is not None else "N/A"

    verdict = "APPROVED" if approved else "REJECTED"
    reason = (
        "fresh IC exceeds unconditional IC — gate has predictive utility"
        if approved
        else "fresh IC does not exceed unconditional IC — gate does not add value"
    )

    lines = [
        f"# C3 Modifier Screen — {proxy_id}\n",
        f"**Run:** {run_ts}  ",
        f"**Period:** Oct 2024 – Jan 2025 (trending period)  ",
        f"**Hold horizon:** {HOLD_HOURS}h | Top-N: {TOP_N} | Equal weight\n",
        f"## Proxy Definition\n",
        f"**Formula:** {meta.get('description', '')}  ",
        f"**Thresholds:** {meta.get('threshold', '')}  ",
        f"**Prior status:** {meta.get('prior', 'Untested')}\n",
        f"## Economic Rationale\n",
        f"{meta.get('theory', '')}\n",
        f"## IC Screen Results\n",
        f"Gate criterion: IC(fresh) > IC(unconditional) at {HOLD_HOURS}h horizon.\n",
        f"| Bucket | Mean IC | t-stat | N |",
        f"|--------|---------|--------|---|",
        f"| Fresh (below threshold) | {_f4(ic_fresh)} | {_f2(result['fresh'].get('t'))} | {result['fresh']['n']} |",
        f"| Stale (above threshold) | {_f4(result['stale']['mean'])} | {_f2(result['stale'].get('t'))} | {result['stale']['n']} |",
        f"| Unconditional | {_f4(ic_uncond)} | {_f2(result['unconditional'].get('t'))} | {result['unconditional']['n']} |\n",
        f"IC uplift (fresh − unconditional): {uplift:+.4f}\n",
        f"## Verdict\n",
        f"**{verdict}** — {reason}.\n",
    ]
    return "\n".join(lines)


# ── Chart generators ───────────────────────────────────────────────────────────

def generate_c2_chart(
    c2_results: List[Tuple[str, dict, dict]],  # (proxy_id, bare, gated)
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  [WARN] matplotlib not available — skipping C2 chart")
        return

    proxy_ids = [r[0] for r in c2_results]
    bare_dds  = [abs(r[1].get("max_dd", 0) or 0) * 100 for r in c2_results]
    gated_dds = [abs(r[2].get("max_dd", 0) or 0) * 100 for r in c2_results]
    bare_wp   = [abs(r[1].get("worst_30d", 0) or 0) * 100 for r in c2_results]
    gated_wp  = [abs(r[2].get("worst_30d", 0) or 0) * 100 for r in c2_results]

    x    = np.arange(len(proxy_ids))
    w    = 0.20
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.bar(x - w / 2, bare_dds,  width=w, label="Bare C1",     color="#e74c3c", alpha=0.8)
    ax.bar(x + w / 2, gated_dds, width=w, label="+ Gate",      color="#2ecc71", alpha=0.8)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("HAZ_", "") for p in proxy_ids], rotation=30, ha="right")
    ax.set_ylabel("Max Drawdown (%)")
    ax.set_title("C2 Max Drawdown: Bare vs Gated")
    ax.legend()

    ax2 = axes[1]
    ax2.bar(x - w / 2, bare_wp,  width=w, label="Bare C1", color="#e74c3c", alpha=0.8)
    ax2.bar(x + w / 2, gated_wp, width=w, label="+ Gate",  color="#2ecc71", alpha=0.8)
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels([p.replace("HAZ_", "") for p in proxy_ids], rotation=30, ha="right")
    ax2.set_ylabel("Worst 30d DD (%)")
    ax2.set_title("C2 Worst 30d DD: Bare vs Gated")
    ax2.legend()

    plt.tight_layout()
    out = os.path.join(CHARTS_DIR, "c2_modifier_comparison.png")
    plt.savefig(out, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  [chart] Saved {out}")


def generate_c3_chart(
    c3_results: List[Tuple[str, dict]],  # (proxy_id, ic_result)
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  [WARN] matplotlib not available — skipping C3 chart")
        return

    proxy_ids = [r[0] for r in c3_results]
    ic_fresh  = [r[1]["fresh"]["mean"] or 0.0 for r in c3_results]
    ic_uncond = [r[1]["unconditional"]["mean"] or 0.0 for r in c3_results]

    x = np.arange(len(proxy_ids))
    w = 0.30
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - w / 2, ic_uncond, width=w, label="Unconditional IC", color="#3498db", alpha=0.8)
    ax.bar(x + w / 2, ic_fresh,  width=w, label="Fresh-only IC",    color="#f39c12", alpha=0.8)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace("MAT_", "") for p in proxy_ids], rotation=30, ha="right")
    ax.set_ylabel("Mean Spearman IC")
    ax.set_title(f"C3 IC Lift: Fresh vs Unconditional (hold = {HOLD_HOURS}h)")
    ax.legend()
    plt.tight_layout()
    out = os.path.join(CHARTS_DIR, "c3_ic_lift.png")
    plt.savefig(out, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  [chart] Saved {out}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("modifier_screen.py — C2 Hazard + C3 Maturity individual screens")
    print("=" * 70)

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── 1. Load data ──────────────────────────────────────────────────────────
    print("\n[1/4] Loading kline data ...")
    pairs = fetch_roostoo_pairs()
    months = _month_range(TRENDING_START, TRENDING_END)
    print(f"  Universe: {len(pairs)} pairs | {months[0]} → {months[-1]}")

    all_prices, volumes, _, _, _, _, high, low = load_klines_all_parallel(pairs, months)

    # Build sorted 1h timestamp grid
    ts_set: set = set()
    for p_dict in all_prices.values():
        ts_set.update(p_dict.keys())
    timestamps = sorted(ts_set)
    print(f"  {len(timestamps)} hourly timestamps loaded")

    active_pairs = [p for p in pairs if len(all_prices.get(p, {})) >= 200]
    print(f"  {len(active_pairs)} active pairs (≥ 200 hours data)")

    # ── 2. Fetch F&G history ──────────────────────────────────────────────────
    print("\n[2/4] Fetching Fear & Greed history ...")
    fng_history = fetch_fng_history()

    # ── 3. C2 screens ─────────────────────────────────────────────────────────
    print("\n[3/4] Running C2 hazard modifier screens ...")
    c2_proxy_ids = [
        "HAZ_BTC_VOL_Z",
        "HAZ_CS_DISPERSION",
        "HAZ_SPREAD_Z",
        "HAZ_FNG_EXTREME",
        "HAZ_MPI_CHOP",
        "HAZ_BTC_DRAWDOWN",
    ]

    c2_results: List[Tuple[str, dict, dict]] = []

    for proxy_id in c2_proxy_ids:
        if proxy_id == "HAZ_FNG_EXTREME" and not fng_history:
            print(f"  [{proxy_id}] Skipping — no F&G data")
            bare_dummy = {"label": "bare", "n_periods": 0}
            gated_dummy = {"label": proxy_id, "n_periods": 0}
            c2_results.append((proxy_id, bare_dummy, gated_dummy))
        else:
            print(f"  [{proxy_id}] Running ...", end=" ", flush=True)
            bare, gated = run_c2_backtest(
                proxy_id, all_prices, high, low, volumes,
                active_pairs, timestamps, fng_history,
            )
            c2_results.append((proxy_id, bare, gated))
            bare_dd = bare.get("max_dd", 0) or 0
            gated_dd = gated.get("max_dd", 0) or 0
            dd_improv = (gated_dd - bare_dd) / abs(bare_dd) if bare_dd != 0 else 0.0
            wp_improv = (gated.get("worst_30d", 0) or 0) - (bare.get("worst_30d", 0) or 0)
            verdict = "APPROVED" if (dd_improv >= 0.10 and wp_improv >= 0.05) else "REJECTED"
            print(f"MaxDD improv={dd_improv:+.1%} worst30d improv={wp_improv:+.2%} → {verdict}")

        # Write per-proxy markdown
        proxy_dir = os.path.join(C2_BASE_DIR, proxy_id)
        os.makedirs(proxy_dir, exist_ok=True)
        md_path = os.path.join(proxy_dir, "02_modifier_screen.md")
        bare_s  = c2_results[-1][1]
        gated_s = c2_results[-1][2]
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(write_c2_markdown(proxy_id, bare_s, gated_s, run_ts))
        print(f"    → {md_path}")

    # ── 4. C3 screens ─────────────────────────────────────────────────────────
    print("\n[4/4] Running C3 maturity IC screens ...")
    c3_proxy_ids = [
        "MAT_PCT_RANK",
        "MAT_SMA_EXT",
        "MAT_RSI_PROXY",
        "MAT_FUNDING_RATE",
        "MAT_TS_ZSCORE_R6H",
        "MAT_VOL_RATIO",
        "MAT_CONSEC_UP",
    ]

    c3_results: List[Tuple[str, dict]] = []

    for proxy_id in c3_proxy_ids:
        print(f"  [{proxy_id}] Running ...", end=" ", flush=True)
        result = run_c3_ic_screen(
            proxy_id, all_prices, volumes, active_pairs, timestamps
        )
        c3_results.append((proxy_id, result))

        ic_f = result["fresh"]["mean"]
        ic_u = result["unconditional"]["mean"]
        verdict = "APPROVED" if (ic_f or 0) > (ic_u or 0) else "REJECTED"
        uplift  = (ic_f or 0) - (ic_u or 0)
        ic_f_str = f"{ic_f:.4f}" if ic_f is not None else "N/A"
        ic_u_str = f"{ic_u:.4f}" if ic_u is not None else "N/A"
        print(f"IC_fresh={ic_f_str} IC_uncond={ic_u_str} uplift={uplift:+.4f} → {verdict}")

        # Write per-proxy markdown
        proxy_dir = os.path.join(C3_BASE_DIR, proxy_id)
        os.makedirs(proxy_dir, exist_ok=True)
        md_path = os.path.join(proxy_dir, "02_modifier_screen.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(write_c3_markdown(proxy_id, result, run_ts))
        print(f"    → {md_path}")

    # ── 5. Charts ─────────────────────────────────────────────────────────────
    print("\nGenerating charts ...")
    generate_c2_chart(c2_results)
    generate_c3_chart(c3_results)

    # ── 6. Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("C2 SUMMARY")
    print("-" * 70)
    print(f"{'Proxy':<24} {'MaxDD bare':>10} {'MaxDD gated':>12} {'DD improv':>10} {'WP improv':>10} {'Verdict'}")
    for proxy_id, bare, gated in c2_results:
        bare_dd  = bare.get("max_dd", 0) or 0
        gated_dd = gated.get("max_dd", 0) or 0
        bare_wp  = bare.get("worst_30d", 0) or 0
        gated_wp = gated.get("worst_30d", 0) or 0
        if bare.get("n_periods", 0) < 2:
            print(f"  {proxy_id:<22} {'N/A':>10} {'N/A':>12} {'N/A':>10} {'N/A':>10}   N/A")
            continue
        dd_imp = (gated_dd - bare_dd) / abs(bare_dd) if bare_dd != 0 else 0.0
        wp_imp = gated_wp - bare_wp
        ok     = "APPROVED" if dd_imp >= 0.10 and wp_imp >= 0.05 else "REJECTED"
        print(f"  {proxy_id:<22} {bare_dd*100:>9.1f}% {gated_dd*100:>11.1f}% {dd_imp*100:>+9.1f}% {wp_imp*100:>+9.1f}pp   {ok}")

    print("\nC3 SUMMARY")
    print("-" * 70)
    print(f"{'Proxy':<24} {'IC uncond':>10} {'IC fresh':>10} {'Uplift':>8} {'Verdict'}")
    for proxy_id, result in c3_results:
        ic_u = result["unconditional"]["mean"]
        ic_f = result["fresh"]["mean"]
        uplift = (ic_f or 0) - (ic_u or 0)
        ok = "APPROVED" if uplift > 0 else "REJECTED"
        ic_u_s = f"{ic_u:.4f}" if ic_u is not None else "N/A"
        ic_f_s = f"{ic_f:.4f}" if ic_f is not None else "N/A"
        print(f"  {proxy_id:<22} {ic_u_s:>10} {ic_f_s:>10} {uplift:>+8.4f}   {ok}")

    print("\nDone.")


if __name__ == "__main__":
    main()
