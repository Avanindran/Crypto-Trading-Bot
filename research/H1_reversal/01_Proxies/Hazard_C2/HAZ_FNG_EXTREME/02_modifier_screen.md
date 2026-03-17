# C2 Modifier Screen — HAZ_FNG_EXTREME

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** Crypto Fear & Greed Index > 75 (extreme greed)  
**Gate threshold:** F&G > 75 (source: Alternative.me)  
**Prior status:** Untested

## Economic Rationale

The Fear & Greed index aggregates sentiment from price momentum, social media, surveys, dominance, and volatility. 'Extreme Greed' (>75) historically precedes corrections as over-optimism creates fragile conditions. Unlike price-based hazard signals, F&G is a leading indicator that reflects positioning before it shows in realized volatility — it can identify elevated hazard before BTC vol reacts.

## Modifier Screen Results

Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d improvement ≥ 5pp.

| Metric | Bare C1 | + HAZ_FNG_EXTREME gate | Improvement | Bar | Result |
|--------|---------|-----------------|-------------|-----|--------|
| Max Drawdown | -34.09% | -28.09% | 17.58% | ≥ 10% rel | PASS |
| Worst 30d DD | -19.82% | -14.48% | 5.34% | ≥ 5pp | PASS |
| Sharpe (ann) | 1.872 | 1.757 | — | — | — |
| Total Return | 59.42% | 39.91% | — | — | — |
| N periods | 732 | 732 | — | — | — |

## Verdict

**APPROVED** — both MaxDD and worst-30d gates cleared.
