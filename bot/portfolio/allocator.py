"""
bot/portfolio/allocator.py — Portfolio allocation from ranked assets to target weights.

Allocation pipeline:
  1. Compute Kelly weights per asset (sizing.py)
  2. Score-weight within basket (override Kelly if scores vary widely)
  3. Apply 30% per-asset cap (MAX_POSITION_WEIGHT)
  4. Normalize to regime gross cap (e.g. 85% NAV for TREND_SUPPORTIVE)

The regime gross cap is the primary exposure control mechanism.
It translates the three-state regime into concrete capital deployment.

Final output: Dict[pair, target_nav_fraction] summing to ≤ regime_gross_cap.
"""
import logging
from typing import Dict, List, Optional

import config
from bot.data.feature_builder import AssetFeatures
from bot.portfolio.sizing import compute_kelly_weights
from bot.strategy.ranking import RankedAsset
from bot.strategy.regime import RegimeState

logger = logging.getLogger(__name__)


def compute_target_weights(
    ranked_assets: List[RankedAsset],
    asset_features: Dict[str, AssetFeatures],
    regime: RegimeState,
    drawdown_gross_override: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute final target portfolio weights for each ranked asset.

    Args:
        ranked_assets:          Sorted eligible assets from ranking.py.
        asset_features:         Per-asset feature data.
        regime:                 Current market regime.
        drawdown_gross_override: Override gross cap if drawdown level requires reduction.

    Returns:
        Dict[pair, target_weight_as_fraction_of_NAV].
        Empty dict if regime is HAZARD_DEFENSIVE or no ranked assets.
    """
    if not ranked_assets:
        return {}

    params = config.REGIME_PARAMS[regime.value]
    if params["max_positions"] == 0:
        return {}

    gross_cap = drawdown_gross_override if drawdown_gross_override is not None else params["gross_cap"]

    # ── Step 1: Kelly weights ──────────────────────────────────────────────────
    kelly_weights = compute_kelly_weights(ranked_assets, asset_features)

    # ── Step 2: Score-weighted blend ──────────────────────────────────────────
    # Blend Kelly with score-proportional weights; use whichever is tighter.
    total_score = sum(a.position_score for a in ranked_assets if a.position_score > 0)
    if total_score <= 0:
        return {}

    raw_weights: Dict[str, float] = {}
    for asset in ranked_assets:
        score_w = asset.position_score / total_score
        kelly_w = kelly_weights.get(asset.pair, score_w)
        # Take the minimum — more conservative when signals diverge
        raw_weights[asset.pair] = min(score_w, kelly_w) if kelly_w < score_w else score_w

    # ── Step 3: Apply per-asset concentration cap ─────────────────────────────
    capped: Dict[str, float] = {
        pair: min(w, config.MAX_POSITION_WEIGHT)
        for pair, w in raw_weights.items()
    }

    # ── Step 4: Normalize to gross cap ────────────────────────────────────────
    total_capped = sum(capped.values())
    if total_capped <= 0:
        return {}

    target_weights: Dict[str, float] = {
        pair: w / total_capped * gross_cap
        for pair, w in capped.items()
    }

    logger.info(
        "Target weights (regime=%s, gross_cap=%.0f%%): %s",
        regime.value,
        gross_cap * 100,
        {p: f"{w:.1%}" for p, w in target_weights.items()},
    )
    return target_weights


def weights_to_usd(
    target_weights: Dict[str, float],
    total_nav_usd: float,
) -> Dict[str, float]:
    """
    Convert NAV-fraction weights to USD target position values.

    Args:
        target_weights: Dict[pair, nav_fraction] from compute_target_weights.
        total_nav_usd:  Current portfolio NAV in USD.

    Returns:
        Dict[pair, target_usd_value].
    """
    return {pair: w * total_nav_usd for pair, w in target_weights.items()}
