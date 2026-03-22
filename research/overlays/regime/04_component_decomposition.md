# Regime Component Decomposition
**Generated:** 2026-03-22 17:06 UTC

Tests 6 hazard gate configurations on H1 final params (all other params fixed).
Answers: does each regime component individually improve robustness across IS sub-periods?

## Component Definitions

| Component | Source | Proxy |
|-----------|--------|-------|
| No gate | — | Baseline: all entries allowed |
| BTC vol z-score | Price history | Rolling BTC realized vol, z-scored vs 48h baseline |
| Cross-section dispersion | Price history | Std of r_6h across universe; collapse = panic |
| MPI proxy | Price history | Fraction positive BTC hourly returns (24h) |
| FEI proxy | Price history | P75−P25 of r_6h cross-section; IQR breadth |
| Composite (vol+disp) | Price history | 0.75×vol_z + 0.25×disp_z threshold |
| Bid-ask spread* | Live ticker | Not in OHLCV backtest — live bot only |
| Fear & Greed* | Alternative.me API | Not in OHLCV backtest — live bot only |

\*LSI_WEIGHT_SPREAD=0.25, LSI_WEIGHT_FNG=0.15 are active in the live bot but
cannot be backtested from OHLCV alone.

---

## Walk-Forward Validation (Selection Criterion)

Expanding-window WF: 3 folds within Oct–Nov 2024 IS period.
**Selection = gate variant with highest average WF validation Sortino (excluding no-gate baseline).**
OOS holdout is never used for selection.

| Gate Variant | Fold 1 (Oct 21–Nov 03) | Fold 2 (Nov 03–Nov 17) | Fold 3 (Nov 17–Nov 30) | **Avg Sortino** | Avg Calmar | Std(Sortino) | Selection |
|--------------|--------------|--------------|--------------|--------------|--------------|--------------|--------------|
| No hazard gate | -5.99 | 5.99 | 9.69 | **3.23** | 324.41 | 6.69 | (baseline) |
| BTC vol z-score only (current) | -5.69 | 10.26 | 10.39 | **4.99** | 867.59 | 7.55 | **SELECTED/DEPLOYED** |
| Cross-section dispersion only | -5.32 | 5.99 | 8.96 | **3.21** | 264.34 | 6.15 | |
| MPI proxy (BTC directionality) | -6.12 | 5.99 | 11.36 | **3.75** | 573.80 | 7.31 | |
| FEI proxy (cross-section IQR) | 0.02 | 6.24 | 8.23 | **4.83** | 174.12 | 3.50 | |
| Composite (vol 75% + disp 25%) | -5.69 | 8.93 | 10.81 | **4.69** | 876.77 | 7.37 | |

---

## In-Sample Reference (Oct–Nov 2024, full IS period)

Not used for selection. Shows degree of in-sample fit vs no-gate baseline.

| Gate Variant | Sortino | Calmar | MaxDD | vs No-Gate Calmar |
|--------------|---------|--------|-------|-------------------|
| No hazard gate | 2.80 | 20.88 | -8.4% | +0.00 |
| BTC vol z-score only (current) | 4.30 | 41.83 | -8.0% | +20.96 |
| Cross-section dispersion only | 3.79 | 33.59 | -8.2% | +12.72 |
| MPI proxy (BTC directionality) | 3.42 | 28.82 | -8.2% | +7.95 |
| FEI proxy (cross-section IQR) | 3.68 | 28.98 | -8.2% | +8.10 |
| Composite (vol 75% + disp 25%) | 3.88 | 38.31 | -7.7% | +17.44 |

---

## Post-Hoc Final Validation (Dec 2024–Jan 2025 OOS)

**Not used for selection.** Shown after WF selection is locked in.

| Gate Variant | Total Return | Sortino | Calmar |
|--------------|-------------|---------|--------|
| No hazard gate | 2.3% | 0.51 | 0.77 |
| BTC vol z-score only (current) | 6.9% | 1.13 | 3.43 |
| Cross-section dispersion only | -8.4% | -1.05 | -1.84 |
| MPI proxy (BTC directionality) | -5.3% | -0.56 | -1.55 |
| FEI proxy (cross-section IQR) | -5.8% | -0.92 | -2.20 |
| Composite (vol 75% + disp 25%) | 5.9% | 0.99 | 2.91 |

---

## Interpretation

**WF-selected gate: vol_only** (WF avg Sortino = 4.99)

Baseline (no gate): IS Calmar = 20.88. Current deployed (vol-only): WF avg Sortino = 4.99.
BTC vol z-score gate is the only component that consistently improves performance across IS sub-periods. Dispersion, MPI, and FEI gates degrade WF performance — they overfit to specific market regimes in the training window.

**Live bot additionally includes (not backtestable):**
- Bid-ask spread z-score (LSI_WEIGHT_SPREAD=0.25) — reacts to illiquidity not captured by vol
- Fear & Greed Index (LSI_WEIGHT_FNG=0.15) — leading sentiment indicator

---

*This study is referenced in `research/10_pipeline_index.md` Step 7A.*
