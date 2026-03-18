# C3 Modifier Screen — MAT_SMA_EXT

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** (price − SMA_12h) / SMA_12h > 2% (extended above moving average)  
**Thresholds:** (price - SMA_12h) / SMA_12h > 0.02 (stale) | ≤ 0 (fresh)  
**Prior status:** Not individually screened (in composite, weight 0.40)

## Economic Rationale

When price is more than 2% above its 12h simple moving average, it has already moved significantly relative to its recent trend. The reversal signal requires an asset to be a laggard — but if it is already extended above its own trend, it is no longer a laggard. This proxy blocks momentum continuation trades that have outrun their fair value.

## IC Screen Results

Gate criterion: IC(fresh) > IC(unconditional) at 4h horizon.

| Bucket | Mean IC | t-stat | N |
|--------|---------|--------|---|
| Fresh (below threshold) | 0.0385 | 2.98 | 587 |
| Stale (above threshold) | 0.0593 | 3.45 | 453 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh − unconditional): -0.0092

## Verdict

**REJECTED** — fresh IC does not exceed unconditional IC — gate does not add value.
