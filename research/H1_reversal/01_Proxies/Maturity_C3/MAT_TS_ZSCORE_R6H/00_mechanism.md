---
proxy_id: MAT_TS_ZSCORE_R6H
family: Maturity_C3
formula: TS z-score of r_6h vs 48h history > 1.50 → block entry
status: REJECTED
ic_best: N/A
---

# MAT_TS_ZSCORE_R6H — Mechanism

## Formula

Time-series z-score of r_6h return vs 48h rolling history > 1.50 → block new entry

```
ts_z = (r_6h − mean_r6h_48h) / std_r6h_48h
block_entry if ts_z > 1.50
```

## Economic Rationale

A 6h return that is more than 1.5 standard deviations above its own recent history
suggests the asset has made an unusually large move by its own standards. This should
indicate late-stage diffusion: the big move has already happened, and entering now risks
buying at the peak. However, in a reversal strategy context, the TS z-score > 1.50 signal
creates a fundamental conflict: the C1 alpha signal targets laggards (negative TS z-scores),
not leaders. An asset with TS z-score > 1.50 on r_6h would already be screened out by C1
as too strong to be a laggard. The C3 filter therefore adds no incremental screening value
for the assets that actually pass C1 selection, resulting in negative IC uplift.

## Signal Family

C3 Maturity — time-series return z-score (self-comparison extension gate)

## Decision

**Status:** REJECTED — IC uplift −0.0362; the worst-performing C3 proxy; creates
conceptual conflict with the C1 laggard selection — assets that pass C1 filtering
essentially never have high r_6h TS z-scores, making this a redundant and
counterproductive filter.
