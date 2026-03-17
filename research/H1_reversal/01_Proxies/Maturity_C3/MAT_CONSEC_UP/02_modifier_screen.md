# C3 Modifier Screen — MAT_CONSEC_UP

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** Fraction of last 6 bars with positive 1h return > 75%  
**Thresholds:** frac(up) in last 6 bars > 0.75 (stale) | < 0.33 (fresh)  
**Prior status:** Untested

## Economic Rationale

Five or more consecutive up-bars (5/6) indicates persistent positive momentum. This is orthogonal to the RSI proxy (which looks at 14 bars): MAT_CONSEC_UP captures very recent streak persistence over a 6h window, specifically relevant for the 4h holding horizon of the strategy. A laggard on a recent 6-bar streak is no longer a laggard.

## IC Screen Results

Gate criterion: IC(fresh) > IC(unconditional) at 4h horizon.

| Bucket | Mean IC | t-stat | N |
|--------|---------|--------|---|
| Fresh (below threshold) | 0.0280 | 1.23 | 267 |
| Stale (above threshold) | -0.0074 | -0.21 | 169 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh − unconditional): -0.0197

## Verdict

**REJECTED** — fresh IC does not exceed unconditional IC — gate does not add value.
