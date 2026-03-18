# C2 Modifier Screen — HAZ_CS_DISPERSION

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** Cross-sectional r_1h dispersion (std) < 0.005  
**Gate threshold:** std(r_1h across assets) < 0.005  
**Prior status:** Untested

## Economic Rationale

In normal conditions, assets move heterogeneously — the reversal signal selects genuine laggards. When cross-sectional dispersion collapses (all assets moving together), the market is in a correlated panic or correlated melt-up. In this regime, the CS_z signal loses discriminating power because the spread between leaders and laggards has compressed: every asset is doing roughly the same thing, so selecting laggards does not identify genuine mean-reversion candidates.

## Modifier Screen Results

Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d improvement ≥ 5pp.

| Metric | Bare C1 | + HAZ_CS_DISPERSION gate | Improvement | Bar | Result |
|--------|---------|-----------------|-------------|-----|--------|
| Max Drawdown | -34.09% | -35.13% | -3.06% | ≥ 10% rel | FAIL |
| Worst 30d DD | -19.82% | -19.20% | 0.62% | ≥ 5pp | FAIL |
| Sharpe (ann) | 1.872 | 2.303 | — | — | — |
| Total Return | 59.42% | 77.69% | — | — | — |
| N periods | 732 | 732 | — | — | — |

## Verdict

**REJECTED** — neither MaxDD nor worst-30d gates cleared.
