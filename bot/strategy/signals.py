"""
bot/strategy/signals.py — C1 Alpha Signal (F-layer / Signal only).

Computes the cross-sectional z-score of asset momentum strength.

Formula:
  raw_i = w1*r_30m + w2*r_2h + w3*r_6h + w4*r_24h + w5*(r_2h - median_r2h)
  C1_i  = (raw_i - mean(raw)) / std(raw)   [cross-sectional z-score]

Role separation (signal layer only):
  - C1 contains ONLY asset-specific continuation signals.
  - No regime state (breadth, BTC trend) enters C1.
  - Relative strength uses cross-sectional median (not BTC) to avoid anchoring bias.
"""
import logging
import math
from typing import Dict, Optional

import config
from bot.data.feature_builder import AssetFeatures, CrossSectionalFeatures

logger = logging.getLogger(__name__)


def _compute_raw_score(
    feat: AssetFeatures,
    cs_median_r2h: float,
) -> Optional[float]:
    """
    Compute the un-normalized C1 raw score for one asset.

    Returns None if critical features are missing.
    """
    if not feat.has_enough_data:
        return None

    # r_6h is the primary signal; require it
    if feat.r_6h is None:
        return None

    score = 0.0
    total_weight = 0.0

    if feat.r_30m is not None:
        score += config.C1_WEIGHT_R30M * feat.r_30m
        total_weight += config.C1_WEIGHT_R30M

    if feat.r_2h is not None:
        score += config.C1_WEIGHT_R2H * feat.r_2h
        total_weight += config.C1_WEIGHT_R2H

    score += config.C1_WEIGHT_R6H * feat.r_6h
    total_weight += config.C1_WEIGHT_R6H

    if feat.r_24h is not None:
        score += config.C1_WEIGHT_R24H * feat.r_24h
        total_weight += config.C1_WEIGHT_R24H

    # Cross-sectional relative strength (vs median, not BTC)
    if feat.r_2h is not None:
        cs_rs = feat.r_2h - cs_median_r2h
        score += config.C1_WEIGHT_CS_RS * cs_rs
        total_weight += config.C1_WEIGHT_CS_RS

    if total_weight <= 0:
        return None

    return score / total_weight


def compute_c1_scores(
    asset_features: Dict[str, AssetFeatures],
    cs: CrossSectionalFeatures,
) -> Dict[str, float]:
    """
    Compute cross-sectional z-score C1 scores for all eligible assets.

    Assets with insufficient data are excluded from the universe used
    for z-score normalization.

    Args:
        asset_features: Per-asset features from feature_builder.
        cs:             Cross-sectional aggregates.

    Returns:
        Dict[pair, c1_z_score] — scores are z-normalized (mean 0, std 1).
        Only pairs with valid data are included.
    """
    raw_scores: Dict[str, float] = {}

    for pair, feat in asset_features.items():
        raw = _compute_raw_score(feat, cs.median_r2h)
        if raw is not None:
            raw_scores[pair] = raw

    if len(raw_scores) < 2:
        # Not enough pairs for meaningful cross-sectional normalization
        return {}

    # Cross-sectional z-score normalization
    vals = list(raw_scores.values())
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var) if var > 0 else 1e-8

    c1_scores: Dict[str, float] = {}
    for pair, raw in raw_scores.items():
        c1_scores[pair] = (raw - mean) / std

    logger.debug(
        "C1 scores computed for %d pairs — mean=%.3f std=%.3f top=%s",
        len(c1_scores),
        mean,
        std,
        sorted(c1_scores.items(), key=lambda x: -x[1])[:3],
    )
    return c1_scores
