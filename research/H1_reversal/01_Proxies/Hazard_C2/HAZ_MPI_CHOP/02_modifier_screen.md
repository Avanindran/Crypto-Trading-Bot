# C2 Modifier Screen — HAZ_MPI_CHOP

**Run:** 2026-03-17 10:42 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Proxy Definition

**Formula:** Market Participation Index < 0.30 (fraction positive 1h returns)  
**Gate threshold:** fraction(r_1h > 0) < 0.30 across universe  
**Prior status:** Untested

## Economic Rationale

MPI measures how many assets are participating in the market direction. When fewer than 30% of assets have positive 1h returns, the market is in a chop or broad sell-off regime. In this state, the reversal thesis weakens: there is no identifiable leader group, making the diffusion lag mechanism unreliable. Low MPI also indicates mean-reversion candidates may continue falling rather than recovering.

## Modifier Screen Results

Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d improvement ≥ 5pp.

| Metric | Bare C1 | + HAZ_MPI_CHOP gate | Improvement | Bar | Result |
|--------|---------|-----------------|-------------|-----|--------|
| Max Drawdown | -34.09% | -38.96% | -14.30% | ≥ 10% rel | FAIL |
| Worst 30d DD | -19.82% | -33.51% | -13.69% | ≥ 5pp | FAIL |
| Sharpe (ann) | 1.872 | 0.665 | — | — | — |
| Total Return | 59.42% | 7.68% | — | — | — |
| N periods | 732 | 732 | — | — | — |

## Verdict

**REJECTED** — neither MaxDD nor worst-30d gates cleared.
