# C2 Modifier Screen — HAZ_BTC_VOL_Z

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** BTC 6h realized-vol z-score (48h window) > 1.50  
**Gate threshold:** BTC vol z-score > 1.50  
**Prior status:** APPROVED (from vector_tests.py Part B)

## Economic Rationale

Elevated BTC realized volatility indicates a stressed market regime where reversal timing uncertainty is high. When BTC vol z-score exceeds 1.50σ, the risk-adjusted value of entering new long reversal positions drops sharply: the IC relationship holds on average but drawdown risk dominates over the 4h holding window.

## Modifier Screen Results

Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d improvement ≥ 5pp.

| Metric | Bare C1 | + HAZ_BTC_VOL_Z gate | Improvement | Bar | Result |
|--------|---------|-----------------|-------------|-----|--------|
| Max Drawdown | -34.09% | -28.00% | 17.84% | ≥ 10% rel | PASS |
| Worst 30d DD | -19.82% | -10.69% | 9.13% | ≥ 5pp | PASS |
| Sharpe (ann) | 1.872 | 3.015 | — | — | — |
| Total Return | 59.42% | 119.05% | — | — | — |
| N periods | 732 | 732 | — | — | — |

## Verdict

**APPROVED** — both MaxDD and worst-30d gates cleared.
