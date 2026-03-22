# Regime Component Decomposition
**Generated:** 2026-03-22 16:41 UTC

Tests 6 hazard gate configurations on H1 final params (all other params fixed).
Answers: does each regime component individually improve Calmar/Sortino? Does the
composite beat individual components?

## Component Definitions

| Component | Source | Proxy |
|-----------|--------|-------|
| BTC vol z-score | Price history | Rolling BTC realized vol, z-scored vs 48h baseline |
| Cross-section dispersion | Price history | Std of r_6h across universe; collapse = panic |
| MPI proxy | Price history | Fraction positive BTC hourly returns (24h) |
| FEI proxy | Price history | P75−P25 of r_6h cross-section; IQR breadth |
| Bid-ask spread* | Live ticker | Not in OHLCV backtest — live bot only |
| Fear & Greed* | Alternative.me API | Not in OHLCV backtest — live bot only |

\*These two components (LSI_WEIGHT_SPREAD=0.25, LSI_WEIGHT_FNG=0.15) are active in the
live bot but cannot be backtested from OHLCV alone.

## In-Sample Results (Oct–Nov 2024)

| Gate Variant | Sortino | Calmar | MaxDD | vs No-Gate Calmar |
|--------------|---------|--------|-------|-------------------|
| No hazard gate | 2.80 | 20.88 | -8.4% | +0.00 |
| BTC vol z-score only (current) | 4.30 | 41.83 | -8.0% | +20.96 |
| Cross-section dispersion only | 3.79 | 33.59 | -8.2% | +12.72 |
| MPI proxy (BTC directionality) | 3.42 | 28.82 | -8.2% | +7.95 |
| FEI proxy (cross-section IQR) | 3.68 | 28.98 | -8.2% | +8.10 |
| Composite (vol 75% + disp 25%) | 3.88 | 38.31 | -7.7% | +17.44 |

## Out-of-Sample Results (Dec 2024–Jan 2025)

| Gate Variant | Total Return | Sortino | Calmar |
|--------------|-------------|---------|--------|
| No hazard gate | 2.3% | 0.51 | 0.77 |
| BTC vol z-score only (current) | 6.9% | 1.13 | 3.43 |
| Cross-section dispersion only | -8.4% | -1.05 | -1.84 |
| MPI proxy (BTC directionality) | -5.3% | -0.56 | -1.55 |
| FEI proxy (cross-section IQR) | -5.8% | -0.92 | -2.20 |
| Composite (vol 75% + disp 25%) | 5.9% | 0.99 | 2.91 |

## Interpretation

**Baseline (no gate):** Calmar = 20.88, MaxDD = -8.4%
**Current deployed (vol-only):** Calmar = 41.83 (+20.96 vs baseline)
**Composite (vol+disp):** Calmar = 38.31 (+17.44 vs baseline)

**Live bot additionally includes:**
- Bid-ask spread z-score (LSI_WEIGHT_SPREAD=0.25) — reacts to market illiquidity not captured by vol alone
- Fear & Greed Index (LSI_WEIGHT_FNG=0.15) — leading sentiment indicator; extreme greed precedes corrections

These components are validated against live performance, not in this OHLCV backtest.

---

*This study is referenced in `research/10_pipeline_index.md` Step 7A.*
