---
proxy_id: CS_NEG_R1H
family: Alpha_C1
formula: CS_z(−r_1h)
status: PROMOTED
ic_best: +0.0492 @ 1h (t=+10.75)
---

# CS_NEG_R1H — Mechanism

## Formula

`CS_z(−r_1h)` — cross-sectional z-score of negative 1-hour return

## Economic Rationale

Recent short-term losers tend to mean-revert faster than longer-horizon laggards because the
1-hour return captures noise-driven overshoots and micro-liquidity gaps. When an asset
underperforms the cross-section over the past hour, a fraction of that gap reflects
transient selling pressure rather than fundamental repricing. The cross-sectional
normalization isolates relative weakness, removing the common-market component and
focusing on idiosyncratic underperformance. The sign inversion converts laggard rank
into a forward-return predictor.

## Signal Family

H1 Reversal — short-horizon cross-sectional mean reversion

## Decision

**Status:** PROMOTED — IC +0.0492, t-stat +10.75 well above the |t|>5 threshold; cleanest
single-horizon reversal signal in the universe; deployed in C1 composite as primary 1h input.
