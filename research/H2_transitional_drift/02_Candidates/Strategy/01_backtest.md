# H2C BTC Lead-Lag — Mechanism-Specific Backtest
**Generated:** 2026-03-17 14:49 UTC

## Signal Formula

```
H2C_score_i = CS_z(β_i × r_BTC,2h − r_i,2h)
β_i = rolling 48h OLS slope (r_i on r_BTC hourly returns)
```

IC = +0.042 @ 1h, t = +9.85 (signal_search.py, promoted)

---

## Version A — H2C Fee Sweep

| Run | Total Return | Sortino | Calmar | MaxDD |
|-----|-------------|---------|--------|-------|
| H2_A_fee0.00 | -7.4% | 0.29 | -0.39 | -51.9% |
| H2_A_fee0.05 | -7.5% | 0.29 | -0.40 | -51.9% |
| H2_A_fee0.10 | -7.5% | 0.29 | -0.40 | -51.9% |

---

## Risk Overlay Sweeps

### C: BTC-Direction Exit

Mechanism-appropriate exit: H2 relies on BTC continuing in the same direction.
Exit when BTC return since position entry falls below threshold.

| BTC Rev Exit | Sortino | Calmar | MaxDD | Exits Triggered |
|--------------|---------|--------|-------|----------------|
| None | 0.29 | -0.40 | -51.9% | 0 |
| -0.005 | 1.68 | 4.96 | -47.7% | 9 |
| -0.01 | 1.64 | 4.65 | -47.7% | 6 |
| -0.015 | 1.65 | 4.70 | -47.7% | 6 |
| -0.02 | 0.61 | 0.58 | -37.6% | 3 |
| -0.03 | 1.58 | 4.04 | -50.0% | 3 |

**Selected: H2_BTCREV_OPT = -0.005**

### D: Hold Cap (diffusion should complete within N hours)

| Hold Cap | Sortino | Calmar |
|----------|---------|--------|
| None | 1.68 | 4.96 |
| 3 | 0.99 | 1.87 |
| 4 | -0.00 | -0.63 |
| 5 | 0.23 | -0.21 |
| 6 | 0.23 | -0.27 |
| 8 | 0.00 | -0.74 |
| 12 | 0.01 | -0.71 |

**Selected: H2_HOLDCAP_OPT = None**

### E: BTC Magnitude Gate

H2 only admissible when BTC made a non-trivial directional move.

| BTC Gate | Sortino | Calmar | MaxDD |
|----------|---------|--------|-------|
| 0.000 | 1.68 | 4.96 | -47.7% |
| 0.003 | 1.68 | 5.06 | -47.7% |
| 0.005 | 1.71 | 5.52 | -47.7% |
| 0.007 | -0.07 | -0.94 | -50.4% |
| 0.010 | 0.92 | 1.88 | -44.6% |
| 0.015 | 0.20 | -0.53 | -51.6% |

**Selected: H2_GATE_OPT = 0.005**

---

## H2C Final — All Selected Layers

| Metric | Value |
|--------|-------|
| Total Return | 34.2% |
| Sortino | 1.34 |
| Calmar | 2.96 |
| Max Drawdown | -47.0% |

*Charts: see `H2_transitional_drift/02_Candidates/Strategy/charts/backtest/`*
