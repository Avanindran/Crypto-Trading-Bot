---
proxy_id: CS_NEG_VOL
family: Alpha_C1
formula: CS_z(−realized_vol_6h)
status: PROMOTED
ic_best: +0.0759 @ 24h (t=+13.26)
---

# CS_NEG_VOL — Mechanism

## Formula

`CS_z(−realized_vol_6h)` — cross-sectional z-score of negative 6h realized volatility

## Economic Rationale

Low-volatility assets within a cross-section tend to exhibit more stable, persistent
price trends than high-volatility assets. This is the H5 stability anomaly: lower realized
vol implies less noise in the price process, which allows the mean-reversion signal to
express itself more cleanly without being overwhelmed by random price variance. The 24h
peak forecast horizon (vs 1h for pure reversal signals) reflects a different mechanism
than H1: this proxy selects stable assets whose slow, low-noise repricing persists over
longer windows. In portfolio context, long low-vol assets after cross-sectional laggard
selection provides a natural risk-reducing tilt while maintaining alpha exposure.

## Signal Family

H5 Vol-Stability — cross-sectional low-volatility stability proxy

## Decision

**Status:** PROMOTED — IC +0.0759 at 24h is the highest raw IC in the universe; t-stat
+13.26 confirms robustness; complements H1 reversal by adding a stability filter on top
of laggard selection.
