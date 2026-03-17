---
proxy_id: TS_BB_DIST
family: Alpha_C1
formula: CS_z((SMA_6h − price) / (2 × std_price_24h))
status: PROMOTED
ic_best: +0.0363 @ 1h (t=+9.44)
---

# TS_BB_DIST — Mechanism

## Formula

`CS_z((SMA_6h − price) / (2 × std_price_24h))` — negative Bollinger band distance

Note: `SMA_6h − price` (not price − SMA) gives a positive value when price is below
the moving average, i.e. when the asset is in the "lower band" region.

## Economic Rationale

Bollinger band distance is a classic mean-reversion indicator: when price is far below
its own rolling average (relative to its volatility), the asset is statistically
extended to the downside and likely to revert. The normalization by `2 × std_price_24h`
gives the distance in units of standard deviations, directly comparable to a z-score.
A high positive value means price is more than one standard deviation below SMA —
the definition of a lower-band touch. The 24h std window provides enough history to
estimate band width robustly. Cross-sectional normalization of this distance creates
a signal that ranks assets by how extreme their own-trend extension is, filtering out
assets that are merely weak in absolute terms.

## Signal Family

H1 TS — time-series Bollinger-band mean reversion

## Decision

**Status:** PROMOTED — IC +0.0363, t-stat +9.44; nearly identical IC to TS_ZSCORE_NEG_R2H
with a slightly different construction; captures lower-band extension rather than
z-score underperformance, providing mild diversification in the signal ensemble.
