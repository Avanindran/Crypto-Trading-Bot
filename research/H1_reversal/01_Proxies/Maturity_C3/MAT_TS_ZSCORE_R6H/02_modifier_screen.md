# C3 Modifier Screen — MAT_TS_ZSCORE_R6H

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** TS z-score of r_6h vs own 48h history > 1.5σ  
**Thresholds:** TS z-score > 1.5 (stale) | < -0.5 (fresh)  
**Prior status:** Untested

## Economic Rationale

Parametric alternative to pct_rank. Computes how many standard deviations the current 6h return is above the asset's own 48h rolling mean return. Above +1.5σ means the current return is unusually strong vs the asset's own historical baseline — unlikely to be a laggard in the CS sense. More sensitive than pct_rank to the magnitude of the deviation.

## IC Screen Results

Gate criterion: IC(fresh) > IC(unconditional) at 4h horizon.

| Bucket | Mean IC | t-stat | N |
|--------|---------|--------|---|
| Fresh (below threshold) | 0.0115 | 0.66 | 406 |
| Stale (above threshold) | 0.1326 | 4.08 | 146 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh − unconditional): -0.0362

## Verdict

**REJECTED** — fresh IC does not exceed unconditional IC — gate does not add value.
