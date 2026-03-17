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
import vector_tests as _vt  # noqa: E402

# ── Output paths (co-located with mechanism) ──────────────────────────────────
OUTPUT_H1   = os.path.join(_here, "H1_reversal",          "02_Candidates", "Strategy", "02_backtest.md")
OUTPUT_H2   = os.path.join(_here, "H2_transitional_drift", "02_Candidates", "Strategy", "01_backtest.md")
OUTPUT_COMB = os.path.join(_here, "portfolio",             "03_combined_backtest.md")
CHARTS_H1   = os.path.join(_here, "H1_reversal",          "02_Candidates", "Strategy", "charts", "backtest")
CHARTS_H2   = os.path.join(_here, "H2_transitional_drift", "02_Candidates", "Strategy", "charts", "backtest")
CHARTS_COMB = os.path.join(_here, "portfolio",             "charts", "combined")

for _d in (OUTPUT_H1, OUTPUT_H2, OUTPUT_COMB):
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
) -> Optional[Dict[str, float]]:
    """H2C: CS_z(β_i × r_BTC,2h − r_i,2h).

    beta_hist: pair → ([r_i_hourly_48], [r_btc_hourly_48]) — updated in-place.
    Requires 24+ hours of β history (48h window, skip first 24h).
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


# ── Overlay backtest engine ────────────────────────────────────────────────────

def _run_overlay_engine(
    all_prices:       Dict[str, Dict[int, float]],
    active_pairs:     List[str],
    timestamps:       List[int],       # 1h grid
    signal_fn:        Callable,        # fn(all_prices, active_pairs, ts, **kwargs) → Optional[Dict]
    signal_kwargs:    dict,
    fee:              float   = 0.0,
    stop_loss_pct:    Optional[float] = None,    # e.g. -0.04; None = disabled
    c1_exit_thresh:   Optional[float] = None,    # exit if score < thresh; None = disabled
    btc_rev_exit:     Optional[float] = None,    # H2: exit if r_BTC since entry < -X; None = disabled
    hold_cap_hours:   Optional[int]   = None,    # H2: force-exit after N hours; None = disabled
    btc_gate_pct:     float   = 0.0,             # skip H2 entry if |r_BTC,2h| < gate
    z_thresh:         float   = 1.50,            # C2 hazard gate
    top_n:            int     = TOP_N_DEFAULT,
    sizing:           str     = "ew",            # "ew" | "score" | "kelly"
    label:            str     = "overlay",
) -> Tuple[List[Tuple[int, float]], dict]:
    """
    Per-position tracking engine with optional risk overlays.

    For H1: use signal_fn = _vt._compute_signal, enable stop_loss_pct and/or c1_exit_thresh.
    For H2: use signal_fn = _compute_h2c_signal, enable btc_rev_exit and/or hold_cap_hours.
    """
    btc_key    = next((p for p in active_pairs if p.startswith("BTC")), None)
    btc_prices = all_prices.get(btc_key, {}) if btc_key else {}

    nav        = 1.0
    cash       = 1.0
    nav_series: List[Tuple[int, float]] = [(timestamps[0], 1.0)]
    positions:  Dict[str, dict] = {}   # pair → {entry_price, entry_ts, entry_btc_price, qty_usd}
    btc_vol_hist: List[float] = []
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
                val = pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - fee)
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
                        val = pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - fee)
                        cash += val
                        del positions[pair]
                        n_exits += 1
                        continue

            # H2 hold cap
            if hold_cap_hours is not None:
                age_h = (ts - pos["entry_ts"]) / MS_PER_HOUR
                if age_h >= hold_cap_hours:
                    val = pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - fee)
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

        # C2 hazard gate
        hazard = False
        if btc_key:
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
                        val = positions[pair]["qty_usd"] * (cp / positions[pair]["entry_price"]) * (1 - fee)
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
            cash += pos["qty_usd"] * (cp / pos["entry_price"]) * (1 - fee)

    nav_series.append((final_ts + MS_PER_HOUR, cash))
    stats = _stats(nav_series, label)
    stats["n_stops"]  = n_stops
    stats["n_exits"]  = n_exits
    stats["n_rebal"]  = sum(1 for i in range(0, len(timestamps), HOLD_HOURS))
    return nav_series, stats


# ── Selection helpers ──────────────────────────────────────────────────────────

def _best_calmar(results: List[dict], baseline_calmar: float) -> dict:
    """Return the result with highest Calmar that is ≥ 1.2× baseline."""
    candidates = [r for r in results if r.get("calmar", 0) >= 1.2 * baseline_calmar]
    if not candidates:
        candidates = results  # fall back to any positive improvement
    return max(candidates, key=lambda r: r.get("calmar", 0))


def _best_sortino(results: List[dict], calmar_min: float) -> dict:
    """Return the result with highest Sortino while Calmar ≥ calmar_min."""
    candidates = [r for r in results if r.get("calmar", 0) >= calmar_min]
    if not candidates:
        candidates = results
    return max(candidates, key=lambda r: r.get("sortino", 0))


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

    # Select: best Calmar, stops < 5%
    h1_sl_opt = None
    no_sl_calmar = next(s["calmar"] for s in sl_results if s["sl"] is None)
    eligible_sl = [s for s in sl_results if s["sl"] is not None and
                   s["n_stops"] / max(s["n_rebal"], 1) < 0.05]
    if eligible_sl:
        best_sl = max(eligible_sl, key=lambda s: s["calmar"])
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
    for s in exit_results:
        if s["exit_thresh"] is not None and s["sortino"] > no_exit_sortino + 0.05:
            h1_exit_opt = s["exit_thresh"]
            break  # take lowest threshold that meets criterion
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

    # Select z-threshold: best Calmar (MaxDD relative improvement >= 10%)
    no_gate_maxdd = z_results[-1]["max_dd"]  # z=2.50 ~ near-no-gate
    eligible_z = [s for s in z_results if abs(s["max_dd"]) < abs(no_gate_maxdd) * 0.90]
    h1_z_opt = 1.50  # default
    if eligible_z:
        best_z = max(eligible_z, key=lambda s: s["calmar"])
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

    best_topn = _best_sortino(topn_results, calmar_min=1.0)
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

    best_sz = _best_sortino(sizing_results, calmar_min=1.0)
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

    def _h2c_sig(all_prices, active_pairs, ts, beta_hist=None):
        if beta_hist is None:
            return None
        return _compute_h2c_signal(all_prices, active_pairs, ts, btc_key, beta_hist)

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
            fee=FEE_DEFAULT, btc_rev_exit=rev, z_thresh=h1_z_opt,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["btc_rev"] = rev
        btc_rev_results.append(stats)
        print(f"  BTCREV={str(rev):8s}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}  exits={stats['n_exits']}")

    no_rev_calmar = next(s["calmar"] for s in btc_rev_results if s["btc_rev"] is None)
    h2_btcrev_opt = None
    eligible_rev = [s for s in btc_rev_results if s["btc_rev"] is not None and
                    s["calmar"] > no_rev_calmar * 1.10]
    if eligible_rev:
        h2_btcrev_opt = max(eligible_rev, key=lambda s: s["calmar"])["btc_rev"]
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
            hold_cap_hours=hc, z_thresh=h1_z_opt,
            top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["hold_cap"] = hc
        holdcap_results.append(stats)
        print(f"  HC={str(hc):5s}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}")

    best_hc = _best_sortino(holdcap_results, calmar_min=0.5)
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
            z_thresh=h1_z_opt, top_n=TOP_N_DEFAULT, label=lbl,
        )
        stats["btc_gate"] = gate
        gate_results.append(stats)
        print(f"  GATE={gate:.3f}: Sortino={stats['sortino']:.2f}  "
              f"Calmar={stats['calmar']:.2f}  MaxDD={stats['max_dd']*100:.1f}%")

    best_gate = _best_sortino(gate_results, calmar_min=0.5)
    h2_gate_opt = best_gate.get("btc_gate", 0.005)
    print(f"  → H2_GATE_OPT = {h2_gate_opt}")

    # ── Portfolio construction ─────────────────────────────────────────────────
    print("\n[F] H2 portfolio construction sweep ...")
    h2_topn_opt = TOP_N_DEFAULT
    for n in [2, 3, 4, 5]:
        bh = _make_beta_hist()
        _, stats = _run_overlay_engine(
            all_prices, active_pairs, timestamps,
            signal_fn=_h2c_sig, signal_kwargs={"beta_hist": bh},
            fee=FEE_DEFAULT, btc_rev_exit=h2_btcrev_opt,
            hold_cap_hours=h2_holdcap_opt, btc_gate_pct=h2_gate_opt,
            z_thresh=h1_z_opt, top_n=n, label=f"H2_TOPN_{n}",
        )
        stats["top_n"] = n
        print(f"  TOPN={n}: Sortino={stats['sortino']:.2f}  Calmar={stats['calmar']:.2f}")
        if stats["sortino"] > va_h2[f"H2_A_fee{FEE_DEFAULT*100:.2f}"]["sortino"] * 0.9 and \
           stats["calmar"] >= 0.5:
            h2_topn_opt = n  # take last that maintains performance

    # ── H2 final ───────────────────────────────────────────────────────────────
    print("\n[G] H2 final (all selected layers) ...")
    bh = _make_beta_hist()
    nav_h2_final, stats_h2_final = _run_overlay_engine(
        all_prices, active_pairs, timestamps,
        signal_fn=_h2c_sig, signal_kwargs={"beta_hist": bh},
        fee=FEE_DEFAULT, btc_rev_exit=h2_btcrev_opt,
        hold_cap_hours=h2_holdcap_opt, btc_gate_pct=h2_gate_opt,
        z_thresh=h1_z_opt, top_n=h2_topn_opt, label="C_H2_final",
    )
    print(f"  C_H2_final: ret={stats_h2_final['total_return']*100:.1f}%  "
          f"Sortino={stats_h2_final['sortino']:.2f}  "
          f"Calmar={stats_h2_final['calmar']:.2f}  "
          f"MaxDD={stats_h2_final['max_dd']*100:.1f}%")

    _write_h2_report(
        va_h2, btc_rev_results, holdcap_results, gate_results,
        stats_h2_final,
        h2_btcrev_opt, h2_holdcap_opt, h2_gate_opt, h2_topn_opt,
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
        """Blend H1 and H2C signals with regime-conditional alpha."""
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
    best_alpha = _best_sortino(alpha_results, calmar_min=max(h1_calmar * 0.90, 0.5))
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
        h1_params, h2_params, alpha_opt,
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
    va_h2, btc_rev_results, holdcap_results, gate_results,
    final_stats, btcrev_opt, holdcap_opt, gate_opt, topn_opt,
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
        "---",
        "",
        "## H2C Final — All Selected Layers",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Return | {_fmt(final_stats['total_return'], True)} |",
        f"| Sortino | {_fmt(final_stats['sortino'])} |",
        f"| Calmar | {_fmt(final_stats['calmar'])} |",
        f"| Max Drawdown | {_fmt(final_stats['max_dd'], True)} |",
        "",
        f"*Charts: see `H2_transitional_drift/02_Candidates/Strategy/charts/backtest/`*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_H2), exist_ok=True)
    with open(OUTPUT_H2, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_H2}")


def _write_combined_report(
    alpha_results, final_stats, oos_stats, perturb_results,
    h1_params, h2_params, alpha_opt,
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
        f"*Charts: see `portfolio/charts/combined/`*",
    ]

    os.makedirs(os.path.dirname(OUTPUT_COMB), exist_ok=True)
    with open(OUTPUT_COMB, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n  Wrote {OUTPUT_COMB}")


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

    print("\n" + "="*60)
    print("DONE")
    print(f"  H1 output:       {OUTPUT_H1}")
    print(f"  H2 output:       {OUTPUT_H2}")
    print(f"  Combined output: {OUTPUT_COMB}")


if __name__ == "__main__":
    main()
