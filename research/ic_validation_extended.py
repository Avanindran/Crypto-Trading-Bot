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


def load_prices_and_volumes_all_parallel(
    symbols: List[str],
    months: List[Tuple[int, int]],
    max_workers: int = 6,
) -> Tuple[Dict[str, Dict[int, float]], Dict[str, Dict[int, float]]]:
    """Download close prices AND base-asset volumes for all symbols × months in one pass."""
    prices:  Dict[str, Dict[int, float]] = {sym: {} for sym in symbols}
    volumes: Dict[str, Dict[int, float]] = {sym: {} for sym in symbols}
    tasks = [(sym, yr, mo) for sym in symbols for yr, mo in months]

    def _fetch_pv(task: Tuple[str, int, int]) -> Tuple[str, Dict[int, float], Dict[int, float]]:
        sym, yr, mo = task
        mp: Dict[int, float] = {}
        mv: Dict[int, float] = {}
        for row in download_monthly_klines(sym, yr, mo):
            if not row or not row[0].isdigit():
                continue
            ts = _normalize_ts(int(row[0]))
            mp[ts] = float(row[4])
            if len(row) > 5:
                try:
                    mv[ts] = float(row[5])
                except (ValueError, IndexError):
                    pass
        return sym, mp, mv

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_pv, t): t for t in tasks}
        completed = 0
        for future in as_completed(futures):
            sym, mp, mv = future.result()
            prices[sym].update(mp)
            volumes[sym].update(mv)
            completed += 1
            if completed % max(1, len(tasks) // 10) == 0:
                print(f"  [{completed}/{len(tasks)} files downloaded]", flush=True)

    return prices, volumes


def load_klines_all_parallel(
    symbols: List[str],
    months: List[Tuple[int, int]],
    max_workers: int = 6,
) -> Tuple[
    Dict[str, Dict[int, float]],  # close (col 4)
    Dict[str, Dict[int, float]],  # base_vol (col 5)
    Dict[str, Dict[int, float]],  # quote_vol (col 7)
    Dict[str, Dict[int, float]],  # num_trades (col 8)
    Dict[str, Dict[int, float]],  # taker_buy_vol (col 9)
    Dict[str, Dict[int, float]],  # open (col 1)
    Dict[str, Dict[int, float]],  # high (col 2)
    Dict[str, Dict[int, float]],  # low (col 3)
]:
    """Download full OHLCV + taker/trade data for OFI signal computation.

    Extracts 8 data streams from Binance 1h klines in a single parallel pass:
    close (col 4), base_vol (col 5), quote_vol (col 7), num_trades (col 8),
    taker_buy_base_vol (col 9), open (col 1), high (col 2), low (col 3).
    """
    empty = lambda: {sym: {} for sym in symbols}  # noqa: E731
    prices, bvol, qvol, ntrades, tbvol, open_, high, low = (
        empty(), empty(), empty(), empty(),
        empty(), empty(), empty(), empty(),
    )
    tasks = [(sym, yr, mo) for sym in symbols for yr, mo in months]

    def _fetch_full(task: Tuple[str, int, int]):
        sym, yr, mo = task
        mp: Dict[int, float] = {}
        mv: Dict[int, float] = {}
        mq: Dict[int, float] = {}
        mn: Dict[int, float] = {}
        mt: Dict[int, float] = {}
        mo_: Dict[int, float] = {}
        mh: Dict[int, float] = {}
        ml: Dict[int, float] = {}
        for row in download_monthly_klines(sym, yr, mo):
            if not row or not row[0].isdigit() or len(row) < 10:
                continue
            ts = _normalize_ts(int(row[0]))
            try:
                mp[ts]  = float(row[4])   # close
                mv[ts]  = float(row[5])   # base volume
                mq[ts]  = float(row[7])   # quote volume
                mn[ts]  = float(row[8])   # num trades
                mt[ts]  = float(row[9])   # taker buy base vol
                mo_[ts] = float(row[1])   # open
                mh[ts]  = float(row[2])   # high
                ml[ts]  = float(row[3])   # low
            except (ValueError, IndexError):
                pass
        return sym, mp, mv, mq, mn, mt, mo_, mh, ml

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_full, t): t for t in tasks}
        completed = 0
        for future in as_completed(futures):
            sym, mp, mv, mq, mn, mt, mo_, mh, ml = future.result()
            prices[sym].update(mp);  bvol[sym].update(mv)
            qvol[sym].update(mq);    ntrades[sym].update(mn)
            tbvol[sym].update(mt);   open_[sym].update(mo_)
            high[sym].update(mh);    low[sym].update(ml)
            completed += 1
            if completed % max(1, len(tasks) // 10) == 0:
                print(f"  [{completed}/{len(tasks)} files downloaded]", flush=True)

    return prices, bvol, qvol, ntrades, tbvol, open_, high, low


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
    all_volumes: Optional[Dict[str, Dict[int, float]]] = None,
    all_qvol: Optional[Dict[str, Dict[int, float]]] = None,
    all_ntrades: Optional[Dict[str, Dict[int, float]]] = None,
    all_tbvol: Optional[Dict[str, Dict[int, float]]] = None,
    all_open: Optional[Dict[str, Dict[int, float]]] = None,
    all_high: Optional[Dict[str, Dict[int, float]]] = None,
    all_low: Optional[Dict[str, Dict[int, float]]] = None,
    regime_filter: bool = False,
) -> Dict[str, dict]:
    """
    Compute per-signal IC against forward 6h returns.

    Tests existing cross-sectional signals (r_30m, r_2h, r_6h, r_24h, C1_composite),
    time-series (TS) candidate formulas (F1–F7), and OFI signals (G1–G6):
      F1: z_ts_6h  — per-asset TS z-score of 6h return vs own 48-period baseline
      F2: z_ts_2h  — per-asset TS z-score of 2h return
      F3: z_ts_24h — per-asset TS z-score of 24h return
      F4: ma_ratio — TS z-score of (price - MA_24h)/MA_24h (deviation from own anchor)
      F5: vol_ratio — current vol / rolling_mean(vol, 48) (flow persistence proxy)
      F6: z_ts_6h × min(vol_ratio, 2.0) — volume-confirmed TS momentum
      F7: 0.35·z6h + 0.35·z2h + 0.20·z24h + 0.10·ma_ratio_z (multi-horizon composite)
      G1: z_ts(taker_buy_ratio) — per-asset TS z-score of taker buy fraction
      G2: z_ts(candle_body)     — per-asset TS z-score of (close-open)/(high-low)
      G3: z_ts(quote_vol)       — per-asset TS z-score of USD-denominated volume
      G4: z_ts(num_trades)      — per-asset TS z-score of trade count
      G5: z_ts(tbr × |r6h|)    — OFI scaled by directional magnitude
      G6: 0.50·G1 + 0.30·G2 + 0.20·G4 — OFI composite

    All TS/OFI signals have a final cross-sectional z-score step (doctrine: allocation normalization).

    Args:
        all_prices:    {symbol: {ts_ms: close}}
        all_volumes:   {symbol: {ts_ms: base_volume}} (optional; F5/F6 require this)
        all_qvol:      {symbol: {ts_ms: quote_volume}} (optional; G3 requires this)
        all_ntrades:   {symbol: {ts_ms: num_trades}} (optional; G4/G6 require this)
        all_tbvol:     {symbol: {ts_ms: taker_buy_base_vol}} (optional; G1/G5/G6 require this)
        all_open:      {symbol: {ts_ms: open}} (optional; G2/G6 require this)
        all_high:      {symbol: {ts_ms: high}} (optional; G2 requires this)
        all_low:       {symbol: {ts_ms: low}} (optional; G2 requires this)
        regime_filter: If True, include only TREND-eligible timestamps (BTC vol z <= 0)

    Returns:
        {signal_name: ic_stats_dict}
    """
    TS_LOOKBACK = 48   # rolling periods for per-asset baseline

    active_pairs = [sym for sym, p in all_prices.items() if len(p) > 100]
    if not active_pairs:
        return {}
    btc_prices = all_prices.get("BTCUSDT", {})
    ts_sets = [set(all_prices[sym].keys()) for sym in active_pairs]
    common_ts = sorted(ts_sets[0].intersection(*ts_sets[1:]))

    # Regime filter state
    vol_history: List[float] = []

    # TS rolling histories per pair (trimmed to TS_LOOKBACK after each update)
    ts_hist: Dict[str, Dict[str, List[float]]] = {
        pair: {"r_2h": [], "r_6h": [], "r_24h": [], "ma_ratio": []}
        for pair in active_pairs
    }
    price_hist: Dict[str, List[float]] = {pair: [] for pair in active_pairs}
    vol_hist:   Dict[str, List[float]] = {pair: [] for pair in active_pairs}

    # OFI rolling histories per pair (G1–G6 signals)
    tbr_hist:     Dict[str, List[float]] = {pair: [] for pair in active_pairs}
    body_hist:    Dict[str, List[float]] = {pair: [] for pair in active_pairs}
    qvol_hist:    Dict[str, List[float]] = {pair: [] for pair in active_pairs}
    ntrades_hist: Dict[str, List[float]] = {pair: [] for pair in active_pairs}
    g5_hist:      Dict[str, List[float]] = {pair: [] for pair in active_pairs}

    # Accumulators: signal_name → [(signal_z, fwd_ret)]
    signals_names = [
        "r_30m", "r_2h", "r_6h", "r_24h", "C1_composite",
        "F1_z6h", "F2_z2h", "F3_z24h", "F4_ma", "F5_vol", "F6_z6h_vol", "F7_composite",
        "G1_tbr", "G2_body", "G3_qvol", "G4_ntrades", "G5_tbr_r6h", "G6_composite",
    ]
    data: Dict[str, List[Tuple[float, float]]] = {s: [] for s in signals_names}

    for ts in common_ts:
        # ── Regime filter ──────────────────────────────────────────────────────
        if regime_filter:
            vol = rolling_btc_vol(btc_prices, ts)
            if vol is not None:
                prev_hist = list(vol_history)
                vol_history.append(vol)
                if len(vol_history) > VOL_LOOKBACK_PERIODS:
                    vol_history = vol_history[-VOL_LOOKBACK_PERIODS:]
                vol_z = z_score(vol, prev_hist) if len(prev_hist) >= 3 else 0.0
                if vol_z > TREND_VOL_Z_THRESHOLD:
                    continue
            else:
                continue

        # ── Compute returns and forward return per asset ────────────────────────
        r30m_raw: Dict[str, float] = {}
        r2h_raw:  Dict[str, float] = {}
        r6h_raw:  Dict[str, float] = {}
        r24h_raw: Dict[str, float] = {}
        fwd_raw:  Dict[str, float] = {}

        for pair in active_pairs:
            r1h  = compute_return(all_prices[pair], ts, 1.0)   # proxy for r_30m
            r2h  = compute_return(all_prices[pair], ts, 2.0)
            r6h  = compute_return(all_prices[pair], ts, 6.0)
            r24h = compute_return(all_prices[pair], ts, 24.0)
            fwd  = compute_forward_return(all_prices[pair], ts, FORWARD_HOURS)
            if None in (r1h, r2h, r6h, r24h, fwd):
                continue
            r30m_raw[pair] = r1h
            r2h_raw[pair]  = r2h
            r6h_raw[pair]  = r6h
            r24h_raw[pair] = r24h
            fwd_raw[pair]  = fwd

        if len(r6h_raw) < max(3, len(active_pairs) // 2):
            continue

        # ── Cross-sectional signals (existing) ──────────────────────────────────
        z30m = cross_sectional_z(r30m_raw)
        z2h  = cross_sectional_z(r2h_raw)
        z6h  = cross_sectional_z(r6h_raw)
        z24h = cross_sectional_z(r24h_raw)

        median_r2h_vals = sorted(r2h_raw.values())
        median_r2h = median_r2h_vals[len(median_r2h_vals) // 2]
        c1_raw_vals: Dict[str, float] = {}
        for pair in r6h_raw.keys():
            c1_raw_vals[pair] = (
                C1_WEIGHT_R30M  * r30m_raw.get(pair, 0.0)
                + C1_WEIGHT_R2H   * r2h_raw.get(pair, 0.0)
                + C1_WEIGHT_R6H   * r6h_raw.get(pair, 0.0)
                + C1_WEIGHT_R24H  * r24h_raw.get(pair, 0.0)
                + C1_WEIGHT_CS_RS * (r2h_raw.get(pair, 0.0) - median_r2h)
            )
        z_c1 = cross_sectional_z(c1_raw_vals)

        # ── TS signals (F1–F7): per-asset z-score → cross-sectional normalize ──
        # Step 1: compute per-asset TS scores using history BEFORE this ts
        computed: Dict[str, dict] = {}
        for pair in r6h_raw.keys():
            z6h_ts  = z_score(r6h_raw[pair],  ts_hist[pair]["r_6h"])
            z2h_ts  = z_score(r2h_raw[pair],  ts_hist[pair]["r_2h"])
            z24h_ts = z_score(r24h_raw[pair], ts_hist[pair]["r_24h"])

            # MA ratio: (current_price − MA_24h) / MA_24h, then TS z-scored
            ph = price_hist[pair]
            ma_ratio   = None
            ma_ratio_z = None
            if len(ph) >= 12:
                ma_24h = sum(ph[-24:]) / min(24, len(ph))
                cur_p  = all_prices[pair].get(ts)
                if cur_p and ma_24h > 0:
                    ma_ratio   = (cur_p - ma_24h) / ma_24h
                    ma_ratio_z = z_score(ma_ratio, ts_hist[pair]["ma_ratio"])

            # Volume ratio: current bar vol / rolling_mean(vol_48h)
            vol_ratio = None
            if all_volumes:
                cur_vol = (all_volumes.get(pair) or {}).get(ts)
                vh = vol_hist[pair]
                if cur_vol is not None and len(vh) >= 10:
                    mean_vol  = sum(vh[-48:]) / min(48, len(vh))
                    vol_ratio = cur_vol / mean_vol if mean_vol > 0 else None

            computed[pair] = {
                "z6h": z6h_ts, "z2h": z2h_ts, "z24h": z24h_ts,
                "ma_ratio": ma_ratio, "ma_ratio_z": ma_ratio_z, "vol_ratio": vol_ratio,
            }

        # Step 2: collect raw TS values for cross-sectional normalization
        f1_raw = {p: c["z6h"]  for p, c in computed.items()}
        f2_raw = {p: c["z2h"]  for p, c in computed.items()}
        f3_raw = {p: c["z24h"] for p, c in computed.items()}
        f4_raw = {p: c["ma_ratio_z"]                          for p, c in computed.items() if c["ma_ratio_z"]  is not None}
        f5_raw = {p: c["vol_ratio"]                           for p, c in computed.items() if c["vol_ratio"]   is not None}
        f6_raw = {p: c["z6h"] * min(c["vol_ratio"], 2.0)     for p, c in computed.items() if c["vol_ratio"]   is not None}
        f7_raw = {
            p: (0.35 * c["z6h"] + 0.35 * c["z2h"] + 0.20 * c["z24h"] + 0.10 * c["ma_ratio_z"])
            for p, c in computed.items() if c["ma_ratio_z"] is not None
        }

        n_min = max(3, len(active_pairs) // 4)
        z_f1 = cross_sectional_z(f1_raw) if len(f1_raw) >= n_min else {}
        z_f2 = cross_sectional_z(f2_raw) if len(f2_raw) >= n_min else {}
        z_f3 = cross_sectional_z(f3_raw) if len(f3_raw) >= n_min else {}
        z_f4 = cross_sectional_z(f4_raw) if len(f4_raw) >= n_min else {}
        z_f5 = cross_sectional_z(f5_raw) if len(f5_raw) >= n_min else {}
        z_f6 = cross_sectional_z(f6_raw) if len(f6_raw) >= n_min else {}
        z_f7 = cross_sectional_z(f7_raw) if len(f7_raw) >= n_min else {}

        # ── OFI signals (G1–G6): per-asset TS z-score → cross-sectional normalize ──
        # Uses taker buy vol, candle OHLC, quote vol, num trades from Binance klines.
        # History accessed BEFORE update (no look-ahead bias).
        ofi_computed: Dict[str, dict] = {}
        for pair in r6h_raw.keys():
            # G1: taker buy ratio = taker_buy_base_vol / base_vol
            tbr = None
            z_tbr = 0.0
            if all_tbvol and all_volumes:
                cur_tb = (all_tbvol.get(pair) or {}).get(ts)
                cur_bv = (all_volumes.get(pair) or {}).get(ts)
                if cur_tb is not None and cur_bv is not None and cur_bv > 0:
                    tbr   = cur_tb / cur_bv
                    z_tbr = z_score(tbr, tbr_hist[pair])

            # G2: candle body ratio = (close - open) / (high - low)
            body   = None
            z_body = 0.0
            if all_open and all_high and all_low:
                op = (all_open.get(pair) or {}).get(ts)
                hi = (all_high.get(pair) or {}).get(ts)
                lo = (all_low.get(pair)  or {}).get(ts)
                cl = all_prices[pair].get(ts)
                if None not in (op, hi, lo, cl):
                    hl = hi - lo
                    if hl > 0:
                        body   = (cl - op) / hl
                        z_body = z_score(body, body_hist[pair])

            # G3: quote volume TS z-score
            qv   = None
            z_qv = 0.0
            if all_qvol:
                qv = (all_qvol.get(pair) or {}).get(ts)
                if qv is not None:
                    z_qv = z_score(qv, qvol_hist[pair])

            # G4: num trades TS z-score
            nt   = None
            z_nt = 0.0
            if all_ntrades:
                nt = (all_ntrades.get(pair) or {}).get(ts)
                if nt is not None:
                    z_nt = z_score(nt, ntrades_hist[pair])

            # G5: tbr × |r6h| — OFI scaled by directional magnitude
            g5_raw_val = None
            z_g5_val   = 0.0
            if tbr is not None:
                g5_raw_val = tbr * abs(r6h_raw.get(pair, 0.0))
                z_g5_val   = z_score(g5_raw_val, g5_hist[pair])

            ofi_computed[pair] = {
                "tbr": tbr, "z_tbr": z_tbr,
                "body": body, "z_body": z_body,
                "qv": qv, "z_qv": z_qv,
                "nt": nt, "z_nt": z_nt,
                "g5_raw": g5_raw_val, "z_g5": z_g5_val,
            }

        # G1–G4: individual TS z-scores; G5: tbr×|r6h| TS z-score; G6: weighted composite
        g1_rd = {p: c["z_tbr"]  for p, c in ofi_computed.items() if c["tbr"]    is not None}
        g2_rd = {p: c["z_body"] for p, c in ofi_computed.items() if c["body"]   is not None}
        g3_rd = {p: c["z_qv"]   for p, c in ofi_computed.items() if c["qv"]     is not None}
        g4_rd = {p: c["z_nt"]   for p, c in ofi_computed.items() if c["nt"]     is not None}
        g5_rd = {p: c["z_g5"]   for p, c in ofi_computed.items() if c["g5_raw"] is not None}
        g6_rd = {
            p: 0.50 * c["z_tbr"] + 0.30 * c["z_body"] + 0.20 * c["z_nt"]
            for p, c in ofi_computed.items()
            if c["tbr"] is not None and c["body"] is not None and c["nt"] is not None
        }
        z_g1 = cross_sectional_z(g1_rd) if len(g1_rd) >= n_min else {}
        z_g2 = cross_sectional_z(g2_rd) if len(g2_rd) >= n_min else {}
        z_g3 = cross_sectional_z(g3_rd) if len(g3_rd) >= n_min else {}
        z_g4 = cross_sectional_z(g4_rd) if len(g4_rd) >= n_min else {}
        z_g5 = cross_sectional_z(g5_rd) if len(g5_rd) >= n_min else {}
        z_g6 = cross_sectional_z(g6_rd) if len(g6_rd) >= n_min else {}

        # Step 3: update TS histories AFTER computing all signals (no look-ahead)
        for pair in active_pairs:
            if pair in r6h_raw:
                ts_hist[pair]["r_6h"].append(r6h_raw[pair])
                ts_hist[pair]["r_2h"].append(r2h_raw[pair])
                ts_hist[pair]["r_24h"].append(r24h_raw[pair])
                for h in ("r_6h", "r_2h", "r_24h"):
                    if len(ts_hist[pair][h]) > TS_LOOKBACK:
                        ts_hist[pair][h] = ts_hist[pair][h][-TS_LOOKBACK:]

                c = computed.get(pair, {})
                if c.get("ma_ratio") is not None:
                    ts_hist[pair]["ma_ratio"].append(c["ma_ratio"])
                    if len(ts_hist[pair]["ma_ratio"]) > TS_LOOKBACK:
                        ts_hist[pair]["ma_ratio"] = ts_hist[pair]["ma_ratio"][-TS_LOOKBACK:]

            cur_p = all_prices[pair].get(ts)
            if cur_p:
                price_hist[pair].append(cur_p)
                if len(price_hist[pair]) > 48:
                    price_hist[pair] = price_hist[pair][-48:]

            if all_volumes:
                cur_vol = (all_volumes.get(pair) or {}).get(ts)
                if cur_vol is not None:
                    vol_hist[pair].append(cur_vol)
                    if len(vol_hist[pair]) > TS_LOOKBACK:
                        vol_hist[pair] = vol_hist[pair][-TS_LOOKBACK:]

            # OFI history updates (G1–G6)
            ofi_c = ofi_computed.get(pair, {})
            if ofi_c.get("tbr") is not None:
                tbr_hist[pair].append(ofi_c["tbr"])
                if len(tbr_hist[pair]) > TS_LOOKBACK:
                    tbr_hist[pair] = tbr_hist[pair][-TS_LOOKBACK:]
            if ofi_c.get("body") is not None:
                body_hist[pair].append(ofi_c["body"])
                if len(body_hist[pair]) > TS_LOOKBACK:
                    body_hist[pair] = body_hist[pair][-TS_LOOKBACK:]
            if ofi_c.get("qv") is not None:
                qvol_hist[pair].append(ofi_c["qv"])
                if len(qvol_hist[pair]) > TS_LOOKBACK:
                    qvol_hist[pair] = qvol_hist[pair][-TS_LOOKBACK:]
            if ofi_c.get("nt") is not None:
                ntrades_hist[pair].append(ofi_c["nt"])
                if len(ntrades_hist[pair]) > TS_LOOKBACK:
                    ntrades_hist[pair] = ntrades_hist[pair][-TS_LOOKBACK:]
            if ofi_c.get("g5_raw") is not None:
                g5_hist[pair].append(ofi_c["g5_raw"])
                if len(g5_hist[pair]) > TS_LOOKBACK:
                    g5_hist[pair] = g5_hist[pair][-TS_LOOKBACK:]

        # ── Accumulate IC data ──────────────────────────────────────────────────
        for pair in fwd_raw.keys():
            fwd_ret = fwd_raw[pair]
            if pair in z30m:  data["r_30m"].append((z30m[pair], fwd_ret))
            if pair in z2h:   data["r_2h"].append((z2h[pair], fwd_ret))
            if pair in z6h:   data["r_6h"].append((z6h[pair], fwd_ret))
            if pair in z24h:  data["r_24h"].append((z24h[pair], fwd_ret))
            if pair in z_c1:  data["C1_composite"].append((z_c1[pair], fwd_ret))
            if pair in z_f1:  data["F1_z6h"].append((z_f1[pair], fwd_ret))
            if pair in z_f2:  data["F2_z2h"].append((z_f2[pair], fwd_ret))
            if pair in z_f3:  data["F3_z24h"].append((z_f3[pair], fwd_ret))
            if pair in z_f4:  data["F4_ma"].append((z_f4[pair], fwd_ret))
            if pair in z_f5:  data["F5_vol"].append((z_f5[pair], fwd_ret))
            if pair in z_f6:  data["F6_z6h_vol"].append((z_f6[pair], fwd_ret))
            if pair in z_f7:  data["F7_composite"].append((z_f7[pair], fwd_ret))
            if pair in z_g1:  data["G1_tbr"].append((z_g1[pair], fwd_ret))
            if pair in z_g2:  data["G2_body"].append((z_g2[pair], fwd_ret))
            if pair in z_g3:  data["G3_qvol"].append((z_g3[pair], fwd_ret))
            if pair in z_g4:  data["G4_ntrades"].append((z_g4[pair], fwd_ret))
            if pair in z_g5:  data["G5_tbr_r6h"].append((z_g5[pair], fwd_ret))
            if pair in z_g6:  data["G6_composite"].append((z_g6[pair], fwd_ret))

    n_pairs = len(active_pairs)
    return {sig: compute_ic_stats(data[sig], n_pairs=n_pairs) for sig in signals_names}


# ── Main ──────────────────────────────────────────────────────────────────────

def fmt_ic(stats: dict) -> str:
    if stats.get("mean_ic") is None or stats.get("n", 0) < 5:
        return "N/A"
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
    return f"IC={ic:+.4f} t={t:+.2f} hit={hr:.0%} n={n}{flag}"


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
    print("  Extracting full OHLCV + taker/trade columns (G1–G6 OFI signals)...")
    current_months = _month_range_recent(CURRENT_LOOKBACK_MONTHS)
    (current_prices, current_bvol, current_qvol, current_nt,
     current_tb, current_open, current_high, current_low) = load_klines_all_parallel(pairs, current_months)
    current_volumes = current_bvol

    # Report coverage
    covered = sum(1 for p in current_prices.values() if len(p) > 100)
    print(f"  {covered}/{len(pairs)} pairs have data")

    print(f"\nDownloading trending-period data (Oct 2024–Jan 2025, {len(pairs)} pairs)...")
    trending_months = _month_range(TRENDING_START, TRENDING_END)
    (trending_prices, trending_bvol, trending_qvol, trending_nt,
     trending_tb, trending_open, trending_high, trending_low) = load_klines_all_parallel(pairs, trending_months)
    trending_volumes = trending_bvol

    covered_t = sum(1 for p in trending_prices.values() if len(p) > 100)
    print(f"  {covered_t}/{len(pairs)} pairs have data")

    # ── Run analysis ──────────────────────────────────────────────────────────
    print("\nRunning Test A: Current period (unconditional)...")
    results_A = run_analysis(
        current_prices, current_volumes, current_qvol, current_nt,
        current_tb, current_open, current_high, current_low, regime_filter=False,
    )

    print("Running Test B: Trending period (Oct 2024–Jan 2025)...")
    results_B = run_analysis(
        trending_prices, trending_volumes, trending_qvol, trending_nt,
        trending_tb, trending_open, trending_high, trending_low, regime_filter=False,
    )

    print("Running Test C: Current period (TREND-eligible hours only)...")
    results_C = run_analysis(
        current_prices, current_volumes, current_qvol, current_nt,
        current_tb, current_open, current_high, current_low, regime_filter=True,
    )

    # ── Format output ─────────────────────────────────────────────────────────
    cs_signals  = ["r_30m", "r_2h", "r_6h", "r_24h", "C1_composite"]
    ts_signals  = ["F1_z6h", "F2_z2h", "F3_z24h", "F4_ma", "F5_vol", "F6_z6h_vol", "F7_composite"]
    ofi_signals = ["G1_tbr", "G2_body", "G3_qvol", "G4_ntrades", "G5_tbr_r6h", "G6_composite"]
    all_signals = cs_signals + ts_signals + ofi_signals

    signal_labels = {
        "r_30m":        "1h ret(30m~)   ",
        "r_2h":         "2h return      ",
        "r_6h":         "6h return      ",
        "r_24h":        "24h return     ",
        "C1_composite": "C1 composite   ",
        "F1_z6h":       "F1: TS z_6h    ",
        "F2_z2h":       "F2: TS z_2h    ",
        "F3_z24h":      "F3: TS z_24h   ",
        "F4_ma":        "F4: TS MA-dev  ",
        "F5_vol":       "F5: vol ratio  ",
        "F6_z6h_vol":   "F6: z6h×vol    ",
        "F7_composite": "F7: TS compos. ",
        "G1_tbr":       "G1: taker_buy  ",
        "G2_body":      "G2: candle_body",
        "G3_qvol":      "G3: quote_vol  ",
        "G4_ntrades":   "G4: num_trades ",
        "G5_tbr_r6h":   "G5: tbr×|r6h|  ",
        "G6_composite": "G6: OFI compos.",
    }

    # Count filtered timestamps for Test C
    n_total_A = results_A.get("C1_composite", {}).get("n", 0)
    n_total_C = results_C.get("C1_composite", {}).get("n", 0)
    pct_trend_eligible = (n_total_C / n_total_A * 100) if n_total_A > 0 else 0

    lines = [
        "# Extended IC Validation — Multi-Signal, Multi-Period, Regime-Conditional",
        "",
        f"**Universe:** {len(pairs)} pairs  |  "
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Test Conditions",
        "",
        "- **A.** Current period (unconditional): Dec 2025–Feb 2026",
        "- **B.** Trending period (unconditional): Oct 2024–Jan 2025 — BTC +61% bull run",
        f"- **C.** Current period, TREND-eligible only: BTC vol z-score ≤ 0 "
        f"({pct_trend_eligible:.0f}% of timestamps)",
        "",
        "Forward return target: forward 6h return.  "
        "Significance: `*` IC>0 · `**` IC>0.03+t>1.0 · `***` IC>0.05+t>1.5",
        "",
        "## Part 1: Cross-Sectional Signal IC (baseline)",
        "",
        "| Signal | Test A (current) | Test B (trending) | Test C (TREND-cond.) |",
        "|--------|-----------------|-------------------|----------------------|",
    ]
    for sig in cs_signals:
        label = signal_labels[sig].strip()
        a = fmt_ic(results_A.get(sig, {}))
        b = fmt_ic(results_B.get(sig, {}))
        c = fmt_ic(results_C.get(sig, {}))
        lines.append(f"| {label} | {a} | {b} | {c} |")

    lines += [
        "",
        "## Part 2: Time-Series (TS) Signal IC — Candidate Formulas F1–F7",
        "",
        "Mechanism: per-asset TS z-score removes cross-section heterogeneity.  ",
        "Final cross-sectional normalization applied as allocation step (doctrine).  ",
        "F1–F3: pure TS momentum · F4: MA deviation anchor · F5: volume flow proxy · "
        "F6: volume-confirmed TS momentum · F7: multi-horizon composite.",
        "",
        "| Signal | Test A (current) | Test B (trending) | Test C (TREND-cond.) |",
        "|--------|-----------------|-------------------|----------------------|",
    ]
    for sig in ts_signals:
        label = signal_labels[sig].strip()
        a = fmt_ic(results_A.get(sig, {}))
        b = fmt_ic(results_B.get(sig, {}))
        c = fmt_ic(results_C.get(sig, {}))
        lines.append(f"| {label} | {a} | {b} | {c} |")

    lines += [
        "",
        "## Part 3: OFI Signal IC — Candidate Formulas G1–G6",
        "",
        "Mechanism: market (taker) buy orders reflect directional conviction — aggressive buyers "
        "pay the spread to get immediate execution. When taker buy fraction is abnormally high "
        "relative to own baseline, continuation pressure builds over next 6h.  ",
        "G1: pure taker buy ratio · G2: candle body conviction · G3: USD vol anomaly · "
        "G4: trade count anomaly · G5: OFI × directional magnitude · G6: OFI composite.  ",
        "Two-step: per-asset TS z-score (Binance klines col 9/5/7/8/1/2/3) → cross-sectional normalize.",
        "",
        "| Signal | Test A (current) | Test B (trending) | Test C (TREND-cond.) |",
        "|--------|-----------------|-------------------|----------------------|",
    ]
    for sig in ofi_signals:
        label = signal_labels[sig].strip()
        a = fmt_ic(results_A.get(sig, {}))
        b = fmt_ic(results_B.get(sig, {}))
        c = fmt_ic(results_C.get(sig, {}))
        lines.append(f"| {label} | {a} | {b} | {c} |")

    # ── Decision gate for TS + OFI formula selection ───────────────────────────
    lines += [
        "",
        "## Signal Selection — Decision Gate (F1–F7 + G1–G6)",
        "",
        "Gate: **IC > 0 in Test B** (trending period) **AND t > 1.0**.  ",
        "Tiebreak: highest IC Sharpe (mean_IC / std_IC across period ICs).",
        "",
        "| Formula | IC (Test B) | t-stat | IC Sharpe | Gate |",
        "|---------|------------|--------|-----------|------|",
    ]

    passing = []
    for sig in ts_signals + ofi_signals:
        ic_b = results_B.get(sig, {}).get("mean_ic") or 0
        t_b  = results_B.get(sig, {}).get("t_stat")  or 0
        period_ics = results_B.get(sig, {}).get("period_ics", [])
        std_ic = (math.sqrt(sum((v - ic_b) ** 2 for v in period_ics) / len(period_ics))
                  if len(period_ics) > 1 else 1e-8)
        ic_sharpe = ic_b / (std_ic or 1e-8)
        gate_pass = ic_b > 0 and t_b > 1.0
        status = "**PASS**" if gate_pass else "FAIL"
        lines.append(
            f"| {signal_labels[sig].strip()} | {ic_b:+.4f} | {t_b:+.2f} | {ic_sharpe:+.2f} | {status} |"
        )
        if gate_pass:
            passing.append((ic_sharpe, sig))

    lines.append("")
    if passing:
        passing.sort(key=lambda x: -x[0])
        best_ts = passing[0][1]
        lines += [
            f"**SELECTED:** {signal_labels[best_ts].strip()} "
            f"(IC Sharpe = {passing[0][0]:+.2f}, {len(passing)} formula(s) passed)",
            "",
            "**Implication:** Replace cross-sectional C1 with this TS signal.  ",
            "Update `config.py` `C1_TS_WEIGHT_*` and `signals.py` accordingly.",
        ]
    else:
        best_ts = None
        lines += [
            "**NO TS FORMULA passes the decision gate.**  ",
            "Strategy value rests on regime-gated drawdown control (Sortino/Calmar),  ",
            "not on selection alpha. Cross-sectional approach retained as-is.",
        ]

    # Overall interpretation
    composite_b = results_B.get("C1_composite", {})
    ic_b_c1 = composite_b.get("mean_ic") or 0
    t_b_c1  = composite_b.get("t_stat")  or 0

    lines += [
        "",
        "## Interpretation",
        "",
        f"**C1 composite (cross-sectional)** — Trending period: IC={ic_b_c1:+.4f}, t={t_b_c1:+.2f}",
    ]
    if best_ts:
        best_b = results_B.get(best_ts, {}).get("mean_ic") or 0
        best_t = results_B.get(best_ts, {}).get("t_stat")  or 0
        lines += [
            f"**{signal_labels[best_ts].strip()}** — Trending period: IC={best_b:+.4f}, t={best_t:+.2f}",
            "",
            "**Verdict:** TS momentum signal shows positive predictive power in the trending "
            "period. Per-asset normalization removes meme-coin contamination that caused "
            "cross-sectional rank to capture exhaustion/reversal rather than drift.  ",
            "**Recommendation:** Implement selected TS formula as C1 replacement.",
        ]
    else:
        lines += [
            "",
            "**Verdict:** Neither cross-sectional nor time-series momentum signals show "
            "statistically meaningful IC in the trending period.  ",
            "Strategy value is entirely in regime gating (Sortino) and kill switch (Calmar).  ",
            "**Recommendation:** No signal change warranted. Maintain current approach.",
        ]

    lines += [
        "",
        "## Notes",
        "",
        "- `r_30m` proxy: Binance Vision provides 1h bars; 1h return used as 30m proxy.",
        "- F5/F6 require volume data (Binance klines col 5).",
        "- G1–G6 require Binance klines cols 9 (taker_buy_base_vol), 1–3 (OHLC), 7 (quote_vol), 8 (num_trades).",
        "- TS/OFI signals use 48-period rolling baseline; first 3 periods return z=0 (warmup).",
        "- Two-step construction: (1) per-asset TS z-score → (2) cross-sectional normalize.",
        "",
        "Reference: `ic_results.md` for baseline unconditional IC, "
        "`backtest_results.md` for simulation results.",
    ]

    output = "\n".join(lines)
    sys.stdout.buffer.write(("\n" + output + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {OUTPUT_FILE}")

    # ── Optional: generate chart ──────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(CHARTS_DIR, exist_ok=True)

        def bar_colors(ics: List[float]) -> List[str]:
            out = []
            for ic in ics:
                if ic >= 0.04:
                    out.append("#2ecc71")
                elif ic > 0:
                    out.append("#f39c12")
                else:
                    out.append("#e74c3c")
            return out

        def draw_ic_bars(ax: "plt.Axes", sig_list: List[str], x_labels: List[str]) -> None:
            ic_A = [results_A.get(s, {}).get("mean_ic") or 0 for s in sig_list]
            ic_B = [results_B.get(s, {}).get("mean_ic") or 0 for s in sig_list]
            ic_C = [results_C.get(s, {}).get("mean_ic") or 0 for s in sig_list]
            x = range(len(sig_list))
            width = 0.25
            for ic_list, offset, lbl, alpha in [
                (ic_A, -width, "A: Current period",              0.65),
                (ic_B,      0, "B: Trending (Oct 2024–Jan 2025)", 0.85),
                (ic_C, +width, "C: TREND-conditional",            0.65),
            ]:
                positions = [xi + offset for xi in x]
                bars = ax.bar(positions, ic_list, width=width * 0.9,
                              label=lbl, color=bar_colors(ic_list), alpha=alpha,
                              edgecolor="white")
                for bar, val in zip(bars, ic_list):
                    ax.text(bar.get_x() + bar.get_width() / 2, val,
                            f"{val:+.3f}", ha="center",
                            va="bottom" if val >= 0 else "top",
                            fontsize=7, color="#2c3e50")
            ax.axhline(0,    color="black",   linewidth=0.8)
            ax.axhline(0.04, color="#2ecc71", linewidth=0.8, linestyle=":", alpha=0.7)
            ax.axhline(-0.04, color="#e74c3c", linewidth=0.8, linestyle=":", alpha=0.7)
            ax.set_xticks(list(x))
            ax.set_xticklabels(x_labels, fontsize=9)
            ax.set_ylabel("Spearman IC")
            all_vals = [results_A.get(s, {}).get("mean_ic") or 0 for s in sig_list] + \
                       [results_B.get(s, {}).get("mean_ic") or 0 for s in sig_list] + \
                       [results_C.get(s, {}).get("mean_ic") or 0 for s in sig_list]
            ax.set_ylim(min(all_vals) - 0.04, max(all_vals) + 0.07)

        cs_labels  = ["30m(~)", "2h", "6h", "24h", "C1"]
        ts_labels  = ["F1:z6h", "F2:z2h", "F3:z24h", "F4:MA", "F5:vol", "F6:z6h×vol", "F7:comp"]
        ofi_labels = ["G1:tbr", "G2:body", "G3:qvol", "G4:ntrd", "G5:tbr×r6h", "G6:OFI"]

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 15))

        draw_ic_bars(ax1, cs_signals, cs_labels)
        ax1.set_title(
            "Part 1: Cross-Sectional Signals (baseline)\n"
            "Green=IC≥0.04, Orange=0<IC<0.04, Red=IC<0",
            fontsize=10, fontweight="bold"
        )
        ax1.legend(fontsize=8, loc="upper right")

        draw_ic_bars(ax2, ts_signals, ts_labels)
        ax2.set_title(
            "Part 2: Time-Series (TS) Candidate Formulas F1–F7\n"
            "Two-step: per-asset TS z-score → cross-sectional normalization",
            fontsize=10, fontweight="bold"
        )
        ax2.legend(fontsize=8, loc="upper right")

        draw_ic_bars(ax3, ofi_signals, ofi_labels)
        ax3.set_title(
            "Part 3: Order Flow Imbalance (OFI) Candidate Formulas G1–G6\n"
            "Taker buy fraction, candle body, USD vol, trade count — Binance klines cols 1–3,7–9",
            fontsize=10, fontweight="bold"
        )
        ax3.legend(fontsize=8, loc="upper right")

        plt.tight_layout()
        chart_path = os.path.join(CHARTS_DIR, "ic_multi_horizon.png")
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Chart saved to {chart_path}")

    except ImportError:
        print("matplotlib not available — skipping chart generation")


if __name__ == "__main__":
    main()
