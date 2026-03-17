"""
bot/strategy/maturity.py — Diffusion Maturity M_t computation (C3 = 1 − M_t).

M_t ∈ [0, 1] represents the fraction of the expected drift that has already
been reflected in price. It gates and scales C1:

  C3_i = 1 − M_t_i  (remaining drift capacity)
  M_t = 0 → completely fresh entry (maximum C3)
  M_t = 1 → fully diffused / overextended (C3 = 0, no entry)

Composed of four sub-signals:
  1. Extension from 12h SMA (how far price has moved from anchor)
  2. RSI proxy (avg_up / (avg_up + avg_dn)) over 6h window
  3. Percentile rank of current 6h return vs historical 6h returns
  4. Funding rate (Binance perp) — crowded long positioning = drift already captured

Each sub-signal is normalized to [0, 1] before composition.
The funding rate component is omitted gracefully when data is unavailable.
"""
import logging
import math
from typing import Dict, Optional

import config
from bot.data.feature_builder import AssetFeatures

logger = logging.getLogger(__name__)

# Rolling normalization state per pair (min/max over recent history)
_ext_history: Dict[str, list] = {}
_rank_history: Dict[str, list] = {}
_MAX_HISTORY = 100  # Keep last 100 observations per pair for normalization


def _min_max_norm(value: float, history: list) -> float:
    """Normalize value to [0, 1] using min/max of history."""
    if len(history) < 3:
        return 0.5  # Neutral before enough data
    lo, hi = min(history), max(history)
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _funding_rate_component(funding_rate: Optional[float]) -> Optional[float]:
    """
    Normalize funding rate to a [0, 1] maturity component.

    High positive funding (longs paying shorts) signals crowded positioning:
    the expected drift has already been captured by leveraged participants,
    so diffusion maturity is elevated.

    Negative or near-zero funding indicates fresh/bearish positioning —
    the component contributes 0 (no maturity penalty for unloved assets).

    Returns None if funding_rate is None (component omitted from M_t).
    """
    if funding_rate is None:
        return None
    component = (funding_rate - config.FUNDING_RATE_NEUTRAL) / config.FUNDING_RATE_SCALE
    return max(0.0, min(1.0, component))


def compute_maturity(pair: str, feat: AssetFeatures) -> Optional[float]:
    """
    Compute diffusion maturity M_t ∈ [0, 1] for one asset.

    Args:
        pair: Trading pair symbol (for history tracking).
        feat: Pre-computed AssetFeatures for this asset.

    Returns:
        M_t in [0, 1], or None if insufficient data.
    """
    components = []
    weights = []

    # ── Component 1: Extension from 12h SMA ─────────────────────────────────
    # High extension (far above SMA) → high maturity (drift is spent)
    if feat.extension is not None:
        if pair not in _ext_history:
            _ext_history[pair] = []
        _ext_history[pair].append(feat.extension)
        if len(_ext_history[pair]) > _MAX_HISTORY:
            _ext_history[pair] = _ext_history[pair][-_MAX_HISTORY:]
        ext_norm = _min_max_norm(feat.extension, _ext_history[pair])
        components.append(ext_norm)
        weights.append(config.MT_WEIGHT_EXTENSION)

    # ── Component 2: RSI proxy ────────────────────────────────────────────────
    # High RSI (>0.7) → overbought → high maturity
    if feat.rsi_proxy is not None:
        components.append(feat.rsi_proxy)   # Already in [0, 1]; 0.5 = neutral
        weights.append(config.MT_WEIGHT_RSI_PROXY)

    # ── Component 3: Percentile rank of r_6h ─────────────────────────────────
    # High percentile → this is already a stretched move → high maturity
    if feat.pct_rank_r6h is not None:
        components.append(feat.pct_rank_r6h)  # Already in [0, 1]
        weights.append(config.MT_WEIGHT_PCT_RANK)

    # ── Component 4: Funding rate (Binance perp) ─────────────────────────────
    # High positive funding → crowded long positioning → drift already captured
    # Falls back gracefully if funding data unavailable
    fr_component = _funding_rate_component(feat.funding_rate)
    if fr_component is not None:
        components.append(fr_component)
        weights.append(config.MT_WEIGHT_FUNDING)

    if not components:
        return None

    # Weights are normalized by their sum — so M_t is correct even when
    # funding rate component is absent (e.g. pair not listed on Binance perps)
    total_w = sum(weights)
    if total_w <= 0:
        return None

    m_t = sum(c * w for c, w in zip(components, weights)) / total_w
    m_t = max(0.0, min(1.0, m_t))

    logger.debug(
        "Maturity %s: M_t=%.3f (ext=%s rsi=%s rank=%s funding=%s)",
        pair,
        m_t,
        f"{feat.extension:.3f}" if feat.extension else "N/A",
        f"{feat.rsi_proxy:.3f}" if feat.rsi_proxy else "N/A",
        f"{feat.pct_rank_r6h:.3f}" if feat.pct_rank_r6h else "N/A",
        f"{feat.funding_rate:.5f}" if feat.funding_rate is not None else "N/A",
    )
    return m_t


def compute_all_maturity(
    asset_features: Dict[str, AssetFeatures],
) -> Dict[str, float]:
    """
    Compute M_t for all assets with available data.

    Returns:
        Dict[pair, M_t] — only pairs with valid maturity included.
    """
    result: Dict[str, float] = {}
    for pair, feat in asset_features.items():
        m_t = compute_maturity(pair, feat)
        if m_t is not None:
            result[pair] = m_t
    return result
