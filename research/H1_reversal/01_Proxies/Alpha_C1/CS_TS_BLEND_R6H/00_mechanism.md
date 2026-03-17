---
proxy_id: CS_TS_BLEND_R6H
family: Alpha_C1
formula: 0.5 × CS_z(−r_6h) + 0.5 × CS_z(−TS_z(r_6h))
status: PROMOTED
ic_best: +0.0347 @ 1h (t=+8.37)
---

# CS_TS_BLEND_R6H — Mechanism

## Formula

`0.5 × CS_z(−r_6h) + 0.5 × CS_z(−TS_z(r_6h))`

An equal-weight blend of the cross-sectional laggard (CS_NEG_R6H) and the
time-series self-comparison laggard (TS_ZSCORE_NEG_R6H) at the 6h horizon.

## Economic Rationale

Cross-sectional and time-series reversal signals capture orthogonal dimensions of
laggard behavior. CS_z(−r_6h) identifies assets that are weak relative to their
peers — relevant when the market is repricing a broad set of assets and some lag.
TS_z(−r_6h) identifies assets that are weak relative to their own recent history —
relevant when an individual asset has had an unusual downside episode regardless of
peer behavior. By blending both in equal proportions, the composite is activated when
an asset is simultaneously a cross-sectional and time-series laggard: the strongest
possible signal for expectation-diffusion lag. The blend trades a small IC reduction
(vs the pure CS signal) for improved signal stability and robustness to regime changes
where one dimension may dominate the other.

## Signal Family

H1 Reversal / H1 TS — blended cross-sectional and time-series laggard at 6h horizon

## Decision

**Status:** PROMOTED — IC +0.0347, t-stat +8.37; IC slightly below pure CS but blend
provides ensemble diversification; deployed as a component in the GP combination to
capture the joint CS+TS laggard condition.
