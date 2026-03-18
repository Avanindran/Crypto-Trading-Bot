---
proxy_id: CS_NEG_R2H
family: Alpha_C1
formula: CS_z(−r_2h)
status: PROMOTED
ic_best: +0.0472 @ 1h (t=+10.33)
---

# CS_NEG_R2H — Mechanism

## Formula

`CS_z(−r_2h)` — cross-sectional z-score of negative 2-hour return

## Economic Rationale

The 2-hour return window straddles the boundary between noise-driven microstructure effects
(captured by r_1h) and the expectation-diffusion lag that is the core H1 thesis. Assets
that have underperformed the cross-section over 2 hours are in the early phase of a
correction cycle: too recent to be fully repriced, but persistent enough to confirm
that selling pressure is not purely random. Cross-sectional z-scoring strips the
market beta component so the signal reflects idiosyncratic lag rather than broad
market direction.

## Signal Family

H1 Reversal — medium-short-horizon cross-sectional mean reversion

## Decision

**Status:** PROMOTED — IC +0.0472, t-stat +10.33; marginally weaker than r_1h but with
better persistence across forecast horizons; included in C1 composite with 0.20 weight.
