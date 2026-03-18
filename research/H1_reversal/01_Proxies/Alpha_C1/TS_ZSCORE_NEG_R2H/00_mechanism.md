---
proxy_id: TS_ZSCORE_NEG_R2H
family: Alpha_C1
formula: CS_z(−TS_z(r_2h)) where TS_z(r_2h) = (r_2h − mean_r2h_48h) / std_r2h_48h
status: PROMOTED
ic_best: +0.0358 @ 1h (t=+9.46)
---

# TS_ZSCORE_NEG_R2H — Mechanism

## Formula

`CS_z(−TS_z(r_2h))` where:

```
TS_z(r_2h) = (r_2h − mean_r2h_48h) / std_r2h_48h
```

## Economic Rationale

The 2-hour time-series z-score captures whether an asset's current 2h return is
anomalously low relative to its own recent behavior over the past 48 hours. Unlike the
cross-sectional 2h signal (CS_NEG_R2H), which measures relative weakness vs peers, this
proxy measures absolute weakness relative to the asset's own regime. Assets with an
unusually weak 2h return vs their own history are likely experiencing temporary
selling pressure disconnected from any fundamental change — exactly the profile for
short-term reversal. The IC at 2h horizon is notably stronger for TS vs CS at the 2h
input, suggesting complementary information.

## Signal Family

H1 TS — time-series self-comparison reversal at 2h horizon

## Decision

**Status:** PROMOTED — IC +0.0358, t-stat +9.46; significantly stronger than the 6h TS
counterpart; provides genuine additive information to CS proxies and is included in the
blended signal CS_TS_BLEND_R6H.
