---
proxy_id: CS_NEG_R6H
family: Alpha_C1
formula: CS_z(−r_6h)
status: PROMOTED
ic_best: +0.0398 @ 2h (t=+8.73)
---

# CS_NEG_R6H — Mechanism

## Formula

`CS_z(−r_6h)` — cross-sectional z-score of negative 6-hour return

## Economic Rationale

The 6-hour horizon is the primary diffusion window in crypto: it spans 1–2 news cycles,
covers Asian-to-European session handoffs, and is long enough for institutional re-pricing
to propagate but short enough that mean reversion has not fully completed. Assets that
are cross-sectional laggards over 6 hours represent the population most likely to catch
up in the next 2–6 hours as the information diffuses to slower-moving participants.
The IC peaks at the 2h forward horizon (not 1h), consistent with the expectation-diffusion
interpretation: the signal is capturing a delayed repricing rather than a microstructure
bounce.

## Signal Family

H1 Reversal — medium-horizon cross-sectional mean reversion (primary horizon)

## Decision

**Status:** PROMOTED — IC +0.0398, t-stat +8.73; strongest mid-horizon predictor and the
primary C1 signal weight (0.35); IC peak at 2h forward confirms diffusion-lag mechanism.
