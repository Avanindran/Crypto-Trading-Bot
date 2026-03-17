# Dual-Engine Regime-Conditional Allocation
**Generated:** 2026-03-17 14:49 UTC

## Architecture

| Regime State | Condition | Allocation |
|-------------|-----------|-----------|
| TREND_ACTIVE | |r_BTC,2h| ≥ 0.5% | α×H2C + (1−α)×H1 (α=0.00) |
| TREND_FLAT | |r_BTC,2h| < 0.5% | H1 only (α=0) |
| HAZARD | BTC vol z > 0.75 | No new entries |

---

## alpha_TREND Sweep (H2 weight in TREND_ACTIVE periods)

| α | Total Return | Sortino | Calmar | MaxDD |
|---|-------------|---------|--------|-------|
| 0.00 | 35.6% | 2.51 | 9.68 | -15.1% |
| 0.10 | 26.2% | 1.91 | 6.31 | -15.8% |
| 0.20 | 26.5% | 1.93 | 6.47 | -15.6% |
| 0.35 | 19.6% | 1.45 | 3.16 | -22.1% |
| 0.50 | 8.2% | 0.75 | 1.26 | -20.9% |
| 0.65 | 4.7% | 0.51 | 0.71 | -20.3% |
| 0.80 | 13.2% | 1.09 | 2.28 | -19.5% |
| 1.00 | 14.6% | 1.21 | 2.71 | -18.4% |

**Selected: α_TREND_OPT = 0.0**

---

## Attribution Table

| Config | Total Return | Sortino | Calmar | MaxDD | Δ Sortino vs H1 |
|--------|-------------|---------|--------|-------|----------------|
| H1-only (C_H1_final) | 39.9% | 2.78 | 11.03 | -15.5% | — |
| H2C-only (C_H2_final) | 34.2% | 1.34 | 2.96 | -47.0% | -1.44 |
| C_combined (α=0.00) | 35.6% | 2.51 | 9.68 | -15.1% | -0.27 |

---

## OOS Holdout (Dec 2024 – Jan 2025)

Parameters frozen from training-period sweep. No adjustment based on OOS results.

| Metric | Value |
|--------|-------|
| Total Return | 1.5% |
| Sortino | 0.40 |
| Calmar | 0.60 |
| Max Drawdown | -15.6% |

---

## Parameter Perturbation Robustness (±20%)

| Perturbation | Sortino | Calmar |
|-------------|---------|--------|
| −20% | 3.20 | 16.45 |
| baseline | 2.51 | 9.68 |
| +20% | 3.07 | 14.86 |

Robustness criterion: Calmar remains positive across all perturbations → PASS

*Charts: see `portfolio/charts/combined/`*
