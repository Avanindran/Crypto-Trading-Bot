# C3 Modifier Screen — MAT_FUNDING_RATE

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** Price z-score vs 48h baseline > 1.0σ (funding rate proxy)  
**Thresholds:** (price - mean_price_48h) / std_price_48h > 1.0 (stale) | ≤ 0 (fresh)  
**Prior status:** Not individually screened (in composite, weight 0.20). Live proxy used.

## Economic Rationale

Positive perpetual funding rates indicate long-biased positioning, which signals overextension. Direct funding rate data requires live Binance fapi access; for backtesting, price z-score vs 48h rolling mean is used as a proxy: persistently elevated price levels correlate with positive funding rates in crypto perpetuals.

## IC Screen Results

Gate criterion: IC(fresh) > IC(unconditional) at 4h horizon.

| Bucket | Mean IC | t-stat | N |
|--------|---------|--------|---|
| Fresh (below threshold) | 0.0578 | 4.45 | 590 |
| Stale (above threshold) | 0.0627 | 3.50 | 435 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh − unconditional): +0.0101

## Verdict

**APPROVED** — fresh IC exceeds unconditional IC — gate has predictive utility.
