"""
research/ic_validation_extended.py — Multi-signal, multi-period, regime-conditional IC validation.

Tests whether individual signal components have sufficient predictive power before
relying on a composite. A composite of individually non-predictive signals remains
non-predictive (law of large numbers does not rescue IC from noise).

Signals tested (each individually):
  r_30m       — 30-minute return
  r_2h        — 2-hour return
  r_6h        — 6-hour return
  r_24h       — 24-hour return
  C1_composite — full weighted composite (matching signals.py):
                 0.10*r_30m + 0.20*r_2h + 0.35*r_6h + 0.25*r_24h + 0.10*(r_2h - median_r2h)
                 then cross-sectional z-score

Three test conditions per signal:
  A. Current period (Dec 2025–Feb 2026)    — unconditional, recent choppy market
  B. Trending period (Oct 2024–Jan 2025)   — period covering BTC +61% bull run
  C. Regime-conditional (current period)   — only TREND-eligible timestamps (BTC vol z ≤ 0)

Forward return target: forward 6h return (matches strategy rebalance horizon)

Run:
  python research/ic_validation_extended.py

Outputs:
  research/ic_results_extended.md
  research/charts/ic_multi_horizon.png
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
from typing import Dict, List, Optional, Tuple

# ── Configuration ──────────────────────────────────────────────────────────────

FALLBACK_PAIRS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
]

ROOSTOO_EXCHANGE_INFO_URL = "https://mock-api.roostoo.com/v3/exchangeInfo"


def fetch_roostoo_pairs() -> List[str]:
    """Fetch all tradable pairs from Roostoo /v3/exchangeInfo (no auth required).

    Maps SYMBOL/USD → SYMBOLUSDT for Binance Vision lookup.
    Falls back to FALLBACK_PAIRS if unreachable.
    """
    try:
        with urllib.request.urlopen(ROOSTOO_EXCHANGE_INFO_URL, timeout=10) as resp:
            data = json.loads(resp.read())
        pairs = []
        for roostoo_pair in data.get("TradePairs", {}).keys():
            symbol = roostoo_pair.replace("/USD", "USDT").replace("/", "")
            if symbol.endswith("USDT"):
                pairs.append(symbol)
        if len(pairs) >= 10:
            return sorted(pairs)
    except Exception as exc:
        print(f"  [WARN] Could not fetch Roostoo pairs: {exc}. Using fallback list.")
    return list(FALLBACK_PAIRS)

FORWARD_HOURS = 6  # Forward return window

# Current period: 3 months ending now
CURRENT_LOOKBACK_MONTHS = 3

# Trending period: Oct 2024 – Jan 2025 (backtest period)
TRENDING_START = (2024, 10)
TRENDING_END   = (2025,  1)

# Regime filter: BTC vol z-score threshold for TREND-eligible periods
TREND_VOL_Z_THRESHOLD = 0.0    # vol_z <= 0 → low vol → TREND regime
VOL_LOOKBACK_PERIODS  = 48     # 48h rolling window for z-score

# C1 weights (match config.py exactly)
C1_WEIGHT_R30M  = 0.10
C1_WEIGHT_R2H   = 0.20
C1_WEIGHT_R6H   = 0.35
C1_WEIGHT_R24H  = 0.25
C1_WEIGHT_CS_RS = 0.10

BINANCE_VISION_BASE = "https://data.binance.vision/data/spot/monthly/klines"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "ic_results_extended.md")
CHARTS_DIR  = os.path.join(os.path.dirname(__file__), "charts")


# ── Data Download ──────────────────────────────────────────────────────────────

def download_monthly_klines(symbol: str, year: int, month: int) -> List[List[str]]:
    month_str = f"{month:02d}"
    filename = f"{symbol}-1h-{year}-{month_str}.zip"
    url = f"{BINANCE_VISION_BASE}/{symbol}/1h/{filename}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            with zf.open(zf.namelist()[0]) as f:
                return list(csv.reader(io.TextIOWrapper(f)))
    except Exception as exc:
        print(f"  [WARN] {symbol} {year}-{month_str}: {exc}")
        return []


def _normalize_ts(ts: int) -> int:
    """Normalize Binance Vision timestamps to milliseconds (they switched to microseconds in 2025)."""
    if ts > 1_000_000_000_000_000:
        return ts // 1000
    return ts


def _month_range_recent(months_back: int) -> List[Tuple[int, int]]:
    """Return list of (year, month) for the last `months_back` months."""
    now = datetime.now(timezone.utc)
    return [(( now - timedelta(days=30 * i)).year, (now - timedelta(days=30 * i)).month)
            for i in range(months_back, 0, -1)]


def _month_range(start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Return list of (year, month) from start to end inclusive."""
    months = []
    year, month = start
    while (year, month) <= end:
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def load_prices_all_parallel(
    symbols: List[str],
    months: List[Tuple[int, int]],
    max_workers: int = 6,
) -> Dict[str, Dict[int, float]]:
    """Download prices for all symbols × months in parallel."""
    prices: Dict[str, Dict[int, float]] = {sym: {} for sym in symbols}
    tasks = [(sym, yr, mo) for sym in symbols for yr, mo in months]

    def _fetch(task: Tuple[str, int, int]) -> Tuple[str, Dict[int, float]]:
        sym, yr, mo = task
        month_prices: Dict[int, float] = {}
        for row in download_monthly_klines(sym, yr, mo):
            if not row or not row[0].isdigit():
                continue
            month_prices[_normalize_ts(int(row[0]))] = float(row[4])
        return sym, month_prices

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch, t): t for t in tasks}
        completed = 0
        for future in as_completed(futures):
            sym, month_prices = future.result()
            prices[sym].update(month_prices)
            completed += 1
            if completed % max(1, len(tasks) // 10) == 0:
                print(f"  [{completed}/{len(tasks)} files downloaded]", flush=True)

    return prices


def load_prices_recent(symbol: str, months_back: int) -> Dict[int, float]:
    """Load hourly close prices for the most recent `months_back` months (single symbol)."""
    now = datetime.now(timezone.utc)
    prices: Dict[int, float] = {}
    for i in range(months_back, 0, -1):
        target = now - timedelta(days=30 * i)
        for row in download_monthly_klines(symbol, target.year, target.month):
            if not row or not row[0].isdigit():
                continue
            prices[_normalize_ts(int(row[0]))] = float(row[4])
    return prices


def load_prices_range(symbol: str, start: Tuple[int, int], end: Tuple[int, int]) -> Dict[int, float]:
    """Load hourly close prices for an explicit year/month range (single symbol)."""
    prices: Dict[int, float] = {}
    year, month = start
    while (year, month) <= end:
        for row in download_monthly_klines(symbol, year, month):
            if not row or not row[0].isdigit():
                continue
            prices[_normalize_ts(int(row[0]))] = float(row[4])
        month += 1
        if month > 12:
            month = 1
            year += 1
    return prices


# ── Feature Computation ────────────────────────────────────────────────────────

def compute_return(prices: Dict[int, float], ts: int, hours: float) -> Optional[float]:
    """Return at `ts` over last `hours` hours."""
    ms = int(hours * 3_600_000)
    p_now = prices.get(ts)
    p_then = prices.get(ts - ms)
    if p_now is None or p_then is None or p_then <= 0:
        return None
    return (p_now - p_then) / p_then


def compute_forward_return(prices: Dict[int, float], ts: int, hours: int) -> Optional[float]:
    """Forward return from `ts` over `hours` hours."""
    ts_fwd = ts + hours * 3_600_000
    p_fwd = prices.get(ts_fwd)
    p_now = prices.get(ts)
    if p_fwd is None or p_now is None or p_now <= 0:
        return None
    return (p_fwd - p_now) / p_now


def cross_sectional_z(values: Dict[str, float]) -> Dict[str, float]:
    """Cross-sectionally z-normalize a dict of values."""
    vals = list(values.values())
    n = len(vals)
    if n < 2:
        return {k: 0.0 for k in values}
    mean = sum(vals) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in vals) / n) or 1e-8
    return {k: (v - mean) / std for k, v in values.items()}


def rolling_btc_vol(btc_prices: Dict[int, float], ts: int, window: int = 24) -> Optional[float]:
    """Rolling std of 1h BTC returns over `window` hours."""
    rets = []
    for i in range(1, window + 1):
        p0 = btc_prices.get(ts - i * 3_600_000)
        p1 = btc_prices.get(ts - (i - 1) * 3_600_000)
        if p0 and p1 and p0 > 0:
            rets.append((p1 - p0) / p0)
    if len(rets) < window // 2:
        return None
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets))


def z_score(value: float, history: List[float]) -> float:
    if len(history) < 3:
        return 0.0
    mean = sum(history) / len(history)
    std = math.sqrt(sum((v - mean) ** 2 for v in history) / len(history)) or 1e-8
    return (value - mean) / std


# ── IC Statistics ──────────────────────────────────────────────────────────────

def spearman_ic(x: List[float], y: List[float]) -> Optional[float]:
    n = len(x)
    if n < 5:
        return None

    def rank(lst: List[float]) -> List[float]:
        idx = sorted(range(n), key=lambda i: lst[i])
        r = [0.0] * n
        for ri, oi in enumerate(idx):
            r[oi] = float(ri + 1)
        return r

    rx, ry = rank(x), rank(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n)) / n
    sx = math.sqrt(sum((v - mx) ** 2 for v in rx) / n)
    sy = math.sqrt(sum((v - my) ** 2 for v in ry) / n)
    if sx < 1e-9 or sy < 1e-9:
        return None
    return cov / (sx * sy)


def t_stat(ic: float, n: int) -> float:
    if n <= 2 or abs(ic) >= 1.0:
        return 0.0
    return ic * math.sqrt(n - 2) / math.sqrt(1 - ic ** 2 + 1e-12)


def compute_ic_stats(data: List[Tuple[float, float]], n_pairs: int = 10) -> dict:
    """Compute IC statistics from (signal, forward_ret) pairs.

    Args:
        data:    List of (signal_z, forward_return) pairs.
        n_pairs: Number of assets in the universe (used as cross-section batch size).
    """
    if len(data) < 20:
        return {"n": len(data), "mean_ic": None, "t_stat": None, "hit_rate": None, "period_ics": []}

    batch = n_pairs
    period_ics = []
    for i in range(0, len(data) - batch, batch):
        bx = [data[j][0] for j in range(i, i + batch)]
        by = [data[j][1] for j in range(i, i + batch)]
        ic = spearman_ic(bx, by)
        if ic is not None:
            period_ics.append(ic)

    if not period_ics:
        xs = [d[0] for d in data]
        ys = [d[1] for d in data]
        ic_full = spearman_ic(xs, ys)
        return {"n": 1, "mean_ic": ic_full, "t_stat": 0.0, "hit_rate": None, "period_ics": []}

    mean_ic = sum(period_ics) / len(period_ics)
    std_ic = math.sqrt(sum((v - mean_ic) ** 2 for v in period_ics) / len(period_ics)) or 1e-8
    hit_rate = sum(1 for v in period_ics if v > 0) / len(period_ics)
    t = t_stat(mean_ic, len(period_ics))

    return {"n": len(period_ics), "mean_ic": mean_ic, "t_stat": t,
            "hit_rate": hit_rate, "period_ics": period_ics}


# ── Core Analysis Runner ───────────────────────────────────────────────────────

def run_analysis(
    all_prices: Dict[str, Dict[int, float]],
    regime_filter: bool = False,
) -> Dict[str, dict]:
    """
    Compute per-signal IC against forward 6h returns.

    Args:
        all_prices:    {symbol: {ts_ms: close}}
        regime_filter: If True, include only TREND-eligible timestamps (BTC vol z <= 0)

    Returns:
        {signal_name: ic_stats_dict}
    """
    active_pairs = [sym for sym, p in all_prices.items() if len(p) > 100]
    if not active_pairs:
        return {}
    btc_prices = all_prices.get("BTCUSDT", {})
    ts_sets = [set(all_prices[sym].keys()) for sym in active_pairs]
    common_ts = sorted(ts_sets[0].intersection(*ts_sets[1:]))

    # Regime filter state
    vol_history: List[float] = []

    # Accumulators: signal_name → [(signal_z, fwd_ret)]
    signals_names = ["r_30m", "r_2h", "r_6h", "r_24h", "C1_composite"]
    data: Dict[str, List[Tuple[float, float]]] = {s: [] for s in signals_names}

    for ts in common_ts:
        # Compute regime filter (BTC vol z-score)
        if regime_filter:
            vol = rolling_btc_vol(btc_prices, ts)
            if vol is not None:
                prev_hist = list(vol_history)
                vol_history.append(vol)
                if len(vol_history) > VOL_LOOKBACK_PERIODS:
                    vol_history = vol_history[-VOL_LOOKBACK_PERIODS:]
                vol_z = z_score(vol, prev_hist) if len(prev_hist) >= 3 else 0.0
                if vol_z > TREND_VOL_Z_THRESHOLD:
                    continue  # Exclude: high vol = non-TREND period
            else:
                # Can't compute vol yet — skip to avoid noise
                continue

        # Compute all returns and forward return per asset
        r30m_raw:  Dict[str, float] = {}
        r2h_raw:   Dict[str, float] = {}
        r6h_raw:   Dict[str, float] = {}
        r24h_raw:  Dict[str, float] = {}
        fwd_raw:   Dict[str, float] = {}

        for pair in active_pairs:
            # Hourly data limitation: 30m return (ts - 1800s) doesn't exist in 1h bars.
            # Use 1h return as proxy for r_30m in both the individual test and C1 composite.
            r1h  = compute_return(all_prices[pair], ts, 1.0)   # proxy for r_30m
            r2h  = compute_return(all_prices[pair], ts, 2.0)
            r6h  = compute_return(all_prices[pair], ts, 6.0)
            r24h = compute_return(all_prices[pair], ts, 24.0)
            fwd  = compute_forward_return(all_prices[pair], ts, FORWARD_HOURS)
            if None in (r1h, r2h, r6h, r24h, fwd):
                continue
            r30m_raw[pair]  = r1h   # 1h proxy
            r2h_raw[pair]   = r2h
            r6h_raw[pair]   = r6h
            r24h_raw[pair]  = r24h
            fwd_raw[pair]   = fwd

        if len(r6h_raw) < max(3, len(active_pairs) // 2):
            continue  # Too few pairs

        # Cross-sectional z-scores for each horizon
        z30m  = cross_sectional_z(r30m_raw)
        z2h   = cross_sectional_z(r2h_raw)
        z6h   = cross_sectional_z(r6h_raw)
        z24h  = cross_sectional_z(r24h_raw)

        # C1 composite: weighted raw signal → cross-sectional z-score
        # Cross-sectional median of r_2h for relative strength term
        median_r2h_vals = sorted(r2h_raw.values())
        median_r2h = median_r2h_vals[len(median_r2h_vals) // 2]

        c1_raw_vals: Dict[str, float] = {}
        for pair in r6h_raw.keys():
            raw = (
                C1_WEIGHT_R30M  * r30m_raw.get(pair, 0.0)
                + C1_WEIGHT_R2H   * r2h_raw.get(pair, 0.0)
                + C1_WEIGHT_R6H   * r6h_raw.get(pair, 0.0)
                + C1_WEIGHT_R24H  * r24h_raw.get(pair, 0.0)
                + C1_WEIGHT_CS_RS * (r2h_raw.get(pair, 0.0) - median_r2h)
            )
            c1_raw_vals[pair] = raw
        z_c1 = cross_sectional_z(c1_raw_vals)

        # Accumulate IC data
        for pair in fwd_raw.keys():
            fwd_ret = fwd_raw[pair]
            if pair in z30m:
                data["r_30m"].append((z30m[pair], fwd_ret))
            if pair in z2h:
                data["r_2h"].append((z2h[pair], fwd_ret))
            if pair in z6h:
                data["r_6h"].append((z6h[pair], fwd_ret))
            if pair in z24h:
                data["r_24h"].append((z24h[pair], fwd_ret))
            if pair in z_c1:
                data["C1_composite"].append((z_c1[pair], fwd_ret))

    n_pairs = len(active_pairs)
    return {sig: compute_ic_stats(data[sig], n_pairs=n_pairs) for sig in signals_names}


# ── Main ──────────────────────────────────────────────────────────────────────

def fmt_ic(stats: dict) -> str:
    if stats.get("mean_ic") is None or stats.get("n", 0) < 5:
        return "  N/A (insufficient data)"
    ic = stats["mean_ic"]
    t  = stats.get("t_stat", 0.0) or 0.0
    hr = stats.get("hit_rate", 0.0) or 0.0
    n  = stats.get("n", 0)
    flag = ""
    if ic >= 0.05 and t >= 1.5:
        flag = " ***"
    elif ic >= 0.03 and t >= 1.0:
        flag = " **"
    elif ic > 0.0:
        flag = " *"
    return f"  IC={ic:+.4f}  t={t:+.2f}  hit={hr:.1%}  n={n}{flag}"


def main() -> None:
    print("=" * 70)
    print("Extended IC Validation — Multi-Signal, Multi-Period, Regime-Conditional")
    print("=" * 70)

    # ── Discover full Roostoo universe ─────────────────────────────────────────
    print("\nFetching tradable pairs from Roostoo...")
    pairs = fetch_roostoo_pairs()
    print(f"Universe: {len(pairs)} pairs")

    # ── Load data in parallel ──────────────────────────────────────────────────
    print(f"\nDownloading current-period data (last {CURRENT_LOOKBACK_MONTHS} months, {len(pairs)} pairs)...")
    current_months = _month_range_recent(CURRENT_LOOKBACK_MONTHS)
    current_prices = load_prices_all_parallel(pairs, current_months)

    # Report coverage
    covered = sum(1 for p in current_prices.values() if len(p) > 100)
    print(f"  {covered}/{len(pairs)} pairs have data")

    print(f"\nDownloading trending-period data (Oct 2024–Jan 2025, {len(pairs)} pairs)...")
    trending_months = _month_range(TRENDING_START, TRENDING_END)
    trending_prices = load_prices_all_parallel(pairs, trending_months)

    covered_t = sum(1 for p in trending_prices.values() if len(p) > 100)
    print(f"  {covered_t}/{len(pairs)} pairs have data")

    # ── Run analysis ──────────────────────────────────────────────────────────
    print("\nRunning Test A: Current period (unconditional)...")
    results_A = run_analysis(current_prices, regime_filter=False)

    print("Running Test B: Trending period (Oct 2024–Jan 2025)...")
    results_B = run_analysis(trending_prices, regime_filter=False)

    print("Running Test C: Current period (TREND-eligible hours only)...")
    results_C = run_analysis(current_prices, regime_filter=True)

    # ── Format output ─────────────────────────────────────────────────────────
    signals = ["r_30m", "r_2h", "r_6h", "r_24h", "C1_composite"]
    signal_labels = {
        "r_30m":       "1h ret(30m~) ",  # hourly data: 1h return used as 30m proxy
        "r_2h":        "2h return    ",
        "r_6h":        "6h return    ",
        "r_24h":       "24h return   ",
        "C1_composite": "C1 composite ",
    }

    # Count filtered timestamps for Test C
    # (rough: count available C1_composite periods in C vs A)
    n_total_A = results_A.get("C1_composite", {}).get("n", 0)
    n_total_C = results_C.get("C1_composite", {}).get("n", 0)
    pct_trend_eligible = (n_total_C / n_total_A * 100) if n_total_A > 0 else 0

    # Decision summary
    def signal_quality(stats_b: dict, stats_c: dict) -> str:
        """Summarize signal quality from trending-period and TREND-conditional results."""
        ic_b = stats_b.get("mean_ic") or 0
        ic_c = stats_c.get("mean_ic") or 0
        t_b = abs(stats_b.get("t_stat") or 0)
        t_c = abs(stats_c.get("t_stat") or 0)
        if ic_b >= 0.05 and t_b >= 1.5:
            return "STRONG in trending period"
        elif ic_c >= 0.04 and t_c >= 1.0:
            return "POSITIVE in TREND regime"
        elif ic_b >= 0.02 or ic_c >= 0.02:
            return "WEAK positive"
        elif ic_b >= 0.0 and ic_c >= 0.0:
            return "Near zero (noise)"
        else:
            return "NEGATIVE (mean-reversion)"

    lines = [
        "# Extended IC Validation — Multi-Signal, Multi-Period, Regime-Conditional",
        f"# Universe: {len(pairs)} pairs ({', '.join(pairs[:6])}, ...)",
        f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Test Conditions",
        "",
        "  A. Current period (unconditional): Dec 2025–Feb 2026",
        "  B. Trending period (unconditional): Oct 2024–Jan 2025  [BTC +61% bull run]",
        f"  C. Current period, TREND-eligible only: BTC vol z-score <= 0  [{pct_trend_eligible:.0f}% of timestamps]",
        "",
        "  Forward return target: forward 6-hour return",
        "  Significance: * = IC>0, ** = IC>0.03+t>1.0, *** = IC>0.05+t>1.5",
        "",
        "## IC Results Table",
        "",
        f"  {'Signal':15s} | {'Test A (current)':30s} | {'Test B (trending)':30s} | {'Test C (TREND-cond.)':30s}",
        f"  {'-'*15}-+-{'-'*30}-+-{'-'*30}-+-{'-'*30}",
    ]
    for sig in signals:
        label = signal_labels[sig]
        a = fmt_ic(results_A.get(sig, {}))
        b = fmt_ic(results_B.get(sig, {}))
        c = fmt_ic(results_C.get(sig, {}))
        lines.append(f"  {label} |{a:<30} |{b:<30} |{c:<30}")

    lines += [
        "",
        "## Signal Quality Assessment",
        "",
    ]
    for sig in signals:
        quality = signal_quality(results_B.get(sig, {}), results_C.get(sig, {}))
        ic_b = results_B.get(sig, {}).get("mean_ic")
        ic_c = results_C.get(sig, {}).get("mean_ic")
        ic_b_str = f"{ic_b:+.4f}" if ic_b is not None else "N/A"
        ic_c_str = f"{ic_c:+.4f}" if ic_c is not None else "N/A"
        lines.append(f"  {signal_labels[sig]}: {quality}  (B IC={ic_b_str}, C IC={ic_c_str})")

    # Overall interpretation
    composite_b = results_B.get("C1_composite", {})
    composite_c = results_C.get("C1_composite", {})
    ic_b_c1  = composite_b.get("mean_ic") or 0
    ic_c_c1  = composite_c.get("mean_ic") or 0
    t_b_c1   = composite_b.get("t_stat") or 0
    t_c_c1   = composite_c.get("t_stat") or 0

    best_trending = max(
        [(results_B.get(s, {}).get("mean_ic") or 0, s) for s in signals],
        key=lambda x: x[0]
    )

    lines += [
        "",
        "## Interpretation",
        "",
        f"  Best individual signal in trending period (Test B): "
        f"{signal_labels[best_trending[1]].strip()} IC={best_trending[0]:+.4f}",
        "",
        f"  C1 composite — Trending period (Test B): IC={ic_b_c1:+.4f}, t={t_b_c1:+.2f}",
        f"  C1 composite — TREND-conditional  (Test C): IC={ic_c_c1:+.4f}, t={t_c_c1:+.2f}",
        "",
    ]

    if ic_b_c1 >= 0.05 and t_b_c1 >= 1.5:
        lines += [
            "  VERDICT: C1 composite signal has statistically meaningful predictive power",
            "  in trending market conditions. The regime gating correctly concentrates",
            "  trading in the periods where the signal has edge.",
            "  RECOMMENDATION: No weight changes needed. Strategy is empirically validated.",
        ]
    elif ic_c_c1 >= 0.04 and t_c_c1 >= 1.0:
        lines += [
            "  VERDICT: C1 composite signal is positively predictive in TREND-eligible",
            "  periods (when the regime engine would allow trading). The unconditional",
            "  IC includes non-TREND hours where we are in cash — those hours should not",
            "  count against the signal. Strategy is conditionally validated.",
            "  RECOMMENDATION: No weight changes needed.",
        ]
    elif ic_b_c1 >= 0.02 or ic_c_c1 >= 0.02:
        lines += [
            "  VERDICT: Weak positive IC in either the trending period or TREND-conditional",
            "  test. The signal has marginal predictive value.",
            "  RECOMMENDATION: Consider shifting weight toward the highest-IC horizon.",
        ]
        # Check if 24h dominates
        ic_24h_b = results_B.get("r_24h", {}).get("mean_ic") or 0
        ic_6h_b  = results_B.get("r_6h", {}).get("mean_ic") or 0
        if ic_24h_b > ic_6h_b + 0.03:
            lines.append(
                f"  NOTE: 24h IC ({ic_24h_b:+.4f}) > 6h IC ({ic_6h_b:+.4f}) by >{0.03:.2f}."
                " Consider shifting weight from 6h to 24h in config.py."
            )
    else:
        lines += [
            "  VERDICT: No individual signal or composite shows meaningful IC (>0.02)",
            "  in the trending period OR in TREND-conditional periods.",
            "  Cross-sectional momentum does not have detectable predictive power",
            "  in this universe across these test windows.",
            "  RECOMMENDATION: Strategy value comes from regime-gated drawdown control",
            "  (Sortino/Calmar), not from signal-based alpha. Narrative should focus on",
            "  risk-adjusted return objectives, not return prediction.",
        ]

    lines += [
        "",
        "## Notes",
        "",
        "  r_30m proxy: Binance Vision provides 1h bars; 30-min return cannot be",
        "  computed directly. 1-hour return is used as a proxy (labeled '1h ret(30m~)').",
        "  The live bot uses 1-min snapshots and can compute r_30m precisely.",
        "",
        "  Law of large numbers: a composite only amplifies predictive signal if",
        "  individual components are positively correlated with the target. A composite",
        "  of non-predictive signals remains non-predictive.",
        "",
        "  Regime-conditionality: the strategy is designed to trade only in TREND",
        "  regimes. IC measured unconditionally includes periods where the strategy",
        "  would be in HAZARD_DEFENSIVE (in cash). Test C isolates the relevant subset.",
        "",
        "  Reference: ic_results.md for baseline 3-month unconditional IC,",
        "  backtest_results.md for simulation results.",
    ]

    output = "\n".join(lines)
    print("\n" + output)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {OUTPUT_FILE}")

    # ── Optional: generate chart ──────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(CHARTS_DIR, exist_ok=True)

        labels = ["30m", "2h", "6h", "24h", "C1 composite"]
        ic_A = [results_A.get(s, {}).get("mean_ic") or 0 for s in signals]
        ic_B = [results_B.get(s, {}).get("mean_ic") or 0 for s in signals]
        ic_C = [results_C.get(s, {}).get("mean_ic") or 0 for s in signals]

        x = range(len(signals))
        width = 0.25

        fig, ax = plt.subplots(figsize=(13, 6))

        def bar_colors(ics):
            colors = []
            for ic in ics:
                if ic >= 0.04:
                    colors.append("#2ecc71")
                elif ic > 0:
                    colors.append("#f39c12")
                else:
                    colors.append("#e74c3c")
            return colors

        for i, (ic_list, offset, label, alpha) in enumerate([
            (ic_A, -width, "A: Current period", 0.65),
            (ic_B,      0, "B: Trending period (Oct 2024–Jan 2025)", 0.85),
            (ic_C, +width, "C: TREND-conditional (low vol only)", 0.65),
        ]):
            positions = [xi + offset for xi in x]
            colors = bar_colors(ic_list)
            bars = ax.bar(positions, ic_list, width=width * 0.9,
                          label=label, color=colors, alpha=alpha, edgecolor="white")
            for bar, val in zip(bars, ic_list):
                va = "bottom" if val >= 0 else "top"
                offset_pts = 2 if val >= 0 else -2
                ax.text(bar.get_x() + bar.get_width() / 2, val,
                        f"{val:+.3f}", ha="center", va=va,
                        fontsize=7.5, color="#2c3e50")

        ax.axhline(0, color="black", linewidth=0.8)
        ax.axhline(0.04, color="#2ecc71", linewidth=0.8, linestyle=":", alpha=0.6,
                   label="IC = 0.04 (weak predictive threshold)")
        ax.axhline(-0.04, color="#e74c3c", linewidth=0.8, linestyle=":", alpha=0.6)

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_title(
            "IC by Signal × Market Regime — Cross-Sectional Momentum Validation\n"
            "Green = IC ≥ 0.04 (predictive), Orange = 0 < IC < 0.04 (weak), Red = IC < 0 (mean-reverting)",
            fontsize=11, fontweight="bold"
        )
        ax.set_ylabel("Spearman Information Coefficient (IC)")
        ax.legend(fontsize=8, loc="upper right")
        ax.set_ylim(min(min(ic_A), min(ic_B), min(ic_C)) - 0.04,
                    max(max(ic_A), max(ic_B), max(ic_C)) + 0.06)

        plt.tight_layout()
        chart_path = os.path.join(CHARTS_DIR, "ic_multi_horizon.png")
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Chart saved to {chart_path}")

    except ImportError:
        print("matplotlib not available — skipping chart generation")


if __name__ == "__main__":
    main()
