# C2 Modifier Screen — HAZ_BTC_DRAWDOWN

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** BTC drawdown from 24h rolling high > 2%  
**Gate threshold:** (BTC_price - BTC_24h_high) / BTC_24h_high < -2%  
**Prior status:** Untested

## Economic Rationale

An active BTC sell-off (measured as DD from 24h rolling high) signals that risk-off is in progress. Altcoins typically lag BTC moves by 1-6h, meaning entering longs on 'laggard' assets during a BTC sell-off is selecting into the path of incoming losses rather than genuine recovery candidates. The 2% threshold captures material drawdowns while ignoring normal intraday oscillations.

## Modifier Screen Results

Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d improvement ≥ 5pp.

| Metric | Bare C1 | + HAZ_BTC_DRAWDOWN gate | Improvement | Bar | Result |
|--------|---------|-----------------|-------------|-----|--------|
| Max Drawdown | -34.09% | -36.27% | -6.41% | ≥ 10% rel | FAIL |
| Worst 30d DD | -19.82% | -20.60% | -0.78% | ≥ 5pp | FAIL |
| Sharpe (ann) | 1.872 | 1.230 | — | — | — |
| Total Return | 59.42% | 24.56% | — | — | — |
| N periods | 732 | 732 | — | — | — |

## Verdict

**REJECTED** — neither MaxDD nor worst-30d gates cleared.
