# H1 Reversal — Mechanism-Specific Backtest
**Generated:** 2026-03-17 14:48 UTC

## Parameter Disclosure

All risk overlay parameters selected by sweep on Oct–Nov 2024 training period.
OOS window (Dec 2024–Jan 2025) evaluated **after** parameter selection, never used for selection.

| Parameter | Value | Source |
|-----------|-------|--------|
| C1 formula | 0.70×CS_z(−C1_raw) + 0.30×CS_z(−rvol) | signal_search.py / vector_tests.py |
| Hold cadence | 4h | vector_tests.py (promoted object) |
| TOP_N | 3 | Portfolio sweep |
| Sizing | kelly | Portfolio sweep |
| C2 z-threshold | 0.75 | Regime sweep |
| Stop-loss | -0.04 | Risk overlay sweep |
| C1 exit threshold | 0.25 | Signal exit sweep |
| Fee/trade | 0.05% maker | Competition rules |

---

## Version A — Cross-Validation (must match vector_tests.py within 0.1pp)

| Run | Total Return | Sortino | Calmar | MaxDD |
|-----|-------------|---------|--------|-------|
| H1_A_bare_fee0.00 | 95.2% | 2.56 | 0.00 | -30.5% |
| H1_A_bare_fee0.05 | -6.0% | 0.29 | 0.00 | -42.8% |
| H1_A_bare_fee0.10 | -54.8% | -1.98 | 0.00 | -63.0% |
| H1_A_c2_fee0.00 | 149.2% | 3.58 | 0.00 | -21.3% |
| H1_A_c2_fee0.05 | 28.9% | 1.31 | 0.00 | -31.4% |
| H1_A_c2_fee0.10 | -33.4% | -0.96 | 0.00 | -49.2% |

---

## Risk Overlay Sweeps

### B: Stop-Loss Threshold

| Stop Level | Total Return | Calmar | MaxDD | Stops/Period |
|------------|-------------|--------|-------|--------------|
| -0.01 | 31.8% | 3.75 | -33.9% | 5.4% |
| -0.02 | 26.3% | 2.76 | -36.1% | 3.8% |
| -0.03 | 30.6% | 4.14 | -29.2% | 3.0% |
| -0.04 | 36.4% | 4.77 | -31.7% | 1.4% |
| -0.05 | -13.7% | -0.67 | -52.8% | 1.5% |
| -0.06 | -12.2% | -0.66 | -48.3% | 1.1% |
| -0.08 | 21.8% | 1.57 | -50.6% | 0.7% |
| None | -11.9% | -0.55 | -56.9% | 0.0% |

**Selected: H1_SL_OPT = -0.04**

### C: C1 Signal Exit

| Exit Threshold | Total Return | Sortino | Calmar |
|---------------|-------------|---------|--------|
| None | 36.4% | 1.41 | 4.77 |
| 0.05 | 18.5% | 0.96 | 1.58 |
| 0.1 | 23.7% | 1.12 | 2.26 |
| 0.15 | 26.5% | 1.19 | 2.71 |
| 0.2 | 31.3% | 1.32 | 3.25 |
| 0.25 | 53.4% | 1.86 | 7.05 |
| 0.3 | 24.4% | 1.15 | 2.39 |

**Selected: H1_EXIT_OPT = 0.25**

### D: Regime Z-Threshold

| Z-Threshold | Total Return | Calmar | MaxDD |
|-------------|-------------|--------|-------|
| 0.75 | 80.6% | 14.52 | -32.9% |
| 1.0 | 78.8% | 13.95 | -33.0% |
| 1.25 | 69.2% | 11.07 | -33.9% |
| 1.5 | 53.4% | 7.05 | -36.2% |
| 1.75 | 39.1% | 4.15 | -40.0% |
| 2.0 | 19.8% | 1.57 | -45.0% |
| 2.5 | 42.7% | 4.83 | -38.7% |

**Selected: H1_Z_OPT = 0.75**

---

## H1 Final — All Selected Layers

| Metric | Value |
|--------|-------|
| Total Return | 39.9% |
| Annualized Return | 170.5% |
| Sortino | 2.78 |
| Calmar | 11.03 |
| Max Drawdown | -15.5% |

## OOS Holdout (Dec 2024 – Jan 2025)

| Metric | Value |
|--------|-------|
| Total Return | 2.5% |
| Sortino | 0.53 |
| Calmar | 0.97 |
| Max Drawdown | -15.9% |

---

*Charts: see `H1_reversal/02_Candidates/Strategy/charts/backtest/`*
