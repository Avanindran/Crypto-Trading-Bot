"""
bot/data/feature_builder.py — Raw feature computation from market cache.

Computes per-asset features used by the regime, signal, and maturity layers.
All transforms are backward-looking: only use data available at observation time.

Feature taxonomy (per Signal Construction Doctrine):
  - Velocity (momentum):  r_30m, r_2h, r_6h, r_24h
  - Level:                sma_12h, atr_12h, spread_pct
  - Derived:              realized_vol_1h, realized_vol_6h, rsi_proxy_6h

Cross-sectional features (require universe-level computation):
  - cs_median_r2h:   Median 2h return across universe (for relative strength)
  - cs_std_r30m:     Cross-sectional std of 30m returns (dispersion measure for LSI)
"""
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from bot.data.market_cache import MarketCache

logger = logging.getLogger(__name__)

# ── Lookback windows in number of 1-minute snapshots ──────────────────────────
_N_30M = 30
_N_2H = 120
_N_6H = 360
_N_12H = 720
_N_48H = 2880  # Used for percentile rank lookback (capped by CACHE_MAXLEN=300)


@dataclass
class AssetFeatures:
    """All computed features for one asset at one point in time."""
    pair: str

    # Momentum velocities
    r_30m: Optional[float] = None       # 30-minute return
    r_2h: Optional[float] = None        # 2-hour return
    r_6h: Optional[float] = None        # 6-hour return (primary C1 horizon)
    r_24h: Optional[float] = None       # 24-hour return (from ticker Change field)

    # Volatility
    realized_vol_1h: Optional[float] = None    # Std of 30m returns over 2h window (6 samples)
    realized_vol_6h: Optional[float] = None    # Std of 30m returns over 12h window (24 samples)
    downside_vol_6h: Optional[float] = None    # Downside vol for Kelly sizing

    # Price levels
    sma_12h: Optional[float] = None     # Simple MA of last 720 snapshots
    atr_12h: Optional[float] = None     # Proxy ATR from std of returns * price

    # Maturity inputs
    extension: Optional[float] = None          # (price - sma_12h) / atr_12h
    rsi_proxy: Optional[float] = None          # avg_up / (avg_up + avg_dn) over 6h
    pct_rank_r6h: Optional[float] = None       # Percentile rank of r_6h vs stored history

    # Market microstructure
    spread_pct: Optional[float] = None         # (ask - bid) / last_price

    # External positioning signal (from Binance perpetual funding rates)
    funding_rate: Optional[float] = None       # Current 8h funding rate (e.g. 0.0001 = 0.01%)

    # Flags
    has_enough_data: bool = False


def _safe_return(prices: List[float], n_back: int) -> Optional[float]:
    """
    Compute percentage return over the last n_back snapshots.
    Returns None if insufficient data.
    """
    if len(prices) < n_back + 1:
        return None
    p_now = prices[-1]
    p_then = prices[-(n_back + 1)]
    if p_then <= 0:
        return None
    return (p_now - p_then) / p_then


def _realized_vol(prices: List[float], window: int, step: int = _N_30M) -> Optional[float]:
    """
    Compute realized volatility as std of step-period returns over a window.
    step=30 and window=360 → std of 30m returns over 6h (12 observations).
    """
    if len(prices) < window + step:
        return None
    returns = []
    for i in range(step, min(window + step, len(prices)), step):
        p0 = prices[-(i + step)] if (i + step) <= len(prices) else None
        p1 = prices[-i] if i <= len(prices) else None
        if p0 and p1 and p0 > 0:
            returns.append((p1 - p0) / p0)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var)


def _downside_vol(prices: List[float], window: int, step: int = _N_30M) -> Optional[float]:
    """Standard deviation of negative returns only (Sortino denominator)."""
    if len(prices) < window + step:
        return None
    neg_returns = []
    for i in range(step, min(window + step, len(prices)), step):
        p0 = prices[-(i + step)] if (i + step) <= len(prices) else None
        p1 = prices[-i] if i <= len(prices) else None
        if p0 and p1 and p0 > 0:
            r = (p1 - p0) / p0
            if r < 0:
                neg_returns.append(r)
    if len(neg_returns) < 2:
        return None
    mean = sum(neg_returns) / len(neg_returns)
    var = sum((r - mean) ** 2 for r in neg_returns) / (len(neg_returns) - 1)
    return math.sqrt(var)


def _rsi_proxy(prices: List[float], window: int = _N_6H) -> Optional[float]:
    """
    RSI-like proxy: avg_up / (avg_up + avg_dn) over the window.
    Returns value in [0, 1]; 0.5 = neutral.
    """
    n = min(window, len(prices) - 1)
    if n < 10:
        return None
    ups, dns = [], []
    for i in range(n):
        delta = prices[-(i + 1)] - prices[-(i + 2)]
        if delta > 0:
            ups.append(delta)
        elif delta < 0:
            dns.append(abs(delta))
    avg_up = sum(ups) / n
    avg_dn = sum(dns) / n
    denom = avg_up + avg_dn
    if denom <= 0:
        return 0.5
    return avg_up / denom


def _percentile_rank(value: float, series: List[float]) -> Optional[float]:
    """Rank of value in series, expressed as a fraction in [0, 1]."""
    if not series:
        return None
    below = sum(1 for v in series if v < value)
    return below / len(series)


def _sma(prices: List[float], window: int) -> Optional[float]:
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window


def _atr_proxy(prices: List[float], window: int, step: int = _N_30M) -> Optional[float]:
    """ATR proxy: std of returns * current price."""
    vol = _realized_vol(prices, window, step)
    if vol is None or not prices:
        return None
    return vol * prices[-1]


# ── Per-asset feature computation ─────────────────────────────────────────────

def compute_asset_features(pair: str, cache: MarketCache) -> AssetFeatures:
    """
    Compute all features for a single asset from its cache history.

    Args:
        pair:  Trading pair symbol (e.g. "BTC/USD").
        cache: Populated MarketCache instance.

    Returns:
        AssetFeatures with available fields populated.
    """
    feat = AssetFeatures(pair=pair)

    prices = cache.prices(pair, _N_12H + _N_30M + 10)  # Extra buffer
    n = len(prices)

    if n < 5:
        return feat  # Not enough data for any feature

    # ── Returns ──────────────────────────────────────────────────────────────
    feat.r_30m = _safe_return(prices, _N_30M)
    feat.r_2h = _safe_return(prices, _N_2H)
    feat.r_6h = _safe_return(prices, _N_6H)

    # r_24h: use ticker Change field directly (available from loop 1)
    snap = cache.latest(pair)
    if snap is not None:
        feat.r_24h = snap.change_24h
        feat.spread_pct = cache.spread_pct(pair)

    # ── Volatility ───────────────────────────────────────────────────────────
    feat.realized_vol_1h = _realized_vol(prices, window=120, step=_N_30M)   # 2h window, 30m steps
    feat.realized_vol_6h = _realized_vol(prices, window=_N_6H, step=_N_30M)
    feat.downside_vol_6h = _downside_vol(prices, window=_N_6H, step=_N_30M)

    # ── Price levels (for M_t extension) ────────────────────────────────────
    feat.sma_12h = _sma(prices, min(_N_12H, n))
    feat.atr_12h = _atr_proxy(prices, min(_N_12H, n))

    if feat.sma_12h and feat.atr_12h and feat.atr_12h > 0 and prices:
        feat.extension = (prices[-1] - feat.sma_12h) / feat.atr_12h

    # ── RSI proxy ────────────────────────────────────────────────────────────
    feat.rsi_proxy = _rsi_proxy(prices, min(_N_6H, n - 1))

    # ── Percentile rank of r_6h vs cached history ────────────────────────────
    if feat.r_6h is not None:
        # Build historical r_6h series from available cache data
        all_snaps = cache.all_snapshots(pair)
        hist_r6h = []
        for i in range(_N_6H, len(all_snaps)):
            p_now = all_snaps[i].last_price
            p_old = all_snaps[i - _N_6H].last_price
            if p_old > 0:
                hist_r6h.append((p_now - p_old) / p_old)
        if len(hist_r6h) >= 5:
            feat.pct_rank_r6h = _percentile_rank(feat.r_6h, hist_r6h)

    feat.has_enough_data = (feat.r_6h is not None and feat.r_2h is not None)
    return feat


# ── Universe-level cross-sectional features ───────────────────────────────────

@dataclass
class CrossSectionalFeatures:
    """Market-wide aggregates computed across all active pairs."""
    median_r2h: float = 0.0         # Used in C1 relative strength term
    std_r30m: float = 0.0           # Cross-section std of 30m returns (LSI dispersion proxy)
    median_spread_pct: float = 0.0  # Median bid-ask spread (LSI illiquidity proxy)
    n_pairs: int = 0


def compute_cross_sectional(
    asset_features: Dict[str, AssetFeatures]
) -> CrossSectionalFeatures:
    """
    Compute cross-sectional statistics across all assets with enough data.

    Args:
        asset_features: Dict of pair → AssetFeatures.

    Returns:
        CrossSectionalFeatures with market-wide aggregates.
    """
    cs = CrossSectionalFeatures()

    r2h_vals = [f.r_2h for f in asset_features.values() if f.r_2h is not None]
    r30m_vals = [f.r_30m for f in asset_features.values() if f.r_30m is not None]
    spread_vals = [f.spread_pct for f in asset_features.values() if f.spread_pct is not None]

    cs.n_pairs = len(r2h_vals)

    if r2h_vals:
        cs.median_r2h = sorted(r2h_vals)[len(r2h_vals) // 2]

    if len(r30m_vals) >= 2:
        mean_30m = sum(r30m_vals) / len(r30m_vals)
        var = sum((r - mean_30m) ** 2 for r in r30m_vals) / len(r30m_vals)
        cs.std_r30m = math.sqrt(var)

    if spread_vals:
        cs.median_spread_pct = sorted(spread_vals)[len(spread_vals) // 2]

    return cs


def build_all_features(
    cache: MarketCache,
    active_pairs: Optional[List[str]] = None,
    funding_rates: Optional[Dict[str, float]] = None,
) -> tuple[Dict[str, AssetFeatures], CrossSectionalFeatures]:
    """
    Compute features for all active pairs and cross-sectional aggregates.

    Args:
        cache:          Populated MarketCache.
        active_pairs:   Subset of pairs to compute (all cache pairs if None).
        funding_rates:  Optional dict of pair → Binance funding rate. When provided,
                        the funding_rate field is populated on each AssetFeatures.

    Returns:
        (asset_features_dict, cross_sectional_features)
    """
    pairs = active_pairs if active_pairs is not None else cache.pairs
    asset_features: Dict[str, AssetFeatures] = {}

    for pair in pairs:
        try:
            feat = compute_asset_features(pair, cache)
            if funding_rates is not None:
                feat.funding_rate = funding_rates.get(pair, None)
            asset_features[pair] = feat
        except Exception as exc:
            logger.warning("Feature computation failed for %s: %s", pair, exc)

    cs = compute_cross_sectional(asset_features)
    return asset_features, cs
