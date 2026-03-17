# C2 Modifier Screen — HAZ_SPREAD_Z

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** OHLC intrabar range z-score (48h) > 1.50 (bid-ask spread proxy)  
**Gate threshold:** (high - low) / close z-score (48h) > 1.50  
**Prior status:** Untested

## Economic Rationale

Elevated intrabar high-low range signals liquidity stress. When spreads are wide, limit orders face adverse selection: the price moves against the new entry before the reversal has time to materialize. Wide range is used as a proxy for elevated bid-ask spread (not directly observable in Binance Vision 1h klines).

## Modifier Screen Results

Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d improvement ≥ 5pp.

| Metric | Bare C1 | + HAZ_SPREAD_Z gate | Improvement | Bar | Result |
|--------|---------|-----------------|-------------|-----|--------|
| Max Drawdown | -34.09% | -39.57% | -16.10% | ≥ 10% rel | FAIL |
| Worst 30d DD | -19.82% | -27.25% | -7.43% | ≥ 5pp | FAIL |
| Sharpe (ann) | 1.872 | 1.383 | — | — | — |
| Total Return | 59.42% | 34.42% | — | — | — |
| N periods | 732 | 732 | — | — | — |

## Verdict

**REJECTED** — neither MaxDD nor worst-30d gates cleared.
