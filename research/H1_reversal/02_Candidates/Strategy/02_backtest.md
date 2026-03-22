# H1 Reversal — Mechanism-Specific Backtest
**Generated:** 2026-03-22 16:41 UTC

## Parameter Disclosure

All risk overlay parameters selected by sweep on Oct–Nov 2024 training period.
OOS window (Dec 2024–Jan 2025) evaluated **after** parameter selection, never used for selection.

| Parameter | Value | Source |
|-----------|-------|--------|
| C1 formula | 0.70×CS_z(−C1_raw) + 0.30×CS_z(−rvol) | signal_search.py / vector_tests.py |
| Hold cadence | 4h | vector_tests.py (promoted object) |
| TOP_N | 3 | Portfolio sweep |
| Sizing | kelly | Portfolio sweep |
| C2 z-threshold | 1.0 | Regime sweep |
| Stop-loss | -0.03 | Risk overlay sweep |
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

**Selected: H1_SL_OPT = -0.03**

### C: C1 Signal Exit

| Exit Threshold | Total Return | Sortino | Calmar |
|---------------|-------------|---------|--------|
| None | 30.6% | 1.33 | 4.14 |
| 0.05 | 7.9% | 0.65 | 0.57 |
| 0.1 | 24.6% | 1.15 | 2.29 |
| 0.15 | 35.3% | 1.44 | 3.70 |
| 0.2 | 34.2% | 1.41 | 3.54 |
| 0.25 | 50.7% | 1.80 | 6.57 |
| 0.3 | 28.4% | 1.25 | 2.86 |

**Selected: H1_EXIT_OPT = 0.25**

### D: Regime Z-Threshold

| Z-Threshold | Total Return | Calmar | MaxDD |
|-------------|-------------|--------|-------|
| 0.75 | 76.1% | 13.05 | -33.4% |
| 1.0 | 69.2% | 11.39 | -33.0% |
| 1.25 | 62.8% | 9.57 | -33.9% |
| 1.5 | 50.7% | 6.57 | -36.2% |
| 1.75 | 43.6% | 4.66 | -41.2% |
| 2.0 | 24.6% | 1.95 | -47.0% |
| 2.5 | 39.5% | 4.35 | -38.7% |

**Selected: H1_Z_OPT = 1.0**

---

## H1 Final — All Selected Layers

| Metric | Value |
|--------|-------|
| Total Return | 38.0% |
| Annualized Return | 160.1% |
| Sortino | 2.69 |
| Calmar | 11.73 |
| Max Drawdown | -13.6% |

## OOS Holdout (Dec 2024 – Jan 2025)

| Metric | Value |
|--------|-------|
| Total Return | 6.9% |
| Sortino | 1.13 |
| Calmar | 3.43 |
| Max Drawdown | -14.1% |

---

## Cost Scenario Analysis

Strategy must remain Sortino > 0 and Calmar > 0 across all realistic fee scenarios.

| Scenario | Entry Fee | Exit Fee | Sortino | Calmar | MaxDD |
|----------|-----------|----------|---------|--------|-------|
| maker/maker | 0.05% | 0.05% | 2.69 | 11.73 | -13.6% |
| maker/taker | 0.05% | 0.10% | 2.28 | 8.71 | -14.1% |
| taker/taker | 0.10% | 0.10% | 1.88 | 6.25 | -14.6% |

Gate: Calmar > 0 in maker/taker scenario → **PASS**

---

*Charts: see `H1_reversal/02_Candidates/Strategy/charts/backtest/`*
