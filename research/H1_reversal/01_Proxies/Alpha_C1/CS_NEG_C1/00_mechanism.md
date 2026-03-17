---
proxy_id: CS_NEG_C1
family: Alpha_C1
formula: CS_z(−C1_raw) where C1_raw = 0.10×r_1h + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r_2h)
status: PROMOTED
ic_best: +0.0431 @ 1h (t=+9.36)
---

# CS_NEG_C1 — Mechanism

## Formula

`CS_z(−C1_raw)` where:

```
C1_raw = 0.10×r_1h + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r_2h)
```

## Economic Rationale

The composite C1 score aggregates momentum across multiple horizons, creating a
multi-scale view of recent price performance. By negating C1_raw and re-normalizing
cross-sectionally, CS_NEG_C1 identifies assets that are laggards across all time scales
simultaneously — a multi-horizon underperformer. Such assets are prime candidates for
expectation-diffusion catches: they have missed the move at every scale, suggesting
systematic repricing lag rather than a single noise spike. The cross-sectional relative
strength term (r_2h minus median) further weights assets that are falling behind their
peers specifically in the mid-term.

## Signal Family

H1 Reversal — composite multi-horizon cross-sectional laggard

## Decision

**Status:** PROMOTED — IC +0.0431, t-stat +9.36; used in final GP combination as the
holistic laggard identifier; captures co-movement of underperformance across all horizons.
