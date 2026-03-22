"""
bot/portfolio/allocator.py — Portfolio allocation from ranked assets to target weights.

Allocation pipeline:
  1. Score-proportional weights (research-validated: IC-Sharpe 11.35 > Kelly 10.48)
     IC-Sharpe = mean(IC) / std(IC) × √n — measures signal consistency:
     a scheme with stable IC across time beats one with equal mean but high variance.
  2. Apply 30% per-asset cap (MAX_POSITION_WEIGHT)
  3. Normalize to regime gross cap (e.g. 85% NAV for TREND_SUPPORTIVE)

The regime gross cap is the primary exposure control mechanism.
It translates the three-state regime into concrete capital deployment.

Final output: Dict[pair, target_nav_fraction] summing to ≤ regime_gross_cap.
"""
import logging
from typing import Dict, List, Optional

import config
from bot.strategy.ranking import RankedAsset
from bot.strategy.regime import RegimeState

logger = logging.getLogger(__name__)


def compute_target_weights(
    ranked_assets: List[RankedAsset],
    regime: RegimeState,
    drawdown_gross_override: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute final target portfolio weights for each ranked asset.

    Uses score-proportional allocation — the method validated in research
    (IC-Sharpe 11.35). Kelly sizing collapses to near-equal weights in practice
    and was not the deployed method in backtests.

    Args:
        ranked_assets:           Sorted eligible assets from ranking.py.
        regime:                  Current market regime.
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

    # ── Score-proportional allocation ─────────────────────────────────────────
    total_score = sum(a.position_score for a in ranked_assets if a.position_score > 0)
    if total_score <= 0:
        return {}

    raw_weights: Dict[str, float] = {
        a.pair: a.position_score / total_score for a in ranked_assets
    }

    # ── Per-asset concentration cap ───────────────────────────────────────────
    capped: Dict[str, float] = {
        pair: min(w, config.MAX_POSITION_WEIGHT)
        for pair, w in raw_weights.items()
    }

    # ── Normalize to gross cap ─────────────────────────────────────────────────
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
