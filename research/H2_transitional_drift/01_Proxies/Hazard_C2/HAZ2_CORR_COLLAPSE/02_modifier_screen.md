# HAZ2_CORR_COLLAPSE — C2 Modifier Screen

**Mechanism:** H2C BTC-Diffusion  
**Training period:** Oct 2024–Jan 2025  
**Approval criterion:** MaxDD relative improvement ≥ 10% AND worst 30d DD improvement ≥ 5pp  

## Summary

| Metric | Bare H2C | HAZ2_CORR_COLLAPSE gated | Change |
|--------|----------|-----------------|--------|
| Total Return | 62.0% | 5.3% | -56.7pp |
| MaxDD | -66.2% | -69.7% | -5.3% relative |
| Worst 30d DD | -48.7% | -48.7% | -0.0pp |
| Sharpe (ann) | 1.80 | 0.71 | — |
| % periods blocked | — | 4.9% | — |
| N rebalances | 738 | 738 | — |

## Decision

**MaxDD relative improvement:** -5.3% < 10% (criterion: ≥ 10%)  
**Worst 30d DD improvement:** -0.0pp < 5pp (criterion: ≥ 5pp)  

**Status: REJECTED**

## Threshold Sweep

| Threshold | MaxDD (bare) | MaxDD (gated) | Rel improvement | Worst 30d (gated) | % blocked |
|-----------|-------------|---------------|----------------|-------------------|-----------|
| 0.3 | -66.2% | -69.7% | -5.3% | -48.7% | 4.9% |
| 0.4 | -66.2% | -69.7% | -5.3% | -48.7% | 4.9% |
| 0.5 | -66.2% | -69.7% | -5.3% | -48.7% | 4.9% |
