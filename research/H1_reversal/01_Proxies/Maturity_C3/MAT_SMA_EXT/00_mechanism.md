---
proxy_id: MAT_SMA_EXT
family: Maturity_C3
formula: (price − SMA_12h) / SMA_12h > 0.02 → block entry
status: REJECTED
ic_best: N/A
---

# MAT_SMA_EXT — Mechanism

## Formula

Price extension above its 12-hour simple moving average > 2% → block new entry

```
sma_ext = (price − SMA_12h) / SMA_12h
block_entry if sma_ext > 0.02
```

## Economic Rationale

A price more than 2% above its 12-hour SMA suggests the asset has extended its move
beyond its recent equilibrium level, implying the diffusion event is mature. In the C3
framework, this is a proxy for "drift saturation": the catch-up trade has run, and
entering now risks buying at the top of the move just before mean reversion begins.
Empirically, this criterion produces a mild negative IC uplift, indicating that assets
which are 2% above SMA still tend to continue outperforming slightly over the next
period. The 2% threshold is likely too conservative for the crypto universe where
2% extensions are commonplace even in trending markets.

## Signal Family

C3 Maturity — price-SMA distance (trend extension proxy)

## Decision

**Status:** REJECTED — IC uplift −0.0092; mildest negative among rejected C3 proxies;
the 2% threshold captures normal trending behavior in crypto rather than genuine
overextension; would need recalibration to a much larger threshold to be informative.
