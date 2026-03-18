"""
bot/strategy/ranking.py — Position scoring and asset ranking.

Implements the core scoring formula for Transitional-Drift Momentum:

  PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)

Where:
  C1_i   = Asset momentum z-score (F-layer / alpha signal)
  λ_t    = Market hazard rate from regime engine (C-layer / governance)
  M_t_i  = Per-asset diffusion maturity; (1 − M_t) = remaining drift capacity (C3)

The exponential hazard form (not linear) is intentional:
  - exp(−λ_t) → ~1.0 when λ_t is low (calm, trend)
  - exp(−λ_t) → ~0.02 when λ_t = 4.0 (defensive)
  - exp(−λ_t) → ~0.0  when λ_t = 10.0 (emergency)

Ranking pipeline:
  1. Compute PositionScore for all pairs with valid C1 and M_t
  2. Filter: C1_z > entry_threshold AND M_t < max_maturity
  3. Sort descending and take top max_positions
"""
import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import config
from bot.strategy.regime import RegimeState

logger = logging.getLogger(__name__)


@dataclass
class RankedAsset:
    """A scored and ranked asset eligible for portfolio inclusion."""
    pair: str
    c1_score: float         # C1 z-score (alpha signal)
    m_t: float              # Diffusion maturity [0, 1]
    c3: float               # Remaining drift capacity: 1 - M_t
    position_score: float   # C1 * exp(-λ_t) * C3


def compute_position_scores(
    c1_scores: Dict[str, float],
    maturity: Dict[str, float],
    lambda_t: float,
) -> Dict[str, float]:
    """
    Compute PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i) for all assets.

    This formula implements the theoretical expected-drift model:
      E[drift] = α × (1 − M_t) × e^(−λ_t × τ)  (with τ=1 simplification)

    The exponential hazard suppresses ALL scores uniformly when market is stressed.
    """
    hazard_multiplier = math.exp(-lambda_t)
    scores: Dict[str, float] = {}

    for pair, c1 in c1_scores.items():
        m_t = maturity.get(pair, 0.5)  # Default to mid-maturity if not available
        c3 = 1.0 - m_t
        score = c1 * hazard_multiplier * c3
        scores[pair] = score

    return scores


def rank_assets(
    c1_scores: Dict[str, float],
    maturity: Dict[str, float],
    lambda_t: float,
    regime: RegimeState,
    downside_vols: Optional[Dict[str, float]] = None,
) -> List[RankedAsset]:
    """
    Apply the full ranking pipeline and return eligible assets sorted by score.

    Filters applied:
      1. C1_z must exceed regime-specific entry threshold
      2. M_t must be below MAX_MATURITY_FOR_ENTRY (reject overextended)
      3. PositionScore must be positive (C1 must be positive for long entries)

    Args:
        c1_scores:     C1 z-scores per pair.
        maturity:      M_t per pair.
        lambda_t:      Current market hazard rate.
        regime:        Current regime state.
        downside_vols: Optional downside vol per pair (for Kelly sizing downstream).

    Returns:
        List of RankedAsset sorted descending by position_score.
    """
    params = config.REGIME_PARAMS[regime.value]
    entry_threshold: float = params["entry_c1_threshold"]
    max_positions: int = params["max_positions"]

    # Compute scores for all eligible pairs
    position_scores = compute_position_scores(c1_scores, maturity, lambda_t)

    ranked: List[RankedAsset] = []
    for pair, score in position_scores.items():
        c1 = c1_scores[pair]
        m_t = maturity.get(pair, 0.5)

        # Filter 1: C1 threshold (regime-dependent stringency)
        if c1 < entry_threshold:
            continue

        # Filter 2: Maturity gate (reject if drift mostly spent)
        if m_t > config.MAX_MATURITY_FOR_ENTRY:
            continue

        # Filter 3: Only long entries (positive score required)
        if score <= 0:
            continue

        ranked.append(RankedAsset(
            pair=pair,
            c1_score=c1,
            m_t=m_t,
            c3=1.0 - m_t,
            position_score=score,
        ))

    # Sort descending by position score
    ranked.sort(key=lambda x: -x.position_score)

    # Limit to max basket size for this regime
    ranked = ranked[:max_positions]

    if ranked:
        logger.info(
            "Ranked basket (%s, λ=%.2f): %s",
            regime.value,
            lambda_t,
            [(r.pair, f"{r.position_score:.3f}") for r in ranked],
        )
    else:
        logger.debug("No eligible assets after ranking filters (regime=%s)", regime.value)

    return ranked


def should_exit(
    pair: str,
    c1_scores: Dict[str, float],
    maturity: Dict[str, float],
) -> tuple[bool, str]:
    """
    Check if an existing position should be exited based on signal decay.

    Exit conditions:
      - C1 z-score fell below EXIT_C1_THRESHOLD (signal has reversed/decayed)
      - M_t rose above MAX_MATURITY_FOR_ENTRY (drift is spent)

    Returns:
        (should_exit, reason_string)
    """
    c1 = c1_scores.get(pair)
    m_t = maturity.get(pair)

    if c1 is not None and c1 < config.EXIT_C1_THRESHOLD:
        return True, f"C1 signal decayed to {c1:.3f} (threshold {config.EXIT_C1_THRESHOLD})"

    if m_t is not None and m_t > config.MAX_MATURITY_FOR_ENTRY:
        return True, f"Maturity M_t={m_t:.3f} exceeds threshold {config.MAX_MATURITY_FOR_ENTRY}"

    return False, ""
