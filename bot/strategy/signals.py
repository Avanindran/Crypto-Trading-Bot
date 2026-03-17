"""
bot/strategy/signals.py — Promoted alpha signal (F-layer / Signal only).

Computes the GP-selected combination signal from Phase 3 of the research pipeline:

  raw_i        = w1*r_30m + w2*r_2h + w3*r_6h + w4*r_24h + w5*(r_2h - median_r2h)
  neg_c1_z_i   = CS_z(−raw_i)       [H1 reversal: recent laggards outperform]
  neg_vol_z_i  = CS_z(−rvol_6h_i)   [H5 low-vol anomaly: stable coins outperform]
  C1_i         = 0.70 × neg_c1_z_i  +  0.30 × neg_vol_z_i

Validated in research/03_validation/ and research/04_gp_search/:
  IC at 4h horizon — train: +0.047 (t=7.2), holdout: +0.066 (t=10.6)
  Decision: PROMOTED (IC > 0.03, t > 1.5, positive holdout)

Economic description: "buy cross-sectional laggards with low realized volatility"
  - High C1 → recent laggard AND stable (low vol) → expected mean-reversion recovery
  - Low C1  → recent winner OR high-vol meme-coin pump → expected to underperform

Role separation (signal layer only):
  - C1 contains ONLY asset-specific reversal and stability signals.
  - No regime state (breadth, BTC trend) enters C1.
  - If realized_vol_6h is unavailable, falls back to reversal-only signal.
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
    # ── Step 1: Compute C1 raw momentum composite ────────────────────────────
    raw_scores: Dict[str, float] = {}
    for pair, feat in asset_features.items():
        raw = _compute_raw_score(feat, cs.median_r2h)
        if raw is not None:
            raw_scores[pair] = raw

    if len(raw_scores) < 2:
        return {}

    # ── Step 2: CS_z(−raw) — H1 reversal component ───────────────────────────
    # Negate so that cross-sectional laggards (low raw) receive high scores.
    vals_raw = list(raw_scores.values())
    mean_raw = sum(vals_raw) / len(vals_raw)
    var_raw = sum((v - mean_raw) ** 2 for v in vals_raw) / len(vals_raw)
    std_raw = math.sqrt(var_raw) if var_raw > 0 else 1e-8
    neg_c1_z: Dict[str, float] = {
        pair: -(raw - mean_raw) / std_raw for pair, raw in raw_scores.items()
    }

    # ── Step 3: Gather −realized_vol_6h — H5 stability component ─────────────
    neg_vol_raw: Dict[str, float] = {
        pair: -feat.realized_vol_6h
        for pair, feat in asset_features.items()
        if pair in raw_scores
        and feat.realized_vol_6h is not None
        and feat.realized_vol_6h > 0
    }

    # ── Step 4: CS_z(−realized_vol_6h) ───────────────────────────────────────
    neg_vol_z: Dict[str, float] = {}
    if len(neg_vol_raw) >= 2:
        vv = list(neg_vol_raw.values())
        mean_v = sum(vv) / len(vv)
        var_v = sum((v - mean_v) ** 2 for v in vv) / len(vv)
        std_v = math.sqrt(var_v) if var_v > 0 else 1e-8
        neg_vol_z = {pair: (v - mean_v) / std_v for pair, v in neg_vol_raw.items()}

    # ── Step 5: Combine 0.70 × reversal + 0.30 × stability ───────────────────
    # Falls back to reversal-only (neg_vol_z contribution = 0) when vol unavailable.
    c1_scores: Dict[str, float] = {}
    for pair, rev in neg_c1_z.items():
        stab = neg_vol_z.get(pair, 0.0)
        c1_scores[pair] = (
            config.ALPHA_WEIGHT_REVERSAL * rev + config.ALPHA_WEIGHT_STABILITY * stab
        )

    logger.debug(
        "C1 scores computed for %d pairs (vol available: %d) — top=%s",
        len(c1_scores),
        len(neg_vol_z),
        sorted(c1_scores.items(), key=lambda x: -x[1])[:3],
    )
    return c1_scores
