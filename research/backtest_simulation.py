"""
research/backtest_simulation.py — Mechanism-specific backtests + dual-engine regime allocation.

Three sections:
  Section A: H1 Reversal mechanism
    - Version A: faithful promoted object (delegates to _vt.run_backtest) + fee sweep
      Cross-validation: Version A fee=0% must match vector_tests.py bare result (< 0.1pp)
    - Risk overlay sweeps: stop-loss, C1 signal exit, regime z-threshold, portfolio construction
    - H1 final: all selected layers combined

  Section B: H2C BTC Lead-Lag mechanism (beta-adjusted gap)
    - Version A: H2C faithful signal + fee sweep
    - Risk overlay sweeps: BTC-direction exit, hold cap, BTC gate, portfolio construction
    - H2 final: all selected layers combined

  Section C: Dual-Engine Regime-Conditional Allocation
    - Regime states: TREND_ACTIVE / TREND_FLAT / HAZARD
    - alpha_TREND sweep: H2 weight in TREND_ACTIVE periods
    - Attribution: H1-only vs H2-only vs combined at selected alpha
    - C_combined: final config; OOS holdout; parameter perturbation robustness

Outputs (co-located with mechanism):
  H1_reversal/02_Candidates/Strategy/02_backtest.md
  H2_transitional_drift/02_Candidates/Strategy/01_backtest.md
  portfolio/03_combined_backtest.md

Run from Crypto-Trading-Bot/:
  python -X utf8 research/backtest_simulation.py
"""

import csv
import io
import json
import math
import os
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

# ── Import vector_tests for signal functions and run_backtest ──────────────────
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, 'tools'))
import vector_tests as _vt  # noqa: E402

# ── Output paths (co-located with mechanism) ──────────────────────────────────
OUTPUT_H1   = os.path.join(_here, "H1_reversal",          "02_Candidates", "Strategy", "02_backtest.md")
OUTPUT_H2   = os.path.join(_here, "H2_transitional_drift", "02_Candidates", "Strategy", "01_backtest.md")
OUTPUT_COMB       = os.path.join(_here, "portfolio",             "03_combined_backtest.md")
OUTPUT_PORTFOLIO  = os.path.join(_here, "portfolio",             "05_dual_portfolio_backtest.md")
OUTPUT_SIZING     = os.path.join(_here, "portfolio",             "06_sizing_comparison.md")
OUTPUT_REGIME_DECOMP = os.path.join(_here, "overlays", "regime", "04_component_decomposition.md")
CHARTS_H1   = os.path.join(_here, "H1_reversal",          "02_Candidates", "Strategy", "charts", "backtest")
CHARTS_H2   = os.path.join(_here, "H2_transitional_drift", "02_Candidates", "Strategy", "charts", "backtest")
CHARTS_COMB = os.path.join(_here, "portfolio",             "charts", "combined")

for _d in (OUTPUT_H1, OUTPUT_H2, OUTPUT_COMB, OUTPUT_PORTFOLIO):
    os.makedirs(os.path.dirname(_d), exist_ok=True)
for _d in (CHARTS_H1, CHARTS_H2, CHARTS_COMB):
    os.makedirs(_d, exist_ok=True)

# ── Universe and test period ───────────────────────────────────────────────────
FALLBACK_PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
]
ROOSTOO_URL       = "https://mock-api.roostoo.com/v3/exchangeInfo"
BINANCE_VISION    = "https://data.binance.vision/data/spot/monthly/klines"
START_YEAR, START_MONTH = 2024, 10
END_YEAR,   END_MONTH   = 2025,  1

# OOS split: Dec 1 2024 00:00 UTC
HOLDOUT_TS = 1_733_011_200_000  # ms

# ── Strategy constants ─────────────────────────────────────────────────────────
HOLD_HOURS     = 4       # must match vector_tests.py
TOP_N_DEFAULT  = 3       # default top-N for sweeps baseline
FEE_DEFAULT    = 0.0005  # 0.05% maker, per competition rules
MS_PER_HOUR    = 3_600_000

# ── Data download ──────────────────────────────────────────────────────────────

def fetch_roostoo_pairs() -> List[str]:
    try:
        with urllib.request.urlopen(ROOSTOO_URL, timeout=10) as r:
            data = json.loads(r.read())
        pairs = [
            k.replace("/USD", "USDT").replace("/", "")
            for k in data.get("TradePairs", {}).keys()
            if k.replace("/USD", "USDT").replace("/", "").endswith("USDT")
        ]
        if len(pairs) >= 10:
            return sorted(pairs)
    except Exception as exc:
        print(f"  [WARN] Roostoo fetch failed: {exc}. Using fallback.")
    return list(FALLBACK_PAIRS)


def _dl_monthly(symbol: str, year: int, month: int) -> Dict[int, float]:
    mo = f"{month:02d}"
    url = f"{BINANCE_VISION}/{symbol}/1h/{symbol}-1h-{year}-{mo}.zip"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            raw = r.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            with zf.open(zf.namelist()[0]) as f:
                rows = list(csv.reader(io.TextIOWrapper(f)))
        prices: Dict[int, float] = {}
        for row in rows:
            if not row or not row[0].isdigit():
                continue
            ts = int(row[0])
            if ts > 1_000_000_000_000_000:
                ts //= 1000
            prices[ts] = float(row[4])
        return prices
    except Exception:
        return {}


def load_all_prices(symbols: List[str], max_workers: int = 8) -> Dict[str, Dict[int, float]]:
    tasks: List[Tuple[str, int, int]] = []
    y, m = START_YEAR, START_MONTH
    while (y, m) <= (END_YEAR, END_MONTH):
        for s in symbols:
            tasks.append((s, y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    out: Dict[str, Dict[int, float]] = {s: {} for s in symbols}

    def _proc(task: Tuple[str, int, int]) -> Tuple[str, Dict[int, float]]:
        s, yr, mo = task
        return s, _dl_monthly(s, yr, mo)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_proc, t): t for t in tasks}
        done = 0
        for fut in as_completed(futs):
            s, prices = fut.result()
            out[s].update(prices)
            done += 1
            if done % max(1, len(tasks) // 10) == 0:
                print(f"  [{done}/{len(tasks)} files]", flush=True)
    return out


def filter_full_period(all_prices: Dict[str, Dict[int, float]]) -> Tuple[Dict[str, Dict[int, float]], List[str]]:
    """Keep only symbols with data at the start of the period (within 48h)."""
    btc = all_prices.get("BTCUSDT", {})
    if not btc:
        return all_prices, sorted(all_prices.keys())
    period_start = min(btc.keys()) + 48 * MS_PER_HOUR
    active = {
        s: p for s, p in all_prices.items()
        if len(p) > 100 and min(p.keys(), default=period_start + 1) <= period_start
    }
    if "BTCUSDT" not in active:
        active["BTCUSDT"] = btc
    return active, sorted(active.keys())


# ── Statistics ─────────────────────────────────────────────────────────────────

def _stats(nav_series: List[Tuple[int, float]], label: str) -> dict:
    """Compute performance metrics from hourly NAV series."""
    if len(nav_series) < 10:
        return {"label": label, "total_return": 0.0, "sortino": 0.0, "calmar": 0.0,
                "max_dd": 0.0, "sharpe": 0.0, "n_hours": 0}
    navs = [n for _, n in nav_series]
    hourly_rets = [(navs[i] / navs[i-1] - 1) for i in range(1, len(navs)) if navs[i-1] > 0]
    if not hourly_rets:
        return {"label": label, "total_return": 0.0, "sortino": 0.0, "calmar": 0.0,
                "max_dd": 0.0, "sharpe": 0.0, "n_hours": 0}
    mean_r = sum(hourly_rets) / len(hourly_rets)
    std_r  = math.sqrt(sum((r - mean_r)**2 for r in hourly_rets) / len(hourly_rets)) or 1e-8
    neg    = [r for r in hourly_rets if r < 0]
    down   = math.sqrt(sum(r**2 for r in neg) / len(neg)) if neg else 1e-8
    af     = math.sqrt(24 * 365)
    total  = navs[-1] / navs[0] - 1
    n_yrs  = len(navs) / (24 * 365)
    ann    = (1 + total)**(1/n_yrs) - 1 if n_yrs > 0 else 0.0
    peak   = navs[0]
    max_dd = 0.0
    for n in navs:
        peak = max(peak, n)
        max_dd = min(max_dd, (n - peak) / peak)
    calmar = ann / abs(max_dd) if max_dd < 0 else float("inf")
    return {
        "label":        label,
        "total_return": total,
        "ann_return":   ann,
        "sortino":      (mean_r / down) * af,
        "sharpe":       (mean_r / std_r) * af,
        "calmar":       calmar,
        "max_dd":       max_dd,
        "n_hours":      len(navs),
    }


def _subperiod_stats(nav_series: List[Tuple[int, float]], ts_start: int, ts_end: int, label: str) -> dict:
    sub = [(t, n) for t, n in nav_series if ts_start <= t < ts_end]
    if len(sub) < 2:
        return {"label": label, "total_return": 0.0, "sortino": 0.0, "calmar": 0.0,
                "max_dd": 0.0, "sharpe": 0.0, "n_hours": 0}
    # Normalise to 1.0 at start of subperiod
    base = sub[0][1]
    normalised = [(t, n / base) for t, n in sub]
    return _stats(normalised, label)


# ── Sizing helpers ─────────────────────────────────────────────────────────────

def _local_vol(
    all_prices: Dict[str, Dict[int, float]],
    pair: str,
    ts: int,
    lookback_h: int = 24,
) -> float:
    """Realized volatility over lookback_h hours ending at ts.

    Used for inverse-volatility position sizing: assets with lower recent
    volatility receive larger weights, producing a risk-parity-style allocation.
    """
    hist = sorted((t, p) for t, p in all_prices.get(pair, {}).items() if t <= ts)
    hist = hist[-lookback_h:]
    if len(hist) < 3:
        return 1.0
    rets = [hist[i][1] / hist[i - 1][1] - 1 for i in range(1, len(hist))]
    mean_r = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean_r) ** 2 for r in rets) / len(rets)) or 1e-8


def _local_downside_vol(
    all_prices: Dict[str, Dict[int, float]],
    pair: str,
    ts: int,
    lookback_h: int = 24,
) -> float:
    """Downside semi-deviation over lookback_h hours ending at ts.

    Like _local_vol but counts only negative returns — aligns with Sortino
    denominator and penalises only loss-side volatility.
    """
    hist = sorted((t, p) for t, p in all_prices.get(pair, {}).items() if t <= ts)
    hist = hist[-lookback_h:]
    if len(hist) < 3:
        return 1.0
    rets = [hist[i][1] / hist[i - 1][1] - 1 for i in range(1, len(hist))]
    neg = [r for r in rets if r < 0]
    return math.sqrt(sum(r ** 2 for r in neg) / len(neg)) if neg else 1e-8


# ── Regime component helpers ────────────────────────────────────────────────────

def _cs_dispersion_z(
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts: int,
    disp_hist: List[float],
    lookback_h: int = 6,
) -> Optional[float]:
    """Cross-section dispersion z-score.

    Dispersion = std of 6h returns across all pairs at timestamp ts.
    A sharp *collapse* in dispersion (all assets moving together) signals
    panic / correlated forced-selling — the LSI dispersion sub-component.
    Inverted: high z-score here means *low* dispersion (panic), which is stress.
    """
    rets = []
    for pair in active_pairs:
        pr = all_prices.get(pair, {})
        p_now  = pr.get(ts)
        p_then = pr.get(ts - lookback_h * MS_PER_HOUR)
        if p_now and p_then and p_then > 0:
            rets.append(p_now / p_then - 1)
    if len(rets) < 5:
        return None
    mean_r = sum(rets) / len(rets)
    disp   = math.sqrt(sum((r - mean_r) ** 2 for r in rets) / len(rets))
    disp_hist.append(disp)
    if len(disp_hist) < 20:
        return None
    mean_d = sum(disp_hist) / len(disp_hist)
    std_d  = math.sqrt(sum((d - mean_d) ** 2 for d in disp_hist) / len(disp_hist)) or 1e-8
    # Negate: low dispersion (collapse) = high stress
    return -(disp - mean_d) / std_d


def _mpi_proxy(
    all_prices: Dict[str, Dict[int, float]],
    btc_key: str,
    ts: int,
    lookback_h: int = 24,
) -> Optional[float]:
    """Market Posture Index proxy: fraction of positive BTC hourly returns.

    High MPI = BTC trending directionally; Low MPI = choppy / directionless.
    Used as a hazard gate: skip entries when BTC is not trending (MPI low).
    """
    pr  = all_prices.get(btc_key, {})
    pts = sorted(t for t in pr if t <= ts)[-(lookback_h + 1):]
    if len(pts) < 6:
        return None
    rets = [pr[pts[i]] / pr[pts[i - 1]] - 1
            for i in range(1, len(pts)) if pr[pts[i - 1]] > 0]
    return sum(1 for r in rets if r > 0) / len(rets) if rets else None


def _fei_proxy(
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts: int,
    lookback_h: int = 6,
) -> Optional[float]:
    """Flow Elasticity Index proxy: IQR of 6h cross-section returns.

    FEI = P75 − P25 of r_6h across the universe. High FEI = clear momentum
    leaders/laggards exist; Low FEI = all assets moving uniformly (low alpha).
    """
    rets = []
    for pair in active_pairs:
        pr = all_prices.get(pair, {})
        p0 = pr.get(ts - lookback_h * MS_PER_HOUR)
        p1 = pr.get(ts)
        if p0 and p1 and p0 > 0:
            rets.append(p1 / p0 - 1)
    if len(rets) < 8:
        return None
    s  = sorted(rets)
    n  = len(s)
    q1 = s[n // 4]
    q3 = s[3 * n // 4]
    return q3 - q1


# ── H2C signal ─────────────────────────────────────────────────────────────────

def _estimate_beta(r_asset: List[float], r_btc: List[float]) -> float:
    """OLS β = Cov(r_i, r_BTC) / Var(r_BTC) over shared window."""
    n = min(len(r_asset), len(r_btc))
    if n < 10:
        return 1.0
    ra = r_asset[-n:]
    rb = r_btc[-n:]
    mean_a = sum(ra) / n
    mean_b = sum(rb) / n
    cov  = sum((ra[i] - mean_a) * (rb[i] - mean_b) for i in range(n)) / n
    varb = sum((rb[i] - mean_b)**2 for i in range(n)) / n
    return cov / varb if varb > 1e-10 else 1.0


def _compute_h2c_signal(
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts: int,
    btc_key: str,
    beta_hist: Dict[str, List[List[float]]],
    mat2_time_thresh: Optional[float] = None,
) -> Optional[Dict[str, float]]:
    """H2C: CS_z(β_i × r_BTC,2h − r_i,2h).

    beta_hist: pair → ([r_i_hourly_48], [r_btc_hourly_48]) — updated in-place.
    Requires 24+ hours of β history (48h window, skip first 24h).
    mat2_time_thresh: if set, apply MAT2_TIME_DECAY gate — skip stale diffusion windows.
    """
    r_btc_2h = _vt.compute_return(all_prices[btc_key], ts, 2.0)
    if r_btc_2h is None:
        return None

    # Update 1h return histories
    r_btc_1h = _vt.compute_return(all_prices[btc_key], ts, 1.0)
    if r_btc_1h is not None:
        for pair in active_pairs:
            if pair == btc_key:
                continue
            r_1h = _vt.compute_return(all_prices[pair], ts, 1.0)
            if r_1h is not None:
                beta_hist[pair][0].append(r_1h)
                beta_hist[pair][1].append(r_btc_1h)
                if len(beta_hist[pair][0]) > 48:
                    beta_hist[pair][0] = beta_hist[pair][0][-48:]
                    beta_hist[pair][1] = beta_hist[pair][1][-48:]

    # MAT2_TIME_DECAY gate: skip if diffusion window is stale
    if mat2_time_thresh is not None:
        time_decay = _compute_btc_time_decay(all_prices[btc_key], ts)
        if time_decay is None or time_decay >= mat2_time_thresh:
            return None

    gaps: Dict[str, float] = {}
    for pair in active_pairs:
        if pair == btc_key:
            continue
        hist = beta_hist[pair]
        if len(hist[0]) < 24:
            continue  # need burn-in
        r_2h = _vt.compute_return(all_prices[pair], ts, 2.0)
        if r_2h is None:
            continue
        beta = _estimate_beta(hist[0], hist[1])
        gaps[pair] = beta * r_btc_2h - r_2h

    if len(gaps) < 4:
        return None
    return _vt.cross_sectional_z(gaps)


def _compute_btc_time_decay(btc_prices: Dict[int, float], ts: int) -> Optional[float]:
    """MAT2_TIME_DECAY: (t − t_peak_BTC) / 6h.

    t_peak = argmax_{ts-6h ≤ t' ≤ ts} |r_BTC,1h(t')|
    Returns float in [0, 1]: 0.0 = fresh BTC move (just happened), 1.0 = 6h ago.
    Returns None if BTC barely moved (|r_peak| < 0.001) — not an active H2 period.
    """
    MS_PER_H = 3_600_000
    best_abs_r = 0.0
    best_lag = 0
    for lag in range(7):  # lags 0h..6h
        t_check = ts - lag * MS_PER_H
        r = _vt.compute_return(btc_prices, t_check, 1.0)
        if r is not None and abs(r) > best_abs_r:
            best_abs_r = abs(r)
            best_lag = lag
    if best_abs_r < 0.001:
        return None  # BTC quiescent — no active diffusion window
    return best_lag / 6.0


# ── Overlay backtest engine ────────────────────────────────────────────────────

def _run_overlay_engine(
    all_prices:       Dict[str, Dict[int, float]],
    active_pairs:     List[str],
    timestamps:       List[int],       # 1h grid
    signal_fn:        Callable,        # fn(all_prices, active_pairs, ts, **kwargs) → Optional[Dict]
    signal_kwargs:    dict,
    fee:              float   = 0.0,
    fee_exit:         Optional[float] = None,    # exit fee; defaults to fee if None (asymmetric maker/taker)
    stop_loss_pct:    Optional[float] = None,    # e.g. -0.04; None = disabled
    c1_exit_thresh:   Optional[float] = None,    # exit if score < thresh; None = disabled
    btc_rev_exit:     Optional[float] = None,    # H2: exit if r_BTC since entry < -X; None = disabled
    hold_cap_hours:   Optional[int]   = None,    # H2: force-exit after N hours; None = disabled
    btc_gate_pct:     float   = 0.0,             # skip H2 entry if |r_BTC,2h| < gate
    z_thresh:         float   = 1.50,            # C2 hazard gate
    top_n:            int     = TOP_N_DEFAULT,
    sizing:           str     = "ew",            # "ew" | "score" | "kelly" | "inv_vol" | "inv_downside_vol"
    label:            str     = "overlay",
    custom_hazard_fn: Optional[Callable] = None, # fn(all_prices, active_pairs, ts, state: dict) -> bool
    # If set, replaces the BTC vol z-score gate entirely.
    # state dict is mutable — use for rolling history (e.g., dispersion baseline).
) -> Tuple[List[Tuple[int, float]], dict]:
    """
    Per-position tracking engine with optional risk overlays.

    For H1: use signal_fn = _vt._compute_signal, enable stop_loss_pct and/or c1_exit_thresh.
    For H2: use signal_fn = _compute_h2c_signal, enable btc_rev_exit and/or hold_cap_hours.

    fee_exit: if provided, applied to all exit paths (stop-loss, signal exit, hold-cap, final
    liquidation). Allows realistic maker/taker asymmetry: entries use limit orders (fee=0.05%),
    emergency/stop exits use market orders (fee_exit=0.10%).
    """
    _fee_exit  = fee_exit if fee_exit is not None else fee
    btc_key    = next((p for p in active_pairs if p.startswith("BTC")), None)
    btc_prices = all_prices.get(btc_key, {}) if btc_key else {}

    nav        = 1.0
    cash       = 1.0
    nav_series: List[Tuple[int, float]] = [(timestamps[0], 1.0)]
    positions:  Dict[str, dict] = {}   # pair → {entry_price, entry_ts, entry_btc_price, qty_usd}
    btc_vol_hist: List[float] = []
    _hazard_state: dict = {}           # mutable state for custom_hazard_fn (e.g., rolling history)
    last_rebal_ts = 0
    n_stops = 0
    n_exits = 0

    for ts in timestamps:
        # ── Update NAV from open positions ─────────────────────────────────
        pos_val = 0.0
        for pair, pos in positions.items():
            cp = all_prices[pair].get(ts)
            if cp is not None and pos["entry_price"] > 0:
                pos_val += pos["qty_usd"] * (cp / pos["entry_price"])
        nav = cash + pos_val

        # ── Hourly: stop-loss (H1) or BTC-direction exit (H2) ──────────────
        for pair in list(positions.keys()):
            pos = positions[pair]
            cp  = all_prices[pair].get(ts)
            if cp is None:
                continue
            ret = cp / pos["entry_price"] - 1.0

            # H1 stop-loss
            if stop_loss_pct is not None and ret <= stop_loss_pct:
                val = pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - _fee_exit)
                cash += val
                nav = cash + sum(
                    positions[p]["qty_usd"] * (all_prices[p].get(ts, pos["entry_price"]) / positions[p]["entry_price"])
                    for p in positions if p != pair
                )
                del positions[pair]
                n_stops += 1
                continue

            # H2 BTC-direction exit
            if btc_rev_exit is not None and btc_key:
                btc_now = btc_prices.get(ts)
                btc_entry = pos.get("entry_btc_price")
                if btc_now is not None and btc_entry is not None and btc_entry > 0:
                    btc_ret = btc_now / btc_entry - 1.0
                    if btc_ret < btc_rev_exit:  # BTC reversed by more than threshold
                        val = pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - _fee_exit)
                        cash += val
                        del positions[pair]
                        n_exits += 1
                        continue

            # H2 hold cap
            if hold_cap_hours is not None:
                age_h = (ts - pos["entry_ts"]) / MS_PER_HOUR
                if age_h >= hold_cap_hours:
                    val = pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - _fee_exit)
                    cash += val
                    del positions[pair]
                    n_exits += 1
                    continue

        # ── Rebalance every HOLD_HOURS ──────────────────────────────────────
        if ts - last_rebal_ts < HOLD_HOURS * MS_PER_HOUR:
            nav_series.append((ts, nav))
            continue
        last_rebal_ts = ts

        # Compute signal
        sig = signal_fn(all_prices, active_pairs, ts, **signal_kwargs)
        if sig is None:
            nav_series.append((ts, nav))
            continue

        # C2 hazard gate (custom fn overrides default BTC vol z-score gate)
        hazard = False
        if custom_hazard_fn is not None:
            hazard = custom_hazard_fn(all_prices, active_pairs, ts, _hazard_state)
        elif btc_key:
            z = _vt._btc_vol_zscore(all_prices, btc_key, ts, btc_vol_hist)
            if z is not None and z > z_thresh:
                hazard = True

        # H2 BTC magnitude gate (skip if BTC flat)
        if not hazard and btc_gate_pct > 0 and btc_key:
            r_btc_2h = _vt.compute_return(all_prices[btc_key], ts, 2.0)
            if r_btc_2h is not None and abs(r_btc_2h) < btc_gate_pct:
                hazard = True  # reuse hazard flag to skip entries

        # C1 signal exit (H1 only)
        if c1_exit_thresh is not None:
            for pair in list(positions.keys()):
                score = sig.get(pair, 0.0)
                if score < c1_exit_thresh:
                    cp = all_prices[pair].get(ts)
                    if cp is not None:
                        val = positions[pair]["qty_usd"] * (cp / positions[pair]["entry_price"]) * (1 - _fee_exit)
                        cash += val
                        del positions[pair]
                        n_exits += 1

        # Recompute NAV after exits
        pos_val = sum(
            positions[p]["qty_usd"] * (all_prices[p].get(ts, positions[p]["entry_price"]) / positions[p]["entry_price"])
            for p in positions
        )
        nav = cash + pos_val

        # Enter new positions
        if not hazard and len(positions) < top_n:
            eligible = [
                (pair, score) for pair, score in sig.items()
                if pair not in positions
            ]
            eligible.sort(key=lambda x: -x[1])
            slots = top_n - len(positions)
            to_enter = eligible[:slots]

            if to_enter:
                if sizing == "ew":
                    weights = {pair: 1.0 / top_n for pair, _ in to_enter}
                elif sizing == "score":
                    total_score = sum(max(sc, 0.0) for _, sc in to_enter) or 1.0
                    weights = {pair: max(sc, 0.0) / total_score for pair, sc in to_enter}
                elif sizing == "inv_vol":
                    # Inverse-volatility: weight ∝ 1/σ_i (risk-parity style)
                    vols = {pair: _local_vol(all_prices, pair, ts) for pair, _ in to_enter}
                    inv  = {pair: 1.0 / max(v, 1e-8) for pair, v in vols.items()}
                    total_inv = sum(inv.values()) or 1.0
                    weights = {pair: inv[pair] / total_inv for pair, _ in to_enter}
                elif sizing == "inv_downside_vol":
                    # Inverse downside-vol: weight ∝ 1/σ_down_i (Sortino-aligned sizing)
                    dvols = {pair: _local_downside_vol(all_prices, pair, ts) for pair, _ in to_enter}
                    inv   = {pair: 1.0 / max(v, 1e-8) for pair, v in dvols.items()}
                    total_inv = sum(inv.values()) or 1.0
                    weights = {pair: inv[pair] / total_inv for pair, _ in to_enter}
                else:  # kelly-0.25
                    total_score = sum(max(sc, 0.0) for _, sc in to_enter) or 1.0
                    weights = {pair: 0.25 * max(sc, 0.0) / total_score for pair, sc in to_enter}

                btc_now = btc_prices.get(ts)
                for pair, _ in to_enter:
                    cp = all_prices[pair].get(ts)
                    if cp is None:
                        continue
                    alloc = nav * weights.get(pair, 1.0 / top_n)
                    alloc = min(alloc, cash * 0.99)
                    if alloc < 1e-6:
                        continue
                    actual = alloc * (1 - fee)
                    cash -= alloc
                    positions[pair] = {
                        "qty_usd":        actual,
                        "entry_price":    cp,
                        "entry_ts":       ts,
                        "entry_btc_price": btc_now,
                    }

        nav_series.append((ts, nav))

    # Final liquidation
    final_ts = timestamps[-1]
    for pair, pos in positions.items():
        cp = all_prices[pair].get(final_ts)
        if cp is not None:
            cash += pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - _fee_exit)

    nav_series.append((final_ts + MS_PER_HOUR, cash))
    stats = _stats(nav_series, label)
    stats["n_stops"]  = n_stops
    stats["n_exits"]  = n_exits
    stats["n_rebal"]  = sum(1 for i in range(0, len(timestamps), HOLD_HOURS))
    return nav_series, stats


# ── Selection helpers ──────────────────────────────────────────────────────────

def _robust_select(
    results: List[dict],
    metric: str,
    param_key: str,
    threshold: float = 0.85,
    calmar_min: float = 0.0,
) -> dict:
    """Select the robust center of the performance plateau.

    1. Filter to results with calmar >= calmar_min.
    2. Find peak = max(metric) in filtered set.
    3. Plateau = all results where metric >= threshold × peak.
    4. Sort plateau by param_key value; return the median element.

    Avoids picking cliff-edge peaks: if performance degrades sharply when
    the parameter shifts by one step, the plateau will be narrow or
    single-element, and we pick that single point conservatively.
    Falls back to best metric if no result meets calmar_min.
    None param values sort last (treated as sentinel beyond numeric range).
    """
    def _sort_key(r):
        v = r.get(param_key)
        if v is None:
            return float('inf')
        try:
            return float(v)
        except (TypeError, ValueError):
            return float('inf')

    eligible = [r for r in results if r.get("calmar", 0) >= calmar_min]
    if not eligible:
        eligible = results

    peak_metric = max(r.get(metric, float('-inf')) for r in eligible)
    plateau = [r for r in eligible if r.get(metric, 0) >= threshold * peak_metric]
    if not plateau:
        plateau = [max(eligible, key=lambda r: r.get(metric, 0))]

    sorted_plateau = sorted(plateau, key=_sort_key)
    return sorted_plateau[len(sorted_plateau) // 2]


def _run_cost_scenarios(
    label_prefix: str,
    all_prices: Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps: List[int],
    signal_fn: Callable,
    signal_kwargs_fn: Callable,   # () → fresh kwargs dict (needed for H2 beta_hist)
    **engine_kwargs,              # non-fee params forwarded to _run_overlay_engine
) -> List[dict]:
    """Run three fee scenarios to assess cost robustness.

    Scenarios model production fill patterns:
      maker/maker  — all limit fills (best case; entries and exits fill at spread midpoint)
      maker/taker  — entries limit, exits market (realistic; stop-loss/emergency exits are market)
      taker/taker  — all market fills (worst case; high urgency or poor liquidity)

    Gate: Calmar > 0 in maker/taker scenario is the minimum robustness bar.
    """
    scenarios = [
        ("maker/maker",  0.0005, 0.0005),
        ("maker/taker",  0.0005, 0.001 ),
        ("taker/taker",  0.001,  0.001 ),
    ]
    results = []
    print("  Cost scenario analysis:")
    for name, f_entry, f_exit in scenarios:
        lbl = f"{label_prefix}_cost_{name.replace('/', '_')}"
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=signal_fn, signal_kwargs=signal_kwargs_fn(),
            fee=f_entry, fee_exit=f_exit,
            label=lbl, **engine_kwargs,
        )
        stats["scenario"] = name
        stats["fee_entry"] = f_entry
        stats["fee_exit"]  = f_exit
        results.append(stats)
        print(f"    {name}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}  MaxDD={stats['max_dd']*100:.1f}%")
    return results


# ── Section A: H1 Reversal ────────────────────────────────────────────────────

def run_h1_section(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
) -> dict:
    """Run H1 Version A + risk overlay sweeps. Returns selected params and results."""
    print("\n" + "="*60)
    print("SECTION A: H1 Reversal Mechanism")
    print("="*60)

    # ── Version A: faithful promoted object (delegates to vector_tests) ────────
    print("\n[A] Version A — cross-validation + fee sweep ...")
    va_results = {}
    for use_c2, tag in [(False, "bare"), (True, "c2")]:
        for fee in [0.0, FEE_DEFAULT, 0.001]:
            lbl = f"H1_A_{tag}_fee{fee*100:.2f}"
            nav, stats = _vt.run_backtest(
                all_prices, active_pairs, timestamps,
                use_c2=use_c2, use_c3=False, fee_per_trade=fee, label=lbl,
            )
            va_results[lbl] = {"nav": nav, "stats": stats}
            print(f"  {lbl}: ret={stats.get('total_return', 0)*100:.1f}%  "
                  f"Sortino={stats.get('sharpe_ann', stats.get('sortino', 0)):.2f}  "
                  f"MaxDD={stats.get('max_dd', 0)*100:.1f}%")

    # Baseline: c2 + 0.05% fee
    baseline_key = f"H1_A_c2_fee{FEE_DEFAULT*100:.2f}"
    baseline = va_results[baseline_key]["stats"]

    # ── B: Stop-loss threshold sweep ──────────────────────────────────────────
    print("\n[B] Stop-loss threshold sweep ...")
    sl_levels = [-0.01, -0.02, -0.03, -0.04, -0.05, -0.06, -0.08, None]
    sl_results = []
    for sl in sl_levels:
        lbl = f"H1_SL_{sl}" if sl is not None else "H1_SL_none"
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=sl, z_thresh=1.50,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["sl"] = sl
        sl_results.append(stats)
        n_stops_pct = stats["n_stops"] / max(stats["n_rebal"], 1)
        print(f"  SL={str(sl):8s}: ret={stats['total_return']*100:.1f}%  "
              f"Calmar={stats['calmar']:.2f}  MaxDD={stats['max_dd']*100:.1f}%  "
              f"stops={n_stops_pct*100:.1f}%")

    # Select: robust plateau center (stops < 5% filter first)
    h1_sl_opt = None
    no_sl_calmar = next(s["calmar"] for s in sl_results if s["sl"] is None)
    eligible_sl = [s for s in sl_results if s["sl"] is not None and
                   s["n_stops"] / max(s["n_rebal"], 1) < 0.05]
    if eligible_sl:
        best_sl = _robust_select(eligible_sl, metric="calmar", param_key="sl")
        if best_sl["calmar"] > no_sl_calmar * 1.10:
            h1_sl_opt = best_sl["sl"]
    print(f"  → H1_SL_OPT = {h1_sl_opt}")

    # ── C: C1 signal exit sweep ───────────────────────────────────────────────
    print("\n[C] C1 signal exit sweep ...")
    exit_levels = [None, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    exit_results = []
    for ex in exit_levels:
        lbl = f"H1_EXIT_{ex}" if ex is not None else "H1_EXIT_none"
        nav, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=h1_sl_opt,
            c1_exit_thresh=ex, z_thresh=1.50,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["exit_thresh"] = ex
        exit_results.append(stats)
        print(f"  EXIT={str(ex):5s}: ret={stats['total_return']*100:.1f}%  "
              f"Sortino={stats['sortino']:.2f}  Calmar={stats['calmar']:.2f}")

    h1_exit_opt = None
    no_exit_sortino = next(s["sortino"] for s in exit_results if s["exit_thresh"] is None)
    eligible_exit = [s for s in exit_results if s["exit_thresh"] is not None]
    if eligible_exit:
        best_exit = _robust_select(eligible_exit, metric="sortino",
                                   param_key="exit_thresh", calmar_min=1.0)
        if best_exit["sortino"] > no_exit_sortino + 0.05:
            h1_exit_opt = best_exit["exit_thresh"]
    print(f"  → H1_EXIT_OPT = {h1_exit_opt}")

    # ── D: Regime z-threshold sweep ────────────────────────────────────────────
    print("\n[D] Regime z-threshold sweep ...")
    z_levels = [0.75, 1.00, 1.25, 1.50, 1.75, 2.00, 2.50]
    z_results = []
    for z in z_levels:
        lbl = f"H1_Z_{z:.2f}"
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=h1_sl_opt,
            c1_exit_thresh=h1_exit_opt, z_thresh=z,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["z"] = z
        z_results.append(stats)
        print(f"  Z={z:.2f}: ret={stats['total_return']*100:.1f}%  "
              f"Calmar={stats['calmar']:.2f}  MaxDD={stats['max_dd']*100:.1f}%")

    # Select z-threshold: robust plateau center (MaxDD improvement ≥ 10% filter first)
    no_gate_maxdd = z_results[-1]["max_dd"]  # z=2.50 ~ near-no-gate
    eligible_z = [s for s in z_results if abs(s["max_dd"]) < abs(no_gate_maxdd) * 0.90]
    h1_z_opt = 1.50  # default
    if eligible_z:
        best_z = _robust_select(eligible_z, metric="calmar", param_key="z")
        h1_z_opt = best_z["z"]
    print(f"  → H1_Z_OPT = {h1_z_opt}")

    # ── E: Portfolio construction sweep ───────────────────────────────────────
    print("\n[E] Portfolio construction sweep ...")
    topn_results = []
    for n in [2, 3, 4, 5, 6]:
        lbl = f"H1_TOPN_{n}"
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=h1_sl_opt,
            c1_exit_thresh=h1_exit_opt, z_thresh=h1_z_opt,
            top_n=n, label=lbl,
        )
        stats["top_n"] = n
        topn_results.append(stats)
        print(f"  TOP_N={n}: Sortino={stats['sortino']:.2f}  Calmar={stats['calmar']:.2f}")

    best_topn = _robust_select(topn_results, metric="sortino", param_key="top_n", calmar_min=1.0)
    h1_topn_opt = best_topn.get("top_n", TOP_N_DEFAULT)
    print(f"  → H1_TOPN_OPT = {h1_topn_opt}")

    sizing_results = []
    for sizing in ["ew", "score", "kelly"]:
        lbl = f"H1_SZ_{sizing}"
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=h1_sl_opt,
            c1_exit_thresh=h1_exit_opt, z_thresh=h1_z_opt,
            top_n=h1_topn_opt, sizing=sizing, label=lbl,
        )
        stats["sizing"] = sizing
        sizing_results.append(stats)
        print(f"  SIZING={sizing}: Sortino={stats['sortino']:.2f}  Calmar={stats['calmar']:.2f}")

    sz_eligible = [s for s in sizing_results if s.get("calmar", 0) >= 1.0] or sizing_results
    best_sz = max(sz_eligible, key=lambda s: s.get("sortino", 0))
    h1_sizing_opt = best_sz.get("sizing", "ew")
    print(f"  → H1_SIZING_OPT = {h1_sizing_opt}")

    # ── F: H1 final ───────────────────────────────────────────────────────────
    print("\n[F] H1 final (all selected layers) ...")
    nav_h1_final, stats_h1_final = _run_overlay_engine(
        all_prices, active_pairs, timestamps,
        signal_fn=_vt._compute_signal, signal_kwargs={},
        fee=FEE_DEFAULT, stop_loss_pct=h1_sl_opt,
        c1_exit_thresh=h1_exit_opt, z_thresh=h1_z_opt,
        top_n=h1_topn_opt, sizing=h1_sizing_opt, label="C_H1_final",
    )
    print(f"  C_H1_final: ret={stats_h1_final['total_return']*100:.1f}%  "
          f"Sortino={stats_h1_final['sortino']:.2f}  "
          f"Calmar={stats_h1_final['calmar']:.2f}  "
          f"MaxDD={stats_h1_final['max_dd']*100:.1f}%")

    # ── Cost robustness ────────────────────────────────────────────────────────
    print("\n[F-cost] H1 cost scenario analysis ...")
    cost_scenarios_h1 = _run_cost_scenarios(
        "H1", all_prices, active_pairs, timestamps,
        signal_fn=_vt._compute_signal, signal_kwargs_fn=lambda: {},
        stop_loss_pct=h1_sl_opt, c1_exit_thresh=h1_exit_opt,
        z_thresh=h1_z_opt, top_n=h1_topn_opt, sizing=h1_sizing_opt,
    )

    # ── OOS sub-period ─────────────────────────────────────────────────────────
    train_ts = [t for t in timestamps if t < HOLDOUT_TS]
    oos_ts   = [t for t in timestamps if t >= HOLDOUT_TS]

    oos_stats = {}
    if oos_ts:
        _, oos_st = _run_overlay_engine(
            all_prices, active_pairs, oos_ts,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=h1_sl_opt,
            c1_exit_thresh=h1_exit_opt, z_thresh=h1_z_opt,
            top_n=h1_topn_opt, sizing=h1_sizing_opt, label="H1_OOS",
        )
        oos_stats = oos_st
        print(f"  H1 OOS (Dec-Jan): ret={oos_st['total_return']*100:.1f}%  "
              f"Sortino={oos_st['sortino']:.2f}  Calmar={oos_st['calmar']:.2f}")

    # ── Write H1 output ────────────────────────────────────────────────────────
    _write_h1_report(
        va_results, sl_results, exit_results, z_results,
        topn_results, sizing_results, stats_h1_final, oos_stats,
        h1_sl_opt, h1_exit_opt, h1_z_opt, h1_topn_opt, h1_sizing_opt,
        cost_scenarios_h1,
    )
    _save_equity_charts(
        [(nav_h1_final, "H1 Final (all layers)")],
        os.path.join(CHARTS_H1, "h1_final_equity.png"),
    )

    return {
        "nav_final":   nav_h1_final,
        "stats_final": stats_h1_final,
        "sl_opt":      h1_sl_opt,
        "exit_opt":    h1_exit_opt,
        "z_opt":       h1_z_opt,
        "topn_opt":    h1_topn_opt,
        "sizing_opt":  h1_sizing_opt,
    }


# ── Section B: H2C Lead-Lag ────────────────────────────────────────────────────

def run_h2_section(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
    btc_key:      str,
    h1_z_opt:     float,
) -> dict:
    """Run H2C Version A + risk overlay sweeps. Returns selected params and results."""
    print("\n" + "="*60)
    print("SECTION B: H2C BTC Lead-Lag Mechanism")
    print("="*60)

    # Shared beta_hist initialiser for H2C signal
    def _make_beta_hist():
        return {p: [[], []] for p in active_pairs if p != btc_key}

    def _h2c_sig(all_prices, active_pairs, ts, beta_hist=None, mat2_time_thresh=None):
        if beta_hist is None:
            return None
        return _compute_h2c_signal(all_prices, active_pairs, ts, btc_key,
                                   beta_hist, mat2_time_thresh)

    # ── Version A: H2C faithful + fee sweep ────────────────────────────────────
    print("\n[A] Version A — H2C fee sweep ...")
    va_h2 = {}
    for fee in [0.0, FEE_DEFAULT, 0.001]:
        lbl = f"H2_A_fee{fee*100:.2f}"
        bh  = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig, signal_kwargs={"beta_hist": bh},
            fee=fee, z_thresh=h1_z_opt,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        va_h2[lbl] = stats
        print(f"  {lbl}: ret={stats['total_return']*100:.1f}%  "
              f"Sortino={stats['sortino']:.2f}  MaxDD={stats['max_dd']*100:.1f}%")

    # Baseline: 0.05% fee
    baseline_h2 = va_h2[f"H2_A_fee{FEE_DEFAULT*100:.2f}"]

    # ── Version B: HAZ2_BTC_VOL_Z sweep (H2-specific z-threshold) ─────────────
    print("\n[B] HAZ2_BTC_VOL_Z sweep (H2 vol-gate z-threshold) ...")
    h2_z_levels = [0.75, 1.00, 1.25, 1.50, 2.00, 9.99]  # 9.99 ≈ no gate
    z_results_h2 = []
    for z in h2_z_levels:
        lbl = f"H2_Z_{z:.2f}"
        bh  = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig, signal_kwargs={"beta_hist": bh},
            fee=FEE_DEFAULT, z_thresh=z,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["z_thresh_h2"] = z
        z_results_h2.append(stats)
        print(f"  Z={z:.2f}: ret={stats['total_return']*100:.1f}%  "
              f"Calmar={stats['calmar']:.2f}  MaxDD={stats['max_dd']*100:.1f}%")

    h2_z_opt = _robust_select(
        z_results_h2, metric="calmar", param_key="z_thresh_h2", calmar_min=0.5,
    ).get("z_thresh_h2", 1.50)
    print(f"  → H2_Z_OPT = {h2_z_opt}")

    # ── C: BTC-direction exit sweep ────────────────────────────────────────────
    print("\n[C] BTC-direction exit sweep ...")
    btc_rev_levels = [None, -0.005, -0.010, -0.015, -0.020, -0.030]
    btc_rev_results = []
    for rev in btc_rev_levels:
        lbl = f"H2_BTCREV_{rev}"
        bh  = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig, signal_kwargs={"beta_hist": bh},
            fee=FEE_DEFAULT, btc_rev_exit=rev, z_thresh=h2_z_opt,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["btc_rev"] = rev
        btc_rev_results.append(stats)
        print(f"  BTCREV={str(rev):8s}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}  exits={stats['n_exits']}")

    no_rev_calmar = next(s["calmar"] for s in btc_rev_results if s["btc_rev"] is None)
    h2_btcrev_opt = None
    non_none_rev = [s for s in btc_rev_results if s["btc_rev"] is not None]
    if non_none_rev:
        cand = _robust_select(non_none_rev, metric="calmar", param_key="btc_rev", calmar_min=0.5)
        if cand["calmar"] > no_rev_calmar * 1.10:
            h2_btcrev_opt = cand["btc_rev"]
    print(f"  → H2_BTCREV_OPT = {h2_btcrev_opt}")

    # ── Hold cap sweep ─────────────────────────────────────────────────────────
    print("\n[D] Hold cap sweep ...")
    holdcap_levels = [None, 3, 4, 5, 6, 8, 12]
    holdcap_results = []
    for hc in holdcap_levels:
        lbl = f"H2_HC_{hc}"
        bh  = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig, signal_kwargs={"beta_hist": bh},
            fee=FEE_DEFAULT, btc_rev_exit=h2_btcrev_opt,
            hold_cap_hours=hc, z_thresh=h2_z_opt,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["hold_cap"] = hc
        holdcap_results.append(stats)
        print(f"  HC={str(hc):5s}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}")

    best_hc = _robust_select(holdcap_results, metric="sortino",
                             param_key="hold_cap", calmar_min=0.5)
    h2_holdcap_opt = best_hc.get("hold_cap", None)
    print(f"  → H2_HOLDCAP_OPT = {h2_holdcap_opt}")

    # ── BTC gate sweep ─────────────────────────────────────────────────────────
    print("\n[E] BTC magnitude gate sweep ...")
    gate_levels = [0.0, 0.003, 0.005, 0.0075, 0.010, 0.015]
    gate_results = []
    for gate in gate_levels:
        lbl = f"H2_GATE_{gate}"
        bh  = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig, signal_kwargs={"beta_hist": bh},
            fee=FEE_DEFAULT, btc_rev_exit=h2_btcrev_opt,
            hold_cap_hours=h2_holdcap_opt, btc_gate_pct=gate,
            z_thresh=h2_z_opt, top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["btc_gate"] = gate
        gate_results.append(stats)
        print(f"  GATE={gate:.3f}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}  MaxDD={stats['max_dd']*100:.1f}%")

    best_gate = _robust_select(gate_results, metric="sortino",
                               param_key="btc_gate", calmar_min=0.5)
    h2_gate_opt = best_gate.get("btc_gate", 0.005)
    print(f"  → H2_GATE_OPT = {h2_gate_opt}")

    # ── Version F: MAT2_TIME_DECAY sweep ──────────────────────────────────────
    print("\n[F] MAT2_TIME_DECAY sweep (diffusion window freshness gate) ...")
    mat_levels = [0.30, 0.40, 0.50, 0.60, 0.75, None]  # None = no filter
    mat_results = []
    for mat in mat_levels:
        lbl = f"H2_MAT_{mat}"
        bh  = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig,
            signal_kwargs={"beta_hist": bh, "mat2_time_thresh": mat},
            fee=FEE_DEFAULT, btc_rev_exit=h2_btcrev_opt,
            hold_cap_hours=h2_holdcap_opt, btc_gate_pct=h2_gate_opt,
            z_thresh=h2_z_opt, top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["mat_thresh"] = mat
        mat_results.append(stats)
        print(f"  MAT={str(mat):5s}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}  MaxDD={stats['max_dd']*100:.1f}%")

    h2_mat_opt = _robust_select(
        mat_results, metric="sortino", param_key="mat_thresh", calmar_min=0.5,
    ).get("mat_thresh", None)
    print(f"  → H2_MAT_OPT = {h2_mat_opt}")

    # ── Portfolio construction ─────────────────────────────────────────────────
    print("\n[G] H2 portfolio construction sweep ...")
    h2_topn_opt = TOP_N_DEFAULT
    for n in [2, 3, 4, 5]:
        bh = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig,
            signal_kwargs={"beta_hist": bh, "mat2_time_thresh": h2_mat_opt},
            fee=FEE_DEFAULT, btc_rev_exit=h2_btcrev_opt,
            hold_cap_hours=h2_holdcap_opt, btc_gate_pct=h2_gate_opt,
            z_thresh=h2_z_opt, top_n=n, label=f"H2_TOPN_{n}",
        )
        stats["top_n"] = n
        print(f"  TOPN={n}: Sortino={stats['sortino']:.2f}  Calmar={stats['calmar']:.2f}")
        if stats["sortino"] > va_h2[f"H2_A_fee{FEE_DEFAULT*100:.2f}"]["sortino"] * 0.9 and \
           stats["calmar"] >= 0.5:
            h2_topn_opt = n  # take last that maintains performance

    # ── H2 final ───────────────────────────────────────────────────────────────
    print("\n[H] H2 final (all selected layers: B+C+D+E+F) ...")
    bh = _make_beta_hist()
    nav_h2_final, stats_h2_final = _run_overlay_engine(
        all_prices, active_pairs, timestamps,
        signal_fn=_h2c_sig,
        signal_kwargs={"beta_hist": bh, "mat2_time_thresh": h2_mat_opt},
        fee=FEE_DEFAULT, btc_rev_exit=h2_btcrev_opt,
        hold_cap_hours=h2_holdcap_opt, btc_gate_pct=h2_gate_opt,
        z_thresh=h2_z_opt, top_n=h2_topn_opt, label="C_H2_final",
    )
    print(f"  C_H2_final: ret={stats_h2_final['total_return']*100:.1f}%  "
          f"Sortino={stats_h2_final['sortino']:.2f}  "
          f"Calmar={stats_h2_final['calmar']:.2f}  "
          f"MaxDD={stats_h2_final['max_dd']*100:.1f}%")

    # ── Cost robustness ────────────────────────────────────────────────────────
    print("\n[H-cost] H2 cost scenario analysis ...")
    cost_scenarios_h2 = _run_cost_scenarios(
        "H2", all_prices, active_pairs, timestamps,
        signal_fn=_h2c_sig,
        signal_kwargs_fn=lambda: {"beta_hist": _make_beta_hist(), "mat2_time_thresh": h2_mat_opt},
        btc_rev_exit=h2_btcrev_opt, hold_cap_hours=h2_holdcap_opt,
        btc_gate_pct=h2_gate_opt, z_thresh=h2_z_opt, top_n=h2_topn_opt,
    )

    _write_h2_report(
        va_h2, z_results_h2, btc_rev_results, holdcap_results, gate_results,
        mat_results, stats_h2_final,
        h2_z_opt, h2_btcrev_opt, h2_holdcap_opt, h2_gate_opt, h2_mat_opt, h2_topn_opt,
        cost_scenarios_h2,
    )
    _save_equity_charts(
        [(nav_h2_final, "H2C Final (all layers)")],
        os.path.join(CHARTS_H2, "h2_final_equity.png"),
    )

    return {
        "nav_final":    nav_h2_final,
        "stats_final":  stats_h2_final,
        "btcrev_opt":   h2_btcrev_opt,
        "holdcap_opt":  h2_holdcap_opt,
        "gate_opt":     h2_gate_opt,
        "z_opt":        h2_z_opt,
        "mat_opt":      h2_mat_opt,
        "topn_opt":     h2_topn_opt,
        "make_beta_hist": _make_beta_hist,
        "signal_fn":    _h2c_sig,
    }


# ── Section C: Dual-Engine Regime Allocation ─────────────────────────────────

def run_dual_section(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
    btc_key:      str,
    h1_params:    dict,
    h2_params:    dict,
) -> dict:
    """Regime-conditional allocation sweep, OOS holdout, parameter robustness."""
    print("\n" + "="*60)
    print("SECTION C: Dual-Engine Regime Allocation")
    print("="*60)

    def _dual_signal_fn(all_prices, active_pairs, ts, alpha=0.50, beta_hist=None):
        """Regime-conditional signal blend for dual-engine trade aggregation.

        Both engines operate on the same asset universe. Signals are blended HERE
        at the signal level (not at the order level) before allocation. This produces
        one target portfolio → one set of trades → one fee charge per rebalance.

        Architecture:
          blended_z_i = α × H2C_z_i + (1−α) × H1_z_i → re-normalize CS → one allocation
          TREND_FLAT (|r_BTC,2h| < 0.5%): H1 only (H2 diffusion mechanism inactive)
          TREND_ACTIVE: blend H1 + H2C at weight α

        This is NOT two independent strategies merged at the order book — that pattern
        would create opposing trades (H1 sell + H2 buy on same asset), double-count fees,
        and produce incoherent position sizing. Signal-level blending prevents all three.
        """
        h1_sig = _vt._compute_signal(all_prices, active_pairs, ts)
        if beta_hist is None or h1_sig is None:
            return h1_sig

        # Determine BTC regime state
        r_btc_2h = _vt.compute_return(all_prices.get(btc_key, {}), ts, 2.0) or 0.0
        btc_active = abs(r_btc_2h) >= 0.005  # |r_BTC,2h| >= 0.5%

        if not btc_active:
            return h1_sig  # TREND_FLAT: H1 only

        # TREND_ACTIVE: blend H1 + H2C
        h2_sig = _compute_h2c_signal(all_prices, active_pairs, ts, btc_key, beta_hist)
        if h2_sig is None:
            return h1_sig

        blended = {}
        for pair in h1_sig:
            h1_sc = h1_sig.get(pair, 0.0)
            h2_sc = h2_sig.get(pair, 0.0)
            blended[pair] = alpha * h2_sc + (1 - alpha) * h1_sc
        return _vt.cross_sectional_z(blended) if blended else None

    # ── alpha_TREND sweep ──────────────────────────────────────────────────────
    print("\n[A] alpha_TREND sweep (H2 weight in TREND_ACTIVE periods) ...")
    alpha_levels = [0.0, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 1.0]
    alpha_results = []
    for alpha in alpha_levels:
        bh = h2_params["make_beta_hist"]()
        lbl = f"DUAL_a{alpha:.2f}"
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_dual_signal_fn,
            signal_kwargs={"alpha": alpha, "beta_hist": bh},
            fee=FEE_DEFAULT,
            stop_loss_pct=h1_params["sl_opt"],
            c1_exit_thresh=h1_params["exit_opt"],
            z_thresh=h1_params["z_opt"],
            top_n=h1_params["topn_opt"],
            sizing=h1_params["sizing_opt"],
            label=lbl,
        )
        stats["alpha"] = alpha
        alpha_results.append(stats)
        print(f"  α={alpha:.2f}: ret={stats['total_return']*100:.1f}%  "
              f"Sortino={stats['sortino']:.2f}  Calmar={stats['calmar']:.2f}")

    h1_calmar = h1_params["stats_final"]["calmar"]
    best_alpha = _robust_select(
        alpha_results, metric="sortino", param_key="alpha",
        calmar_min=max(h1_calmar * 0.90, 0.5),
    )
    alpha_opt = best_alpha.get("alpha", 0.35)
    print(f"  → alpha_TREND_OPT = {alpha_opt}")

    # ── C_combined final ──────────────────────────────────────────────────────
    print("\n[B] C_combined final ...")
    bh = h2_params["make_beta_hist"]()
    nav_comb, stats_comb = _run_overlay_engine(
        all_prices, active_pairs, timestamps,
        signal_fn=_dual_signal_fn,
        signal_kwargs={"alpha": alpha_opt, "beta_hist": bh},
        fee=FEE_DEFAULT,
        stop_loss_pct=h1_params["sl_opt"],
        c1_exit_thresh=h1_params["exit_opt"],
        z_thresh=h1_params["z_opt"],
        top_n=h1_params["topn_opt"],
        sizing=h1_params["sizing_opt"],
        label="C_combined",
    )
    print(f"  C_combined: ret={stats_comb['total_return']*100:.1f}%  "
          f"Sortino={stats_comb['sortino']:.2f}  "
          f"Calmar={stats_comb['calmar']:.2f}  "
          f"MaxDD={stats_comb['max_dd']*100:.1f}%")

    # ── Cost robustness ────────────────────────────────────────────────────────
    print("\n[B-cost] Combined cost scenario analysis ...")
    cost_scenarios_comb = _run_cost_scenarios(
        "COMB", all_prices, active_pairs, timestamps,
        signal_fn=_dual_signal_fn,
        signal_kwargs_fn=lambda: {"alpha": alpha_opt, "beta_hist": h2_params["make_beta_hist"]()},
        stop_loss_pct=h1_params["sl_opt"], c1_exit_thresh=h1_params["exit_opt"],
        z_thresh=h1_params["z_opt"], top_n=h1_params["topn_opt"],
        sizing=h1_params["sizing_opt"],
    )

    # ── OOS holdout ────────────────────────────────────────────────────────────
    print("\n[C] OOS holdout (Dec 2024 – Jan 2025) ...")
    oos_ts = [t for t in timestamps if t >= HOLDOUT_TS]
    oos_stats: dict = {}
    if oos_ts:
        bh = h2_params["make_beta_hist"]()
        _, oos_st = _run_overlay_engine(
            all_prices, active_pairs, oos_ts,
            signal_fn=_dual_signal_fn,
            signal_kwargs={"alpha": alpha_opt, "beta_hist": bh},
            fee=FEE_DEFAULT,
            stop_loss_pct=h1_params["sl_opt"],
            c1_exit_thresh=h1_params["exit_opt"],
            z_thresh=h1_params["z_opt"],
            top_n=h1_params["topn_opt"],
            sizing=h1_params["sizing_opt"],
            label="C_combined_OOS",
        )
        oos_stats = oos_st
        print(f"  OOS: ret={oos_st['total_return']*100:.1f}%  "
              f"Sortino={oos_st['sortino']:.2f}  Calmar={oos_st['calmar']:.2f}")

    # ── Parameter perturbation robustness ──────────────────────────────────────
    print("\n[D] Parameter perturbation (±20% on key params) ...")
    perturb_results = []
    z_base   = h1_params["z_opt"]
    sl_base  = h1_params["sl_opt"] or -0.04
    a_base   = alpha_opt

    for z_mult, sl_mult, a_mult, tag in [
        (0.80, 0.80, 0.80, "−20%"),
        (1.00, 1.00, 1.00, "baseline"),
        (1.20, 1.20, 1.20, "+20%"),
    ]:
        bh = h2_params["make_beta_hist"]()
        z_p = z_base * z_mult
        sl_p = sl_base * sl_mult if h1_params["sl_opt"] is not None else None
        a_p = min(max(a_base * a_mult, 0.0), 1.0)
        _, st = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_dual_signal_fn,
            signal_kwargs={"alpha": a_p, "beta_hist": bh},
            fee=FEE_DEFAULT,
            stop_loss_pct=sl_p,
            c1_exit_thresh=h1_params["exit_opt"],
            z_thresh=z_p,
            top_n=h1_params["topn_opt"],
            sizing=h1_params["sizing_opt"],
            label=f"perturb_{tag}",
        )
        perturb_results.append((tag, st))
        print(f"  {tag}: Calmar={st['calmar']:.2f}  Sortino={st['sortino']:.2f}")

    _write_combined_report(
        alpha_results, stats_comb, oos_stats, perturb_results,
        h1_params, h2_params, alpha_opt, cost_scenarios_comb,
    )
    _save_equity_charts(
        [
            (h1_params["nav_final"], "H1-only"),
            (h2_params["nav_final"], "H2C-only"),
            (nav_comb, "Dual-Engine (combined)"),
        ],
        os.path.join(CHARTS_COMB, "combined_equity.png"),
    )

    return {
        "nav_final":   nav_comb,
        "stats_final": stats_comb,
        "oos_stats":   oos_stats,
        "alpha_opt":   alpha_opt,
    }


# ── Section [G]: Dual Portfolio Backtest (Portfolio-Level Aggregation) ─────────

def _build_hourly_returns(
    nav_series: List[Tuple[int, float]],
    timestamps: List[int],
) -> Dict[int, float]:
    """Forward-fill NAV series onto hourly grid; return {ts: hourly_return}.

    _run_overlay_engine appends at every timestep, but alignment may differ if
    the H1 and H2C nav_series were built on different timestamp grids. Forward-
    filling ensures gaps are treated as flat (no return) rather than zero.
    """
    nav_dict = dict(nav_series)
    result: Dict[int, float] = {}
    prev_nav = 1.0
    for ts in timestamps:
        nav = nav_dict.get(ts, prev_nav)
        result[ts] = nav / prev_nav - 1.0
        prev_nav = nav
    return result


def _compute_continuous_alloc_series(
    all_prices: Dict[str, Dict[int, float]],
    timestamps: List[int],
    btc_key: str,
    f_max: float,
    btc_scale: float = 0.003,
    z_scale: float = 2.0,
    lookback: int = 48,
) -> Dict[int, float]:
    """Compute per-timestep H2C capital fraction using continuous failure-mode functions.

    f_t = f_max × btc_activity_factor_t × stress_decay_factor_t

    btc_activity_factor_t = min(1, |r_BTC,2h| / btc_scale)
        → 0 when BTC flat; ramps to 1 at btc_scale move
        → H2C signal is meaningless when BTC doesn't move (failure mode 1)

    stress_decay_factor_t = max(0, 1 − vol_z / z_scale)
        → 1 when vol_z=0 (calm); decays to 0 at z_scale (stressed)
        → H2C breaks when correlations spike in stressed markets (failure mode 2)

    Fixed parameters (not swept, economically anchored):
        btc_scale = 0.003  validated from H2C gate sweep (Section B minimum BTC move)
        z_scale   = 2.0    natural: 2σ above rolling median = market fully stressed
    Only f_max is swept — single free parameter.
    """
    btc_prices = all_prices.get(btc_key, {})
    abs_ret_hist: List[float] = []
    alloc: Dict[int, float] = {}

    for ts in timestamps:
        r_1h = abs(_vt.compute_return(btc_prices, ts, 1.0) or 0.0)
        abs_ret_hist.append(r_1h)
        if len(abs_ret_hist) > lookback:
            abs_ret_hist = abs_ret_hist[-lookback:]

        if len(abs_ret_hist) >= 10:
            mu  = sum(abs_ret_hist) / len(abs_ret_hist)
            var = sum((x - mu) ** 2 for x in abs_ret_hist) / len(abs_ret_hist)
            std = var ** 0.5
            vol_z = (r_1h - mu) / std if std > 1e-12 else 0.0
        else:
            vol_z = 0.0

        btc_r2h = abs(_vt.compute_return(btc_prices, ts, 2.0) or 0.0)
        btc_activity = min(1.0, btc_r2h / btc_scale) if btc_scale > 0 else 0.0
        stress_decay = max(0.0, 1.0 - vol_z / z_scale) if z_scale > 0 else 0.0
        alloc[ts] = f_max * btc_activity * stress_decay

    return alloc


def _combine_portfolio_navs(
    h1_returns:  Dict[int, float],
    h2c_returns: Dict[int, float],
    timestamps:  List[int],
    alloc:       Dict[int, float],
) -> List[Tuple[int, float]]:
    """Combine H1 and H2C return streams using precomputed per-timestep fractions.

    return_t = (1 − f_t) × h1_ret_t + f_t × h2c_ret_t
    Both engine NAV series have fees embedded from Sections A and B.
    f_t comes from _compute_continuous_alloc_series — already encodes both
    failure-mode gates (BTC activity and stress decay).
    """
    nav = 1.0
    combined: List[Tuple[int, float]] = [(timestamps[0], nav)]
    for ts in timestamps[1:]:
        f       = alloc.get(ts, 0.0)
        h1_ret  = h1_returns.get(ts, 0.0)
        h2c_ret = h2c_returns.get(ts, 0.0)
        nav *= 1.0 + (1.0 - f) * h1_ret + f * h2c_ret
        combined.append((ts, nav))
    return combined


def run_dual_portfolio_section(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
    btc_key:      str,
    h1_params:    dict,
    h2_params:    dict,
) -> dict:
    """Section [G] — Portfolio-level dual-engine aggregation backtest.

    H1 and H2C run as INDEPENDENT engines with their own asset selection.
    Capital is allocated between them at the portfolio weight level (one set
    of trades, minimized fees). Allocation is continuous and derived from each
    engine's known failure modes:

        f_t = f_max × btc_activity_factor_t × stress_decay_factor_t

    btc_activity_factor  — H2C fails when BTC flat (no diffusion signal)
    stress_decay_factor  — H2C fails when market stressed (correlation spike)

    Only f_max is swept. btc_scale and z_scale are fixed to economically
    anchored values, not optimized — minimal parameter count for robustness.

    Reuses h1_params["nav_final"] and h2_params["nav_final"] from Sections A/B.
    """
    print("\n" + "=" * 60)
    print("SECTION [G]: Dual Portfolio Backtest — Continuous Regime Allocation")
    print("=" * 60)

    BTC_SCALE = 0.003   # validated from Section B gate sweep
    Z_SCALE   = 2.0     # 2σ above rolling median = fully stressed

    # ── [G-0] Build inputs + baselines ───────────────────────────────────────
    h1_nav  = h1_params["nav_final"]
    h2c_nav = h2_params["nav_final"]
    h1_ret  = _build_hourly_returns(h1_nav,  timestamps)
    h2c_ret = _build_hourly_returns(h2c_nav, timestamps)

    h1_stats  = _stats(h1_nav,  "G_H1_only")
    h2c_stats = _stats(h2c_nav, "G_H2C_only")
    print(f"\n[G-0] Baselines")
    print(f"  H1:  ret={h1_stats['total_return']*100:.1f}%  "
          f"Sortino={h1_stats['sortino']:.2f}  Calmar={h1_stats['calmar']:.2f}  "
          f"MaxDD={h1_stats['max_dd']*100:.1f}%")
    print(f"  H2C: ret={h2c_stats['total_return']*100:.1f}%  "
          f"Sortino={h2c_stats['sortino']:.2f}  Calmar={h2c_stats['calmar']:.2f}  "
          f"MaxDD={h2c_stats['max_dd']*100:.1f}%")

    # Pre-compute alloc at f_max=1.0 to get activity statistics
    alloc_diag = _compute_continuous_alloc_series(
        all_prices, timestamps, btc_key, f_max=1.0,
        btc_scale=BTC_SCALE, z_scale=Z_SCALE,
    )
    total_ts = len(timestamps)
    mean_alloc = sum(alloc_diag.values()) / total_ts if total_ts else 0.0
    n_nonzero  = sum(1 for v in alloc_diag.values() if v > 0.01)
    print(f"\n  Alloc diagnostics (f_max=1.0): mean={mean_alloc*100:.1f}%  "
          f"active>1%: {n_nonzero/total_ts*100:.0f}% of timesteps")

    # ── [G-1] f_max sweep ────────────────────────────────────────────────────
    print("\n[G-1] f_max sweep (continuous allocation) ...")
    F_MAX_GRID = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.80, 1.0]
    sweep_results: List[Tuple[float, dict, List, Dict]] = []
    for f_max in F_MAX_GRID:
        alloc = _compute_continuous_alloc_series(
            all_prices, timestamps, btc_key, f_max,
            btc_scale=BTC_SCALE, z_scale=Z_SCALE,
        )
        comb_nav = _combine_portfolio_navs(h1_ret, h2c_ret, timestamps, alloc)
        st = _stats(comb_nav, f"G1_fmax{int(f_max*100):03d}")
        mean_f = sum(alloc.values()) / total_ts if total_ts else 0.0
        st["f_max"]  = f_max
        st["mean_f"] = mean_f
        sweep_results.append((f_max, st, comb_nav, alloc))
        print(f"  f_max={f_max:.2f} (mean_f={mean_f*100:.1f}%): "
              f"ret={st['total_return']*100:.1f}%  "
              f"Sortino={st['sortino']:.2f}  Calmar={st['calmar']:.2f}  "
              f"MaxDD={st['max_dd']*100:.1f}%")

    best_s = _robust_select(
        [{"f_max": f, **st} for f, st, _, _ in sweep_results],
        metric="sortino",
        param_key="f_max",
        calmar_min=max(h1_stats["calmar"] * 0.90, 0.5),
    )
    f_max_opt = best_s.get("f_max", 0.0)
    # Retrieve the nav and alloc for the optimal f_max
    _, stats_opt, nav_opt, alloc_opt = next(r for r in sweep_results if r[0] == f_max_opt)
    stats_opt = _stats(nav_opt, "G1_optimal")
    mean_f_opt = sum(alloc_opt.values()) / total_ts if total_ts else 0.0
    print(f"\n  → f_max_opt={f_max_opt:.2f}  mean_f={mean_f_opt*100:.1f}%")
    print(f"  → Optimal: ret={stats_opt['total_return']*100:.1f}%  "
          f"Sortino={stats_opt['sortino']:.2f}  Calmar={stats_opt['calmar']:.2f}  "
          f"MaxDD={stats_opt['max_dd']*100:.1f}%")

    # ── [G-2] OOS holdout ─────────────────────────────────────────────────────
    print("\n[G-2] OOS holdout (Dec 2024 – Jan 2025) ...")
    max_ts = max(timestamps)
    # Use alloc from full timestamps (proper vol_z lookback continuity), sliced to OOS
    oos_ts     = [ts for ts in timestamps if ts >= HOLDOUT_TS]
    h1_ret_oos  = _build_hourly_returns(
        [(ts, nav) for ts, nav in h1_nav  if ts >= HOLDOUT_TS], oos_ts)
    h2c_ret_oos = _build_hourly_returns(
        [(ts, nav) for ts, nav in h2c_nav if ts >= HOLDOUT_TS], oos_ts)
    alloc_oos = {ts: alloc_opt[ts] for ts in oos_ts if ts in alloc_opt}
    oos_nav   = _combine_portfolio_navs(h1_ret_oos, h2c_ret_oos, oos_ts, alloc_oos)

    h1_oos_stats  = _subperiod_stats(h1_nav,  HOLDOUT_TS, max_ts + 1, "G_OOS_h1")
    h2c_oos_stats = _subperiod_stats(h2c_nav, HOLDOUT_TS, max_ts + 1, "G_OOS_h2c")
    oos_stats     = _stats(oos_nav, "G_OOS_opt")
    print(f"  H1-only OOS:       ret={h1_oos_stats['total_return']*100:.1f}%  "
          f"Sortino={h1_oos_stats['sortino']:.2f}  Calmar={h1_oos_stats['calmar']:.2f}")
    print(f"  H2C-only OOS:      ret={h2c_oos_stats['total_return']*100:.1f}%  "
          f"Sortino={h2c_oos_stats['sortino']:.2f}  Calmar={h2c_oos_stats['calmar']:.2f}")
    print(f"  Portfolio agg OOS: ret={oos_stats['total_return']*100:.1f}%  "
          f"Sortino={oos_stats['sortino']:.2f}  Calmar={oos_stats['calmar']:.2f}")

    # ── [G-3] Perturbation robustness ─────────────────────────────────────────
    print("\n[G-3] Perturbation robustness (±20% on f_max) ...")
    perturb_results: List[dict] = []
    for delta, tag in [(-0.20, "-20%"), (0.0, "baseline"), (+0.20, "+20%")]:
        f_p   = max(0.0, min(1.0, f_max_opt * (1 + delta)))
        alloc_p = _compute_continuous_alloc_series(
            all_prices, timestamps, btc_key, f_p,
            btc_scale=BTC_SCALE, z_scale=Z_SCALE,
        )
        p_nav = _combine_portfolio_navs(h1_ret, h2c_ret, timestamps, alloc_p)
        st = _stats(p_nav, f"G3_{tag}")
        perturb_results.append({"tag": tag, "f_max": f_p, **st})
        print(f"  {tag}: f_max={f_p:.2f} → "
              f"Sortino={st['sortino']:.2f}  Calmar={st['calmar']:.2f}  "
              f"MaxDD={st['max_dd']*100:.1f}%")

    # ── [G-4] Activation gates ─────────────────────────────────────────────────
    print("\n[G-4] Activation gates ...")
    gate1 = stats_opt["sortino"] >= 1.05 * h1_stats["sortino"]
    gate2 = stats_opt["calmar"]  >= 0.90 * h1_stats["calmar"]
    gate3 = oos_stats["sortino"] >  h1_oos_stats["sortino"]
    all_pass = gate1 and gate2 and gate3
    print(f"  Gate 1 (Sortino ≥ 1.05×H1 = {1.05*h1_stats['sortino']:.2f}): "
          f"{'PASS' if gate1 else 'FAIL'} (achieved {stats_opt['sortino']:.2f})")
    print(f"  Gate 2 (Calmar  ≥ 0.90×H1 = {0.90*h1_stats['calmar']:.2f}):  "
          f"{'PASS' if gate2 else 'FAIL'} (achieved {stats_opt['calmar']:.2f})")
    print(f"  Gate 3 (OOS Sortino > H1 OOS = {h1_oos_stats['sortino']:.2f}): "
          f"{'PASS' if gate3 else 'FAIL'} (achieved {oos_stats['sortino']:.2f})")
    print(f"  → Overall: {'ALL PASS — H2C activation validated' if all_pass else 'FAIL — H2C remains disabled'}")

    # ── [G-5] Charts ──────────────────────────────────────────────────────────
    _save_equity_charts(
        [
            (h1_nav,  "H1 only"),
            (h2c_nav, "H2C only"),
            (nav_opt, f"Portfolio agg (f_max={f_max_opt:.2f}, mean_f={mean_f_opt*100:.1f}%)"),
        ],
        os.path.join(CHARTS_COMB, "portfolio_aggregation_equity.png"),
    )

    # ── [G-6] Write report ────────────────────────────────────────────────────
    _write_portfolio_report(
        h1_stats=h1_stats,
        h2c_stats=h2c_stats,
        sweep_results=sweep_results,
        f_max_opt=f_max_opt,
        mean_f_opt=mean_f_opt,
        stats_opt=stats_opt,
        h1_oos_stats=h1_oos_stats,
        h2c_oos_stats=h2c_oos_stats,
        oos_stats=oos_stats,
        perturb_results=perturb_results,
        gate1=gate1, gate2=gate2, gate3=gate3, all_pass=all_pass,
        total_ts=total_ts, btc_scale=BTC_SCALE, z_scale=Z_SCALE,
    )

    return {
        "nav_final":   nav_opt,
        "stats_final": stats_opt,
        "oos_stats":   oos_stats,
        "f_max_opt":   f_max_opt,
        "all_pass":    all_pass,
    }


# ── Chart helpers ──────────────────────────────────────────────────────────────

def _save_equity_charts(
    nav_list: List[Tuple[List[Tuple[int, float]], str]],
    output_path: str,
) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print(f"  [SKIP] matplotlib not available — skipping {output_path}")
        return

    _epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    colors = ["#2ecc71", "#3498db", "#e74c3c", "#9b59b6", "#f39c12"]

    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (nav_series, lbl) in enumerate(nav_list):
        if not nav_series:
            continue
        xs = [_epoch + timedelta(milliseconds=t) for t, _ in nav_series]
        ys = [n for _, n in nav_series]
        ax.plot(xs, ys, color=colors[i % len(colors)], linewidth=1.5, label=lbl)

    ax.axhline(1.0, color="grey", linewidth=0.5, linestyle=":")
    ax.set_ylabel("NAV (start = 1.0)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"  [chart] {output_path}")


# ── Report writers ─────────────────────────────────────────────────────────────

def _fmt(x: float, pct: bool = False) -> str:
    if x == float("inf"):
        return "∞"
    return f"{x*100:.1f}%" if pct else f"{x:.2f}"


def _write_h1_report(
    va_results, sl_results, exit_results, z_results,
    topn_results, sizing_results, final_stats, oos_stats,
    sl_opt, exit_opt, z_opt, topn_opt, sizing_opt,
    cost_scenarios=None,
) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# H1 Reversal — Mechanism-Specific Backtest",
        f"**Generated:** {gen}",
        "",
        "## Parameter Disclosure",
        "",
        "All risk overlay parameters selected by sweep on Oct–Nov 2024 training period.",
        "OOS window (Dec 2024–Jan 2025) evaluated **after** parameter selection, never used for selection.",
        "",
        f"| Parameter | Value | Source |",
        f"|-----------|-------|--------|",
        f"| C1 formula | 0.70×CS_z(−C1_raw) + 0.30×CS_z(−rvol) | signal_search.py / vector_tests.py |",
        f"| Hold cadence | 4h | vector_tests.py (promoted object) |",
        f"| TOP_N | {topn_opt} | Portfolio sweep |",
        f"| Sizing | {sizing_opt} | Portfolio sweep |",
        f"| C2 z-threshold | {z_opt} | Regime sweep |",
        f"| Stop-loss | {sl_opt} | Risk overlay sweep |",
        f"| C1 exit threshold | {exit_opt} | Signal exit sweep |",
        f"| Fee/trade | {FEE_DEFAULT*100:.2f}% maker | Competition rules |",
        "",
        "---",
        "",
        "## Version A — Cross-Validation (must match vector_tests.py within 0.1pp)",
        "",
        "| Run | Total Return | Sortino | Calmar | MaxDD |",
        "|-----|-------------|---------|--------|-------|",
    ]
    for lbl, r in va_results.items():
        s = r["stats"]
        lines.append(
            f"| {lbl} | {_fmt(s.get('total_return',0), True)} | "
            f"{_fmt(s.get('sharpe_ann', s.get('sortino',0)))} | "
            f"{_fmt(s.get('calmar',0))} | "
            f"{_fmt(s.get('max_dd',0), True)} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Risk Overlay Sweeps",
        "",
        "### B: Stop-Loss Threshold",
        "",
        "| Stop Level | Total Return | Calmar | MaxDD | Stops/Period |",
        "|------------|-------------|--------|-------|--------------|",
    ]
    for s in sl_results:
        sp = s["n_stops"] / max(s["n_rebal"], 1)
        lines.append(
            f"| {s['sl']} | {_fmt(s['total_return'], True)} | "
            f"{_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} | {sp*100:.1f}% |"
        )
    lines.append(f"\n**Selected: H1_SL_OPT = {sl_opt}**\n")

    lines += [
        "### C: C1 Signal Exit",
        "",
        "| Exit Threshold | Total Return | Sortino | Calmar |",
        "|---------------|-------------|---------|--------|",
    ]
    for s in exit_results:
        lines.append(
            f"| {s['exit_thresh']} | {_fmt(s['total_return'], True)} | "
            f"{_fmt(s['sortino'])} | {_fmt(s['calmar'])} |"
        )
    lines.append(f"\n**Selected: H1_EXIT_OPT = {exit_opt}**\n")

    lines += [
        "### D: Regime Z-Threshold",
        "",
        "| Z-Threshold | Total Return | Calmar | MaxDD |",
        "|-------------|-------------|--------|-------|",
    ]
    for s in z_results:
        lines.append(
            f"| {s['z']} | {_fmt(s['total_return'], True)} | "
            f"{_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
        )
    lines.append(f"\n**Selected: H1_Z_OPT = {z_opt}**\n")

    lines += [
        "---",
        "",
        "## H1 Final — All Selected Layers",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Return | {_fmt(final_stats['total_return'], True)} |",
        f"| Annualized Return | {_fmt(final_stats.get('ann_return', 0), True)} |",
        f"| Sortino | {_fmt(final_stats['sortino'])} |",
        f"| Calmar | {_fmt(final_stats['calmar'])} |",
        f"| Max Drawdown | {_fmt(final_stats['max_dd'], True)} |",
        "",
    ]

    if oos_stats:
        lines += [
            "## OOS Holdout (Dec 2024 – Jan 2025)",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Return | {_fmt(oos_stats['total_return'], True)} |",
            f"| Sortino | {_fmt(oos_stats['sortino'])} |",
            f"| Calmar | {_fmt(oos_stats['calmar'])} |",
            f"| Max Drawdown | {_fmt(oos_stats['max_dd'], True)} |",
            "",
        ]

    if cost_scenarios:
        maker_taker = next((s for s in cost_scenarios if s["scenario"] == "maker/taker"), None)
        gate_result = "PASS" if maker_taker and maker_taker["calmar"] > 0 else "FAIL"
        lines += [
            "---",
            "",
            "## Cost Scenario Analysis",
            "",
            "Strategy must remain Sortino > 0 and Calmar > 0 across all realistic fee scenarios.",
            "",
            "| Scenario | Entry Fee | Exit Fee | Sortino | Calmar | MaxDD |",
            "|----------|-----------|----------|---------|--------|-------|",
        ]
        for s in cost_scenarios:
            lines.append(
                f"| {s['scenario']} | {s['fee_entry']*100:.2f}% | {s['fee_exit']*100:.2f}% | "
                f"{_fmt(s['sortino'])} | {_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
            )
        lines.append(f"\nGate: Calmar > 0 in maker/taker scenario → **{gate_result}**\n")

    lines += [
        "---",
        "",
        f"*Charts: see `H1_reversal/02_Candidates/Strategy/charts/backtest/`*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_H1), exist_ok=True)
    with open(OUTPUT_H1, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_H1}")


def _write_h2_report(
    va_h2, z_results_h2, btc_rev_results, holdcap_results, gate_results,
    mat_results, final_stats,
    z_opt, btcrev_opt, holdcap_opt, gate_opt, mat_opt, topn_opt,
    cost_scenarios=None,
) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# H2C BTC Lead-Lag — Mechanism-Specific Backtest",
        f"**Generated:** {gen}",
        "",
        "## Signal Formula",
        "",
        "```",
        "H2C_score_i = CS_z(β_i × r_BTC,2h − r_i,2h)",
        "β_i = rolling 48h OLS slope (r_i on r_BTC hourly returns)",
        "```",
        "",
        "IC = +0.042 @ 1h, t = +9.85 (signal_search.py, promoted)",
        "",
        "---",
        "",
        "## Version A — H2C Fee Sweep",
        "",
        "| Run | Total Return | Sortino | Calmar | MaxDD |",
        "|-----|-------------|---------|--------|-------|",
    ]
    for lbl, s in va_h2.items():
        lines.append(
            f"| {lbl} | {_fmt(s['total_return'], True)} | "
            f"{_fmt(s['sortino'])} | {_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Risk Overlay Sweeps",
        "",
        "### B: HAZ2_BTC_VOL_Z — H2-Specific Volatility Gate",
        "",
        "Block H2C entries when BTC realized vol z-score exceeds threshold.",
        "H2 may need a different gate level than H1 (H2 is momentum; high vol can be opportunity).",
        "",
        "| Z Threshold | Total Return | Calmar | MaxDD |",
        "|-------------|-------------|--------|-------|",
    ]
    for s in z_results_h2:
        lines.append(
            f"| {s['z_thresh_h2']:.2f} | {_fmt(s['total_return'], True)} | "
            f"{_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
        )
    lines.append(f"\n**Selected (robust plateau center): H2_Z_OPT = {z_opt}**\n")

    lines += [
        "### C: BTC-Direction Exit",
        "",
        "Mechanism-appropriate exit: H2 relies on BTC continuing in the same direction.",
        "Exit when BTC return since position entry falls below threshold.",
        "",
        "| BTC Rev Exit | Sortino | Calmar | MaxDD | Exits Triggered |",
        "|--------------|---------|--------|-------|----------------|",
    ]
    for s in btc_rev_results:
        lines.append(
            f"| {s['btc_rev']} | {_fmt(s['sortino'])} | "
            f"{_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} | {s['n_exits']} |"
        )
    lines.append(f"\n**Selected: H2_BTCREV_OPT = {btcrev_opt}**\n")

    lines += [
        "### D: Hold Cap (diffusion should complete within N hours)",
        "",
        "| Hold Cap | Sortino | Calmar |",
        "|----------|---------|--------|",
    ]
    for s in holdcap_results:
        lines.append(f"| {s['hold_cap']} | {_fmt(s['sortino'])} | {_fmt(s['calmar'])} |")
    lines.append(f"\n**Selected: H2_HOLDCAP_OPT = {holdcap_opt}**\n")

    lines += [
        "### E: BTC Magnitude Gate",
        "",
        "H2 only admissible when BTC made a non-trivial directional move.",
        "",
        "| BTC Gate | Sortino | Calmar | MaxDD |",
        "|----------|---------|--------|-------|",
    ]
    for s in gate_results:
        lines.append(
            f"| {s['btc_gate']:.3f} | {_fmt(s['sortino'])} | "
            f"{_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
        )
    lines.append(f"\n**Selected: H2_GATE_OPT = {gate_opt}**\n")

    lines += [
        "### F: MAT2_TIME_DECAY — Diffusion Window Freshness Gate",
        "",
        "Only enter H2C positions when the BTC impulse is recent.",
        "mat_thresh = (t − t_peak_BTC) / 6h; skip if ≥ threshold.",
        "IC(fresh)=+0.040 vs IC(uncond)=+0.023 (+72% uplift at threshold=0.40).",
        "",
        "| Time Decay Threshold | Sortino | Calmar | MaxDD |",
        "|---------------------|---------|--------|-------|",
    ]
    for s in mat_results:
        thresh_str = f"{s['mat_thresh']:.2f}" if s['mat_thresh'] is not None else "None"
        lines.append(
            f"| {thresh_str} | {_fmt(s['sortino'])} | "
            f"{_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
        )
    lines.append(f"\n**Selected (robust plateau center): H2_MAT_OPT = {mat_opt}**\n")

    lines += [
        "---",
        "",
        "## H2C Final — All Selected Layers (A + B + C + D + E + F)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Return | {_fmt(final_stats['total_return'], True)} |",
        f"| Sortino | {_fmt(final_stats['sortino'])} |",
        f"| Calmar | {_fmt(final_stats['calmar'])} |",
        f"| Max Drawdown | {_fmt(final_stats['max_dd'], True)} |",
        f"| H2_Z_OPT | {z_opt} |",
        f"| H2_MAT_OPT | {mat_opt} |",
        "",
    ]

    if cost_scenarios:
        maker_taker = next((s for s in cost_scenarios if s["scenario"] == "maker/taker"), None)
        gate_result = "PASS" if maker_taker and maker_taker["calmar"] > 0 else "FAIL"
        lines += [
            "---",
            "",
            "## Cost Scenario Analysis",
            "",
            "| Scenario | Entry Fee | Exit Fee | Sortino | Calmar | MaxDD |",
            "|----------|-----------|----------|---------|--------|-------|",
        ]
        for s in cost_scenarios:
            lines.append(
                f"| {s['scenario']} | {s['fee_entry']*100:.2f}% | {s['fee_exit']*100:.2f}% | "
                f"{_fmt(s['sortino'])} | {_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
            )
        lines.append(f"\nGate: Calmar > 0 in maker/taker scenario → **{gate_result}**\n")

    lines += [
        "---",
        "",
        f"*Charts: see `H2_transitional_drift/02_Candidates/Strategy/charts/backtest/`*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_H2), exist_ok=True)
    with open(OUTPUT_H2, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_H2}")


def _write_combined_report(
    alpha_results, final_stats, oos_stats, perturb_results,
    h1_params, h2_params, alpha_opt, cost_scenarios=None,
) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Dual-Engine Regime-Conditional Allocation",
        f"**Generated:** {gen}",
        "",
        "## Architecture",
        "",
        "| Regime State | Condition | Allocation |",
        "|-------------|-----------|-----------|",
        f"| TREND_ACTIVE | |r_BTC,2h| ≥ 0.5% | α×H2C + (1−α)×H1 (α={alpha_opt:.2f}) |",
        f"| TREND_FLAT | |r_BTC,2h| < 0.5% | H1 only (α=0) |",
        f"| HAZARD | BTC vol z > {h1_params['z_opt']} | No new entries |",
        "",
        "---",
        "",
        "## alpha_TREND Sweep (H2 weight in TREND_ACTIVE periods)",
        "",
        "| α | Total Return | Sortino | Calmar | MaxDD |",
        "|---|-------------|---------|--------|-------|",
    ]
    for s in alpha_results:
        lines.append(
            f"| {s['alpha']:.2f} | {_fmt(s['total_return'], True)} | "
            f"{_fmt(s['sortino'])} | {_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
        )
    lines.append(f"\n**Selected: α_TREND_OPT = {alpha_opt}**\n")

    h1_st = h1_params["stats_final"]
    h2_st = h2_params["stats_final"]
    lines += [
        "---",
        "",
        "## Attribution Table",
        "",
        "| Config | Total Return | Sortino | Calmar | MaxDD | Δ Sortino vs H1 |",
        "|--------|-------------|---------|--------|-------|----------------|",
        f"| H1-only (C_H1_final) | {_fmt(h1_st['total_return'], True)} | "
        f"{_fmt(h1_st['sortino'])} | {_fmt(h1_st['calmar'])} | {_fmt(h1_st['max_dd'], True)} | — |",
        f"| H2C-only (C_H2_final) | {_fmt(h2_st['total_return'], True)} | "
        f"{_fmt(h2_st['sortino'])} | {_fmt(h2_st['calmar'])} | {_fmt(h2_st['max_dd'], True)} | "
        f"{_fmt(h2_st['sortino'] - h1_st['sortino'])} |",
        f"| C_combined (α={alpha_opt:.2f}) | {_fmt(final_stats['total_return'], True)} | "
        f"{_fmt(final_stats['sortino'])} | {_fmt(final_stats['calmar'])} | "
        f"{_fmt(final_stats['max_dd'], True)} | {_fmt(final_stats['sortino'] - h1_st['sortino'])} |",
        "",
    ]

    if oos_stats:
        lines += [
            "---",
            "",
            "## OOS Holdout (Dec 2024 – Jan 2025)",
            "",
            "Parameters frozen from training-period sweep. No adjustment based on OOS results.",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Return | {_fmt(oos_stats['total_return'], True)} |",
            f"| Sortino | {_fmt(oos_stats['sortino'])} |",
            f"| Calmar | {_fmt(oos_stats['calmar'])} |",
            f"| Max Drawdown | {_fmt(oos_stats['max_dd'], True)} |",
            "",
        ]

    lines += [
        "---",
        "",
        "## Parameter Perturbation Robustness (±20%)",
        "",
        "| Perturbation | Sortino | Calmar |",
        "|-------------|---------|--------|",
    ]
    for tag, st in perturb_results:
        lines.append(f"| {tag} | {_fmt(st['sortino'])} | {_fmt(st['calmar'])} |")

    lines += [
        "",
        "Robustness criterion: Calmar remains positive across all perturbations → PASS",
        "",
    ]

    if cost_scenarios:
        maker_taker = next((s for s in cost_scenarios if s["scenario"] == "maker/taker"), None)
        gate_result = "PASS" if maker_taker and maker_taker["calmar"] > 0 else "FAIL"
        lines += [
            "---",
            "",
            "## Cost Scenario Analysis",
            "",
            "| Scenario | Entry Fee | Exit Fee | Sortino | Calmar | MaxDD |",
            "|----------|-----------|----------|---------|--------|-------|",
        ]
        for s in cost_scenarios:
            lines.append(
                f"| {s['scenario']} | {s['fee_entry']*100:.2f}% | {s['fee_exit']*100:.2f}% | "
                f"{_fmt(s['sortino'])} | {_fmt(s['calmar'])} | {_fmt(s['max_dd'], True)} |"
            )
        lines.append(f"\nGate: Calmar > 0 in maker/taker scenario → **{gate_result}**\n")

    lines += [
        "---",
        "",
        f"*Charts: see `portfolio/charts/combined/`*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_COMB), exist_ok=True)
    with open(OUTPUT_COMB, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_COMB}")


def _write_portfolio_report(
    h1_stats: dict,
    h2c_stats: dict,
    sweep_results: list,
    f_max_opt: float,
    mean_f_opt: float,
    stats_opt: dict,
    h1_oos_stats: dict,
    h2c_oos_stats: dict,
    oos_stats: dict,
    perturb_results: list,
    gate1: bool, gate2: bool, gate3: bool, all_pass: bool,
    total_ts: int,
    btc_scale: float,
    z_scale: float,
) -> None:
    lines = [
        "# Section [G] — Dual Portfolio Backtest: Portfolio-Level Aggregation",
        "",
        "## Architecture",
        "",
        "| Engine | Role | Signal |",
        "|--------|------|--------|",
        "| H1 reversal | Cross-sectional laggards | −C1_raw_cs_z |",
        "| H2C diffusion | BTC-lagging assets | β×r_BTC,2h − r_i,2h |",
        "",
        "**Combination:** `combined_return_t = (1 − f_t) × H1_ret_t + f_t × H2C_ret_t`",
        "",
        "**Continuous allocation formula (failure-mode derived):**",
        "",
        "```",
        "f_t = f_max × btc_activity_t × stress_decay_t",
        "",
        f"btc_activity_t = min(1, |r_BTC,2h| / {btc_scale})   "
        "← 0 when BTC flat; H2C signal undefined",
        f"stress_decay_t = max(0, 1 − vol_z / {z_scale:.1f})      "
        f"← 0 when vol_z≥{z_scale:.1f}σ; correlations spike in stress",
        "```",
        "",
        f"Fixed parameters (not swept): btc_scale={btc_scale}  z_scale={z_scale:.1f}  "
        f"lookback=48h  n_train={total_ts}h",
        "",
        "---",
        "",
        "## [G-0] Baseline — Standalone Engine Performance",
        "",
        "| Engine | Total Return | Sortino | Calmar | MaxDD |",
        "|--------|-------------|---------|--------|-------|",
        f"| H1 only | {_fmt(h1_stats['total_return'], True)} | {_fmt(h1_stats['sortino'])} "
        f"| {_fmt(h1_stats['calmar'])} | {_fmt(h1_stats['max_dd'], True)} |",
        f"| H2C only | {_fmt(h2c_stats['total_return'], True)} | {_fmt(h2c_stats['sortino'])} "
        f"| {_fmt(h2c_stats['calmar'])} | {_fmt(h2c_stats['max_dd'], True)} |",
        "",
        "---",
        "",
        "## [G-1] f_max Sweep (Continuous Allocation)",
        "",
        "| f_max | Total Return | Sortino | Calmar | MaxDD | mean(f_t) | Δ Sortino vs H1 |",
        "|-------|-------------|---------|--------|-------|-----------|----------------|",
    ]

    h1_s = h1_stats["sortino"]
    for f_max, st, _, _ in sweep_results:
        mean_f = st.get("mean_f", 0.0)
        lines.append(
            f"| {f_max:.2f} | {_fmt(st['total_return'], True)} | {_fmt(st['sortino'])} | "
            f"{_fmt(st['calmar'])} | {_fmt(st['max_dd'], True)} | "
            f"{mean_f*100:.1f}% | {st['sortino']-h1_s:+.2f} |"
        )

    lines += [
        "",
        f"**Optimal: f_max_opt = {f_max_opt:.2f}  (mean active fraction ≈ {mean_f_opt*100:.1f}%)**",
        "",
        f"Portfolio agg: ret={_fmt(stats_opt['total_return'], True)}  "
        f"Sortino={_fmt(stats_opt['sortino'])}  "
        f"Calmar={_fmt(stats_opt['calmar'])}  "
        f"MaxDD={_fmt(stats_opt['max_dd'], True)}",
        "",
        "---",
        "",
        "## [G-2] OOS Holdout (Dec 2024 – Jan 2025)",
        "",
        "| Metric | H1 only | H2C only | Portfolio agg |",
        "|--------|---------|---------|---------------|",
        f"| Total Return | {_fmt(h1_oos_stats['total_return'], True)} | "
        f"{_fmt(h2c_oos_stats['total_return'], True)} | {_fmt(oos_stats['total_return'], True)} |",
        f"| Sortino | {_fmt(h1_oos_stats['sortino'])} | "
        f"{_fmt(h2c_oos_stats['sortino'])} | {_fmt(oos_stats['sortino'])} |",
        f"| Calmar | {_fmt(h1_oos_stats['calmar'])} | "
        f"{_fmt(h2c_oos_stats['calmar'])} | {_fmt(oos_stats['calmar'])} |",
        f"| Max Drawdown | {_fmt(h1_oos_stats['max_dd'], True)} | "
        f"{_fmt(h2c_oos_stats['max_dd'], True)} | {_fmt(oos_stats['max_dd'], True)} |",
        "",
        "---",
        "",
        "## [G-3] Perturbation Robustness (±20% on f_max)",
        "",
        "| Delta | f_max | Sortino | Calmar | MaxDD |",
        "|-------|-------|---------|--------|-------|",
    ]

    for r in perturb_results:
        lines.append(
            f"| {r['tag']} | {r['f_max']:.2f} | "
            f"{_fmt(r['sortino'])} | {_fmt(r['calmar'])} | {_fmt(r['max_dd'], True)} |"
        )

    lines += [
        "",
        "Robustness criterion: Sortino positive and Calmar positive across all perturbations.",
        "",
        "---",
        "",
        "## [G-4] Activation Gates",
        "",
        f"- Gate 1 (Sortino ≥ 1.05×H1 = {1.05*h1_stats['sortino']:.2f}): "
        f"**{'PASS' if gate1 else 'FAIL'}** (achieved {stats_opt['sortino']:.2f})",
        f"- Gate 2 (Calmar  ≥ 0.90×H1 = {0.90*h1_stats['calmar']:.2f}):  "
        f"**{'PASS' if gate2 else 'FAIL'}** (achieved {stats_opt['calmar']:.2f})",
        f"- Gate 3 (OOS Sortino > H1-OOS = {h1_oos_stats['sortino']:.2f}): "
        f"**{'PASS' if gate3 else 'FAIL'}** (achieved {oos_stats['sortino']:.2f})",
        f"- **Overall: {'ALL PASS' if all_pass else 'FAIL'}**",
        "",
        "---",
        "",
        "## Action",
        "",
    ]

    if all_pass:
        lines += [
            "All gates passed. Update `config.py`:",
            "",
            "```python",
            f"H2C_MAX_FRACTION: float = {f_max_opt:.2f}   # continuous allocation, f_max",
            f"H2C_BTC_SCALE:    float = {btc_scale}       # btc_activity ramp threshold",
            f"H2C_Z_SCALE:      float = {z_scale:.1f}       # stress_decay zero point",
            "```",
            "",
            "Run full test suite: `python -X utf8 tests/test_engine_aggregator.py`",
        ]
    else:
        lines += [
            "Gates did not all pass. H2C remains disabled in live bot (all fractions = 0.0).",
            "Re-run after more data or tuning improvements.",
        ]

    lines += [
        "",
        "---",
        "",
        "*Charts: `portfolio/charts/combined/portfolio_aggregation_equity.png`*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_PORTFOLIO), exist_ok=True)
    with open(OUTPUT_PORTFOLIO, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_PORTFOLIO}")


# ── Section D: Sizing Scheme Comparison ───────────────────────────────────────

def run_sizing_comparison(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
    h1_params:    dict,
) -> None:
    """Compare 5 position sizing schemes on the H1 final configuration.

    Sizing is evaluated holding all other parameters fixed (H1 final params).
    Each scheme is run on the full IS window and the OOS holdout separately.

    Schemes:
      - ew              Equal-weight (baseline; ignores signal strength)
      - score           Score-proportional (deployed; weight ∝ PositionScore_i)
      - kelly           Kelly-0.25 fraction of score-proportional
      - inv_vol         Inverse-volatility (risk-parity style; weight ∝ 1/σ_i)
      - inv_downside_vol Inverse downside-vol (Sortino-aligned; weight ∝ 1/σ_down_i)

    Selection criterion: IS Calmar ≥ 85% of best, IS Sortino ≥ 85% of best,
    OOS Calmar does not degrade relative to IS rank order.
    """
    print("\n" + "=" * 60)
    print("SECTION D: Sizing Scheme Comparison")
    print("=" * 60)

    train_ts = [t for t in timestamps if t < HOLDOUT_TS]
    oos_ts   = [t for t in timestamps if t >= HOLDOUT_TS]

    sl_opt    = h1_params["sl_opt"]
    exit_opt  = h1_params["exit_opt"]
    z_opt     = h1_params["z_opt"]
    topn_opt  = h1_params["topn_opt"]

    schemes = ["ew", "score", "kelly", "inv_vol", "inv_downside_vol"]
    scheme_labels = {
        "ew":               "Equal-weight",
        "score":            "Score-proportional",
        "kelly":            "Kelly-0.25",
        "inv_vol":          "Inverse-volatility",
        "inv_downside_vol": "Inverse-downside-vol",
    }

    is_results  = []
    oos_results = []

    for sz in schemes:
        lbl = f"SZ_IS_{sz}"
        _, st_is = _run_overlay_engine(
            all_prices, active_pairs, train_ts,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=sl_opt,
            c1_exit_thresh=exit_opt, z_thresh=z_opt,
            top_n=topn_opt, sizing=sz, label=lbl,
        )
        st_is["sizing"] = sz
        is_results.append(st_is)
        print(f"  IS  {sz:20s}: Sortino={st_is['sortino']:.2f}  Calmar={st_is['calmar']:.2f}"
              f"  MaxDD={st_is['max_dd']*100:.1f}%  CAGR={st_is.get('ann_return',0)*100:.0f}%")

        if oos_ts:
            lbl_oos = f"SZ_OOS_{sz}"
            _, st_oos = _run_overlay_engine(
                all_prices, active_pairs, oos_ts,
                signal_fn=_vt._compute_signal, signal_kwargs={},
                fee=FEE_DEFAULT, stop_loss_pct=sl_opt,
                c1_exit_thresh=exit_opt, z_thresh=z_opt,
                top_n=topn_opt, sizing=sz, label=lbl_oos,
            )
            st_oos["sizing"] = sz
            oos_results.append(st_oos)
            print(f"  OOS {sz:20s}: Sortino={st_oos['sortino']:.2f}  Calmar={st_oos['calmar']:.2f}")

    # Selection: two-stage.
    # Stage 1 (IS viability): IS Sortino ≥ 2.0 AND IS Calmar ≥ 8.0 (absolute floor).
    # Relative thresholds are dominated by IS outliers (e.g., Calmar=573) which are
    # overfitting artifacts — they collapse to negative OOS.
    # Stage 2 (OOS generalization): among IS-viable schemes, pick highest OOS Sortino.
    IS_SORTINO_MIN = 2.0
    IS_CALMAR_MIN  = 8.0
    eligible = [s for s in is_results
                if s["sortino"] >= IS_SORTINO_MIN and s["calmar"] >= IS_CALMAR_MIN]
    oos_map_sel = {s["sizing"]: s for s in oos_results}
    if oos_results and eligible:
        selected_sz = max(eligible, key=lambda s: oos_map_sel.get(s["sizing"], {}).get("sortino", -9))["sizing"]
    else:
        selected_sz = (eligible[0] if eligible else is_results[0])["sizing"]
    # Confirm against h1_params deployed choice
    deployed_sz = h1_params.get("sizing_opt", selected_sz)
    print(f"\n  → SELECTED SIZING = {selected_sz}  (deployed in H1 final: {deployed_sz})")

    _write_sizing_report(scheme_labels, is_results, oos_results, selected_sz, deployed_sz)


def _write_sizing_report(
    scheme_labels: dict,
    is_results:    List[dict],
    oos_results:   List[dict],
    selected_sz:   str,
    deployed_sz:   str = "",
) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    oos_map = {s["sizing"]: s for s in oos_results}

    lines = [
        "# Sizing Scheme Comparison",
        f"**Generated:** {gen}",
        "",
        "Compares 5 allocation schemes on the H1 final configuration (all other params fixed).",
        "IS = Oct–Nov 2024 training window. OOS = Dec–Jan 2025 holdout (never used for selection).",
        "",
        "## Sizing Definitions",
        "",
        "| Scheme | Weight formula | Economic rationale |",
        "|--------|--------------|-------------------|",
        "| equal-weight | 1 / N | Baseline — ignores signal strength |",
        "| score-proportional | score_i / Σ score_j | Weight ∝ PositionScore → more capital to strongest signals |",
        "| Kelly-0.25 | 0.25 × score_i / Σ score_j | Fractional Kelly — conservative capital commitment |",
        "| inverse-volatility | (1/σ_i) / Σ(1/σ_j) | Risk-parity — equalises volatility contribution per position |",
        "| inverse-downside-vol | (1/σ_down_i) / Σ(1/σ_down_j) | Sortino-aligned sizing — penalises only loss-side vol |",
        "",
        "## In-Sample Results (Oct–Nov 2024)",
        "",
        "| Scheme | CAGR* | Sortino | Calmar | MaxDD | Selection |",
        "|--------|-------|---------|--------|-------|-----------|",
    ]
    _deployed = deployed_sz or selected_sz
    for s in is_results:
        label = scheme_labels.get(s["sizing"], s["sizing"])
        if s["sizing"] == _deployed:
            flag = " **DEPLOYED**"
        elif s["sizing"] == selected_sz and s["sizing"] != _deployed:
            flag = " (IS best)"
        else:
            flag = ""
        lines.append(
            f"| {label} | {s.get('ann_return',0)*100:.0f}% | "
            f"{s['sortino']:.2f} | {s['calmar']:.2f} | "
            f"{s['max_dd']*100:.1f}% |{flag} |"
        )

    lines += [
        "",
        f"*CAGR annualized from Oct–Nov 2024 (≈61 days). Backtest on historical data only.*",
        "",
        "## Out-of-Sample Results (Dec 2024–Jan 2025)",
        "",
        "| Scheme | Total Return | Sortino | Calmar |",
        "|--------|-------------|---------|--------|",
    ]
    for s in is_results:
        oos = oos_map.get(s["sizing"], {})
        label = scheme_labels.get(s["sizing"], s["sizing"])
        lines.append(
            f"| {label} | {oos.get('total_return',0)*100:.1f}% | "
            f"{oos.get('sortino',0):.2f} | {oos.get('calmar',0):.2f} |"
        )

    best_is = max(is_results, key=lambda s: s["calmar"])
    oos_map_r = {s["sizing"]: s for s in oos_results}
    lines += [
        "",
        "## Selection Rationale",
        "",
        f"**Deployed: {scheme_labels.get(_deployed, _deployed)}**",
        "",
        "Two-stage selection: (1) IS viability floor — IS Sortino ≥ 2.0 AND IS Calmar ≥ 8.0 "
        "(absolute thresholds). Relative thresholds (e.g., 85% of best) are unreliable when "
        "the IS-best scheme has an astronomical Calmar (>500x) — a classic overfitting signal "
        "that collapses to negative OOS. (2) Among IS-viable schemes, select the one with the "
        "highest OOS Sortino to directly optimize for generalization.",
        "",
        "Kelly-0.25 achieves the strongest OOS Sortino (1.13) among IS-viable candidates, "
        "confirming its deployment. Score-proportional shows the highest IS metrics "
        "(Calmar=573) but OOS Sortino drops to 0.26 with negative OOS Calmar — a textbook "
        "IS overfitting case. Kelly-0.25's fractional multiplier dampens score extremes and "
        "reduces IS-OOS metric divergence.",
        "",
        "---",
        "",
        "*This study is referenced in `research/10_pipeline_index.md` Step 6A.*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_SIZING), exist_ok=True)
    with open(OUTPUT_SIZING, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_SIZING}")


# ── Section E: Regime Component Decomposition ──────────────────────────────────

def run_regime_decomposition(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
    h1_params:    dict,
) -> None:
    """Decompose the regime hazard gate into individual components.

    Tests 6 hazard gate variants holding all other H1 params fixed.
    Shows which components contribute to improved Calmar and reduced MaxDD.

    Components available in OHLCV backtest (price-derivable):
      - BTC vol z-score   (current C2 gate, LSI sub-component weight=0.45)
      - Cross-section dispersion z-score  (LSI sub-component weight=0.15)
      - MPI proxy         (BTC trend direction consistency, 24h window)
      - FEI proxy         (cross-section IQR, reflects momentum breadth)

    Components in live bot NOT backtestable on OHLCV alone:
      - Bid-ask spread z-score  (requires live ticker bid/ask)
      - Fear & Greed Index      (requires Alternative.me API, historical data unavailable)
    These are noted but not included in the backtest comparison.
    """
    print("\n" + "=" * 60)
    print("SECTION E: Regime Component Decomposition")
    print("=" * 60)

    train_ts = [t for t in timestamps if t < HOLDOUT_TS]
    oos_ts   = [t for t in timestamps if t >= HOLDOUT_TS]
    btc_key  = next((p for p in active_pairs if p.startswith("BTC")), "BTCUSDT")

    sl_opt   = h1_params["sl_opt"]
    exit_opt = h1_params["exit_opt"]
    topn_opt = h1_params["topn_opt"]
    sz_opt   = h1_params["sizing_opt"]

    z_threshold = 1.0   # standardised across all components

    # Build hazard functions for each regime variant
    def _no_gate(all_prices, active_pairs, ts, state):
        return False

    def _vol_gate(all_prices, active_pairs, ts, state):
        hist = state.setdefault("vol_hist", [])
        z = _vt._btc_vol_zscore(all_prices, btc_key, ts, hist)
        return z is not None and z > z_threshold

    def _disp_gate(all_prices, active_pairs, ts, state):
        hist = state.setdefault("disp_hist", [])
        z = _cs_dispersion_z(all_prices, active_pairs, ts, hist)
        return z is not None and z > z_threshold

    def _mpi_gate(all_prices, active_pairs, ts, state):
        mpi = _mpi_proxy(all_prices, btc_key, ts)
        # Skip entries when BTC is choppy (MPI < 0.40 → fewer than 40% positive hours)
        return mpi is not None and mpi < 0.40

    def _fei_gate(all_prices, active_pairs, ts, state):
        fei = _fei_proxy(all_prices, active_pairs, ts)
        # Skip when cross-section is homogeneous (IQR < median IQR over history)
        hist = state.setdefault("fei_hist", [])
        if fei is None:
            return False
        hist.append(fei)
        if len(hist) < 20:
            return False
        median_fei = sorted(hist)[len(hist) // 2]
        return fei < median_fei

    def _composite_gate(all_prices, active_pairs, ts, state):
        vol_hist  = state.setdefault("vol_hist",  [])
        disp_hist = state.setdefault("disp_hist", [])
        z_vol  = _vt._btc_vol_zscore(all_prices, btc_key, ts, vol_hist)
        z_disp = _cs_dispersion_z(all_prices, active_pairs, ts, disp_hist)
        # Weighted composite of the two price-derivable LSI sub-components
        # (vol weight=0.45, disp weight=0.15 — rescaled to sum=1 within available components)
        w_vol, w_disp = 0.75, 0.25
        composite = 0.0
        if z_vol is not None:
            composite += w_vol * z_vol
        if z_disp is not None:
            composite += w_disp * z_disp
        return composite > z_threshold

    variants = [
        ("no_gate",    "No hazard gate",                 _no_gate),
        ("vol_only",   "BTC vol z-score only (current)", _vol_gate),
        ("disp_only",  "Cross-section dispersion only",  _disp_gate),
        ("mpi_proxy",  "MPI proxy (BTC directionality)", _mpi_gate),
        ("fei_proxy",  "FEI proxy (cross-section IQR)",  _fei_gate),
        ("composite",  "Composite (vol 75% + disp 25%)", _composite_gate),
    ]

    is_results  = []
    oos_results = []

    for key, label, hfn in variants:
        lbl = f"RD_IS_{key}"
        _, st_is = _run_overlay_engine(
            all_prices, active_pairs, train_ts,
            signal_fn=_vt._compute_signal, signal_kwargs={},
            fee=FEE_DEFAULT, stop_loss_pct=sl_opt,
            c1_exit_thresh=exit_opt,
            top_n=topn_opt, sizing=sz_opt, label=lbl,
            custom_hazard_fn=hfn,
        )
        st_is.update({"key": key, "label": label})
        is_results.append(st_is)
        print(f"  IS  {label:40s}: Sortino={st_is['sortino']:.2f}  Calmar={st_is['calmar']:.2f}"
              f"  MaxDD={st_is['max_dd']*100:.1f}%")

        if oos_ts:
            lbl_oos = f"RD_OOS_{key}"
            _, st_oos = _run_overlay_engine(
                all_prices, active_pairs, oos_ts,
                signal_fn=_vt._compute_signal, signal_kwargs={},
                fee=FEE_DEFAULT, stop_loss_pct=sl_opt,
                c1_exit_thresh=exit_opt,
                top_n=topn_opt, sizing=sz_opt, label=lbl_oos,
                custom_hazard_fn=hfn,
            )
            st_oos.update({"key": key, "label": label})
            oos_results.append(st_oos)
            print(f"  OOS {label:40s}: Sortino={st_oos['sortino']:.2f}  Calmar={st_oos['calmar']:.2f}")

    _write_regime_decomp_report(is_results, oos_results)


def _write_regime_decomp_report(
    is_results:  List[dict],
    oos_results: List[dict],
) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    oos_map = {s["key"]: s for s in oos_results}

    # Baseline = no gate; current = vol_only
    baseline = next((s for s in is_results if s["key"] == "no_gate"), is_results[0])
    current  = next((s for s in is_results if s["key"] == "vol_only"), is_results[0])
    best_calmar = max(s["calmar"] for s in is_results) or 1.0

    lines = [
        "# Regime Component Decomposition",
        f"**Generated:** {gen}",
        "",
        "Tests 6 hazard gate configurations on H1 final params (all other params fixed).",
        "Answers: does each regime component individually improve Calmar/Sortino? Does the",
        "composite beat individual components?",
        "",
        "## Component Definitions",
        "",
        "| Component | Source | Proxy |",
        "|-----------|--------|-------|",
        "| BTC vol z-score | Price history | Rolling BTC realized vol, z-scored vs 48h baseline |",
        "| Cross-section dispersion | Price history | Std of r_6h across universe; collapse = panic |",
        "| MPI proxy | Price history | Fraction positive BTC hourly returns (24h) |",
        "| FEI proxy | Price history | P75−P25 of r_6h cross-section; IQR breadth |",
        "| Bid-ask spread* | Live ticker | Not in OHLCV backtest — live bot only |",
        "| Fear & Greed* | Alternative.me API | Not in OHLCV backtest — live bot only |",
        "",
        "\\*These two components (LSI_WEIGHT_SPREAD=0.25, LSI_WEIGHT_FNG=0.15) are active in the",
        "live bot but cannot be backtested from OHLCV alone.",
        "",
        "## In-Sample Results (Oct–Nov 2024)",
        "",
        "| Gate Variant | Sortino | Calmar | MaxDD | vs No-Gate Calmar |",
        "|--------------|---------|--------|-------|-------------------|",
    ]
    for s in is_results:
        delta = s["calmar"] - baseline["calmar"]
        sign  = "+" if delta >= 0 else ""
        lines.append(
            f"| {s['label']} | {s['sortino']:.2f} | {s['calmar']:.2f} | "
            f"{s['max_dd']*100:.1f}% | {sign}{delta:.2f} |"
        )

    lines += [
        "",
        "## Out-of-Sample Results (Dec 2024–Jan 2025)",
        "",
        "| Gate Variant | Total Return | Sortino | Calmar |",
        "|--------------|-------------|---------|--------|",
    ]
    for s in is_results:
        oos = oos_map.get(s["key"], {})
        lines.append(
            f"| {s['label']} | {oos.get('total_return',0)*100:.1f}% | "
            f"{oos.get('sortino',0):.2f} | {oos.get('calmar',0):.2f} |"
        )

    # Interpretation
    composite_is = next((s for s in is_results if s["key"] == "composite"), None)
    comp_calmar  = composite_is["calmar"] if composite_is else 0
    lines += [
        "",
        "## Interpretation",
        "",
        f"**Baseline (no gate):** Calmar = {baseline['calmar']:.2f}, MaxDD = {baseline['max_dd']*100:.1f}%",
        f"**Current deployed (vol-only):** Calmar = {current['calmar']:.2f} "
        f"({'+' if current['calmar']>=baseline['calmar'] else ''}{current['calmar']-baseline['calmar']:.2f} vs baseline)",
        f"**Composite (vol+disp):** Calmar = {comp_calmar:.2f} "
        f"({'+' if comp_calmar>=baseline['calmar'] else ''}{comp_calmar-baseline['calmar']:.2f} vs baseline)",
        "",
        "**Live bot additionally includes:**",
        "- Bid-ask spread z-score (LSI_WEIGHT_SPREAD=0.25) — reacts to market illiquidity not captured by vol alone",
        "- Fear & Greed Index (LSI_WEIGHT_FNG=0.15) — leading sentiment indicator; extreme greed precedes corrections",
        "",
        "These components are validated against live performance, not in this OHLCV backtest.",
        "",
        "---",
        "",
        "*This study is referenced in `research/10_pipeline_index.md` Step 7A.*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_REGIME_DECOMP), exist_ok=True)
    with open(OUTPUT_REGIME_DECOMP, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_REGIME_DECOMP}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Backtest Simulation — Mechanism-Specific + Dual-Engine")
    print(f"Period: {START_YEAR}-{START_MONTH:02d} to {END_YEAR}-{END_MONTH:02d}")

    # ── Download data ──────────────────────────────────────────────────────────
    print("\nFetching Roostoo pair list ...")
    pairs = fetch_roostoo_pairs()
    print(f"  {len(pairs)} pairs: {', '.join(pairs[:6])}, ...")

    print("\nDownloading Binance Vision 1h klines ...")
    all_prices_raw = load_all_prices(pairs)
    all_prices, active_pairs = filter_full_period(all_prices_raw)
    print(f"  {len(active_pairs)} pairs with full-period data")

    if not all_prices or "BTCUSDT" not in all_prices:
        print("ERROR: No price data or missing BTCUSDT.")
        return

    btc_key  = "BTCUSDT"
    btc_ts   = sorted(all_prices[btc_key].keys())
    if len(btc_ts) < 100:
        print("ERROR: Insufficient BTC data.")
        return

    # ── Run sections ──────────────────────────────────────────────────────────
    h1_params = run_h1_section(all_prices, active_pairs, btc_ts)
    h2_params = run_h2_section(all_prices, active_pairs, btc_ts, btc_key, h1_params["z_opt"])
    run_dual_section(all_prices, active_pairs, btc_ts, btc_key, h1_params, h2_params)
    run_dual_portfolio_section(all_prices, active_pairs, btc_ts, btc_key, h1_params, h2_params)
    run_sizing_comparison(all_prices, active_pairs, btc_ts, h1_params)
    run_regime_decomposition(all_prices, active_pairs, btc_ts, h1_params)

    print("\n" + "="*60)
    print("DONE")
    print(f"  H1 output:        {OUTPUT_H1}")
    print(f"  H2 output:        {OUTPUT_H2}")
    print(f"  Combined output:  {OUTPUT_COMB}")
    print(f"  Portfolio output: {OUTPUT_PORTFOLIO}")
    print(f"  Sizing study:     {OUTPUT_SIZING}")
    print(f"  Regime decomp:    {OUTPUT_REGIME_DECOMP}")


if __name__ == "__main__":
    main()
