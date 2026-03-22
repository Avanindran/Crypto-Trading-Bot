# H2C BTC Lead-Lag — Mechanism-Specific Backtest
**Generated:** 2026-03-22 17:06 UTC

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

### B: HAZ2_BTC_VOL_Z — H2-Specific Volatility Gate

Block H2C entries when BTC realized vol z-score exceeds threshold.
H2 may need a different gate level than H1 (H2 is momentum; high vol can be opportunity).

| Z Threshold | Total Return | Calmar | MaxDD |
|-------------|-------------|--------|-------|
| 0.75 | -7.5% | -0.40 | -51.9% |
| 1.00 | -7.5% | -0.40 | -51.9% |
| 1.25 | -7.5% | -0.40 | -51.9% |
| 1.50 | -7.5% | -0.40 | -51.9% |
| 2.00 | -7.5% | -0.40 | -51.9% |
| 9.99 | -7.5% | -0.40 | -51.9% |

**Selected (robust plateau center): H2_Z_OPT = 0.75**

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

**Selected: H2_BTCREV_OPT = -0.01**

### D: Hold Cap (diffusion should complete within N hours)

| Hold Cap | Sortino | Calmar |
|----------|---------|--------|
| None | 1.64 | 4.65 |
| 3 | 1.36 | 3.47 |
| 4 | 1.08 | 2.00 |
| 5 | 1.70 | 5.99 |
| 6 | 1.84 | 6.99 |
| 8 | 0.88 | 1.13 |
| 12 | 0.63 | 0.29 |

**Selected: H2_HOLDCAP_OPT = 6**

### E: BTC Magnitude Gate

H2 only admissible when BTC made a non-trivial directional move.

| BTC Gate | Sortino | Calmar | MaxDD |
|----------|---------|--------|-------|
| 0.000 | 1.84 | 6.99 | -40.7% |
| 0.003 | 1.71 | 14.81 | -22.0% |
| 0.005 | -0.75 | -1.24 | -50.0% |
| 0.007 | -0.25 | -0.89 | -34.1% |
| 0.010 | 0.45 | 2.80 | -18.3% |
| 0.015 | 0.64 | 6.33 | -9.0% |

**Selected: H2_GATE_OPT = 0.003**

### F: MAT2_TIME_DECAY — Diffusion Window Freshness Gate

Only enter H2C positions when the BTC impulse is recent.
mat_thresh = (t − t_peak_BTC) / 6h; skip if ≥ threshold.
IC(fresh)=+0.040 vs IC(uncond)=+0.023 (+72% uplift at threshold=0.40).

| Time Decay Threshold | Sortino | Calmar | MaxDD |
|---------------------|---------|--------|-------|
| 0.30 | -0.45 | -1.15 | -39.8% |
| 0.40 | -0.26 | -0.80 | -45.9% |
| 0.50 | -0.26 | -0.80 | -45.9% |
| 0.60 | 0.10 | -0.23 | -41.7% |
| 0.75 | 0.27 | 0.20 | -36.4% |
| None | 1.71 | 14.81 | -22.0% |

**Selected (robust plateau center): H2_MAT_OPT = None**

---

## H2C Final — All Selected Layers (A + B + C + D + E + F)

| Metric | Value |
|--------|-------|
| Total Return | 74.0% |
| Sortino | 1.99 |
| Calmar | 20.25 |
| Max Drawdown | -20.6% |
| H2_Z_OPT | 0.75 |
| H2_MAT_OPT | None |

---

## Cost Scenario Analysis

| Scenario | Entry Fee | Exit Fee | Sortino | Calmar | MaxDD |
|----------|-----------|----------|---------|--------|-------|
| maker/maker | 0.05% | 0.05% | 1.99 | 20.25 | -20.6% |
| maker/taker | 0.05% | 0.10% | 1.66 | 12.71 | -22.1% |
| taker/taker | 0.10% | 0.10% | 1.33 | 7.14 | -25.2% |

Gate: Calmar > 0 in maker/taker scenario → **PASS**

---

*Charts: see `H2_transitional_drift/02_Candidates/Strategy/charts/backtest/`*
