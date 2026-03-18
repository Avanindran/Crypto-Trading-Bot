# C3 Modifier Screen — MAT_PCT_RANK

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** pct_rank(r_6h, 48h rolling history) > 0.72  
**Thresholds:** pct_rank > 0.72 (stale) | < 0.30 (fresh)  
**Prior status:** REJECTED standalone (IC gate fail in vector_tests.py Part C)

## Economic Rationale

If the current 6h return is already in the top 72nd percentile of its own recent history, the laggard has already recovered most of its expected reversion. Remaining upside is limited. Non-parametric percentile rank captures the ordinal position without assuming a return distribution.

## IC Screen Results

Gate criterion: IC(fresh) > IC(unconditional) at 4h horizon.

| Bucket | Mean IC | t-stat | N |
|--------|---------|--------|---|
| Fresh (below threshold) | 0.0190 | 1.12 | 432 |
| Stale (above threshold) | 0.0544 | 3.08 | 440 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh − unconditional): -0.0287

## Verdict

**REJECTED** — fresh IC does not exceed unconditional IC — gate does not add value.
