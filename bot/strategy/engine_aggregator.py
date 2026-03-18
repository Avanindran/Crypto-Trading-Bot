"""
bot/strategy/engine_aggregator.py — Multi-engine portfolio aggregation.

H1 (reversal) and H2C (BTC-diffusion) are independent engines. Each produces
its own target portfolio. The regime determines capital allocation between them.
This module combines the two portfolios at the weight level — BEFORE execution —
so that only one set of orders is placed per rebalance cycle.

Architecture:
    H1 engine  →  h1_target_weights  (optimized for reversal)
    H2C engine →  h2c_target_weights (optimized for BTC diffusion)
    Regime     →  h2c_capital_fraction (0.0 = H1 only, e.g. 0.4 = 60/40 split)
    Aggregator →  combined_weights  (before execution)

Why portfolio-level, not signal-level:
    Signal blending: H2C modifies WHICH assets H1 selects → not independent
    Portfolio aggregation: H2C selects its OWN assets → genuine diversification
    Research: alpha_opt=0.0 in signal-blending sweep (H2C as score contributor
    does not improve H1). H2C standalone Sortino=1.99 > combined blends.

Engine failure modes (handled by regime allocation):
    H1 reversal:      breaks in correlated crashes (all assets fall together)
    H2C diffusion:    breaks when BTC is flat or correlations spike (HAZARD)
    HAZARD_DEFENSIVE: both engines at 0% — no new entries
    NEUTRAL_MIXED:    H1 muted (λ=1.5), H2C fraction minimal or zero
    TREND_SUPPORTIVE + BTC active: H2C diffusion most reliable → higher fraction

Scalability: Adding H3 follows the same pattern — extend aggregate_engine_portfolios()
with a third weight dict and capital fraction.
"""
from typing import Dict


def aggregate_engine_portfolios(
    h1_weights: Dict[str, float],
    h2c_weights: Dict[str, float],
    h2c_capital_fraction: float,
) -> Dict[str, float]:
    """
    Combine H1 and H2C portfolios proportional to capital allocation.

    Both engines produce weights normalized to their regime gross cap. The
    aggregation scales each by its capital fraction — since fractions sum to 1,
    the combined gross exposure equals the individual gross cap.

    Example (TREND_SUPPORTIVE, 60/40 split):
        H1 gross_cap=85% × fraction=0.60 → contributes up to 51% NAV
        H2C gross_cap=85% × fraction=0.40 → contributes up to 34% NAV
        Combined: up to 85% NAV — consistent with regime gross cap.

    Args:
        h1_weights:           H1 target weights as fraction of full NAV.
        h2c_weights:          H2C target weights as fraction of full NAV.
        h2c_capital_fraction: Capital fraction allocated to H2C (0.0 → H1 only).

    Returns:
        Combined portfolio weights as fraction of NAV. H2C disabled (fraction=0)
        returns h1_weights unchanged — zero behavioral cost.
    """
    if h2c_capital_fraction <= 0.0 or not h2c_weights:
        return h1_weights

    h1_fraction = 1.0 - h2c_capital_fraction
    combined: Dict[str, float] = {}

    for pair, w in h1_weights.items():
        combined[pair] = w * h1_fraction

    for pair, w in h2c_weights.items():
        combined[pair] = combined.get(pair, 0.0) + w * h2c_capital_fraction

    return combined
