"""
bot/portfolio/sizing.py — Position sizing using Quarter-Kelly criterion.

Quarter-Kelly targeting Sortino ratio maximization:

  kelly_f_i = 0.25 × (expected_r_6h_i / downside_vol_6h_i²)

The Kelly fraction maximizes long-run geometric compounding (growth-optimal objective).
Quarter-Kelly applies an overconfidence correction — typical in live trading.
The denominator uses DOWNSIDE variance only, which directly targets Sortino
by penalizing sizing in assets with large negative return risk.

Bounds: [MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT] per config.
"""
import logging
from typing import Dict, List, Optional

import config
from bot.data.feature_builder import AssetFeatures
from bot.strategy.ranking import RankedAsset

logger = logging.getLogger(__name__)


def _kelly_weight(
    expected_return: float,
    downside_vol: float,
) -> float:
    """
    Compute quarter-Kelly position weight.

    Args:
        expected_return: Proxy for expected 6h return (C1 raw score scaled).
        downside_vol:    Downside volatility of 6h returns (std of negative returns).

    Returns:
        Weight in [MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT].
    """
    if downside_vol <= 0:
        return config.MIN_POSITION_WEIGHT

    kelly = config.KELLY_FRACTION * (expected_return / (downside_vol ** 2))
    return max(config.MIN_POSITION_WEIGHT, min(config.MAX_POSITION_WEIGHT, kelly))


def compute_kelly_weights(
    ranked_assets: List[RankedAsset],
    asset_features: Dict[str, AssetFeatures],
) -> Dict[str, float]:
    """
    Compute Kelly-adjusted target weights for a basket of ranked assets.

    For assets without downside vol data, falls back to equal weighting
    within the Kelly bounds.

    Args:
        ranked_assets:  Sorted list of eligible assets from ranking.py.
        asset_features: Per-asset feature data (for downside vol).

    Returns:
        Dict[pair, target_weight] — raw weights (not yet normalized to gross cap).
    """
    weights: Dict[str, float] = {}

    for asset in ranked_assets:
        feat = asset_features.get(asset.pair)
        downside_vol = feat.downside_vol_6h if feat else None

        if downside_vol and downside_vol > 0:
            # Use C1 score as proxy for expected return
            # (higher momentum score → higher expected drift)
            expected_r = max(0.0, asset.c1_score * 0.005)  # Scale: z=1 → ~0.5% expected
            w = _kelly_weight(expected_r, downside_vol)
        else:
            # Fall back to equal weight within limits when vol not available
            n = len(ranked_assets)
            w = max(config.MIN_POSITION_WEIGHT, min(config.MAX_POSITION_WEIGHT, 1.0 / n))

        weights[asset.pair] = w
        logger.debug("Kelly weight %s: %.3f", asset.pair, w)

    return weights
