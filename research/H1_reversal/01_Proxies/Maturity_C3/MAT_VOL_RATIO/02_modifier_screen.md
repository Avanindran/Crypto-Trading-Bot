# C3 Modifier Screen — MAT_VOL_RATIO

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** Recent 6h volume vs 48h median volume > 2.0× (climax volume)  
**Thresholds:** mean(vol_6h) / median(vol_48h) > 2.0 (stale) | < 0.5 (fresh)  
**Prior status:** Untested

## Economic Rationale

High volume relative to recent norms signals potential exhaustion or climax: the move has attracted broad participation, suggesting the impulsive phase is ending. High volume on a recovery already in progress means the easy recovery money has been made. Classic technical analysis exhaustion signal adapted for the diffusion lag mechanism.

## IC Screen Results

Gate criterion: IC(fresh) > IC(unconditional) at 4h horizon.

| Bucket | Mean IC | t-stat | N |
|--------|---------|--------|---|
| Fresh (below threshold) | 0.1117 | 2.12 | 75 |
| Stale (above threshold) | 0.0363 | 1.46 | 236 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh − unconditional): +0.0640

## Verdict

**APPROVED** — fresh IC exceeds unconditional IC — gate has predictive utility.
