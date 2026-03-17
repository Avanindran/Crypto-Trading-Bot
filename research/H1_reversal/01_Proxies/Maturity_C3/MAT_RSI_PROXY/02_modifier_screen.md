# C3 Modifier Screen — MAT_RSI_PROXY

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** Fraction of up bars in last 14h > 70% (RSI-like overbought)  
**Thresholds:** frac(r_1h > 0) in last 14h > 0.70 (stale) | < 0.30 (fresh)  
**Prior status:** Not individually screened (in composite, weight 0.15)

## Economic Rationale

Classic RSI overbought signal adapted for hourly klines. When more than 70% of the last 14 bars have been up-bars, the asset is in a persistent uptrend and unlikely to revert further. The RSI proxy uses the fraction of positive-return bars rather than the traditional formula, which requires price history not always available in kline data.

## IC Screen Results

Gate criterion: IC(fresh) > IC(unconditional) at 4h horizon.

| Bucket | Mean IC | t-stat | N |
|--------|---------|--------|---|
| Fresh (below threshold) | 0.0228 | 0.98 | 245 |
| Stale (above threshold) | 0.0145 | 0.42 | 137 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh − unconditional): -0.0249

## Verdict

**REJECTED** — fresh IC does not exceed unconditional IC — gate does not add value.
