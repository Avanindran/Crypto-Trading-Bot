# Dual-Engine Regime-Conditional Allocation
**Generated:** 2026-03-18 08:53 UTC

## Architecture

| Regime State | Condition | Allocation |
|-------------|-----------|-----------|
| TREND_ACTIVE | |r_BTC,2h| ≥ 0.5% | α×H2C + (1−α)×H1 (α=0.00) |
| TREND_FLAT | |r_BTC,2h| < 0.5% | H1 only (α=0) |
| HAZARD | BTC vol z > 1.0 | No new entries |

---

## alpha_TREND Sweep (H2 weight in TREND_ACTIVE periods)

| α | Total Return | Sortino | Calmar | MaxDD |
|---|-------------|---------|--------|-------|
| 0.00 | 39.3% | 2.78 | 12.13 | -13.8% |
| 0.10 | 25.4% | 1.93 | 6.66 | -14.4% |
| 0.20 | 27.4% | 2.03 | 6.47 | -16.3% |
| 0.35 | 23.6% | 1.80 | 4.68 | -18.7% |
| 0.50 | 18.2% | 1.49 | 3.72 | -17.2% |
| 0.65 | 8.1% | 0.78 | 1.59 | -16.3% |
| 0.80 | 14.5% | 1.24 | 3.25 | -15.3% |
| 1.00 | 15.6% | 1.34 | 3.51 | -15.4% |

**Selected: α_TREND_OPT = 0.0**

---

## Attribution Table

| Config | Total Return | Sortino | Calmar | MaxDD | Δ Sortino vs H1 |
|--------|-------------|---------|--------|-------|----------------|
| H1-only (C_H1_final) | 38.0% | 2.69 | 11.73 | -13.6% | — |
| H2C-only (C_H2_final) | 74.0% | 1.99 | 20.25 | -20.6% | -0.70 |
| C_combined (α=0.00) | 39.3% | 2.78 | 12.13 | -13.8% | 0.08 |

---

## OOS Holdout (Dec 2024 – Jan 2025)

Parameters frozen from training-period sweep. No adjustment based on OOS results.

| Metric | Value |
|--------|-------|
| Total Return | 5.6% |
| Sortino | 0.96 |
| Calmar | 2.65 |
| Max Drawdown | -14.3% |

---

## Parameter Perturbation Robustness (±20%)

| Perturbation | Sortino | Calmar |
|-------------|---------|--------|
| −20% | 2.12 | 7.26 |
| baseline | 2.78 | 12.13 |
| +20% | 3.19 | 15.31 |

Robustness criterion: Calmar remains positive across all perturbations → PASS

---

## Cost Scenario Analysis

| Scenario | Entry Fee | Exit Fee | Sortino | Calmar | MaxDD |
|----------|-----------|----------|---------|--------|-------|
| maker/maker | 0.05% | 0.05% | 2.78 | 12.13 | -13.8% |
| maker/taker | 0.05% | 0.10% | 2.36 | 9.09 | -14.3% |
| taker/taker | 0.10% | 0.10% | 1.97 | 6.61 | -14.7% |

Gate: Calmar > 0 in maker/taker scenario → **PASS**

---

*Charts: see `portfolio/charts/combined/`*
