---
proxy_id: MAT_RSI_PROXY
family: Maturity_C3
formula: fraction of up-bars in last 14h > 0.70 → block entry
status: REJECTED
ic_best: N/A
---

# MAT_RSI_PROXY — Mechanism

## Formula

Fraction of 1h bars with positive returns in the last 14 hours > 0.70 → block new entry

```
rsi_proxy = mean(r_1h[-14:] > 0)   # fraction of up-bars in last 14h
block_entry if rsi_proxy > 0.70
```

## Economic Rationale

This proxy approximates the Wilder RSI using bar counts rather than magnitude: when more
than 70% of the last 14 bars are positive, the asset is in overbought territory by the
traditional RSI interpretation (equivalent to RSI > 70). In the C3 maturity context,
sustained upward momentum indicates the diffusion move is well advanced and entering now
risks being the last buyer before reversal. The bar-count formulation is more robust to
outlier bars than magnitude-based RSI. Despite the theoretical appeal, the empirical
result shows negative IC uplift: the ">70% up bars" condition appears to select assets
in momentum phases rather than genuinely overextended ones.

## Signal Family

C3 Maturity — RSI-analogue overbought gate

## Decision

**Status:** REJECTED — IC uplift −0.0249; the bar-count RSI proxy blocks entries during
sustained momentum phases that continue to generate positive returns; threshold of 0.70
is too low and captures normal trending behavior.
