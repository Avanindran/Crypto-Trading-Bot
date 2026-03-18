# Section [G] — Dual Portfolio Backtest: Portfolio-Level Aggregation

## Architecture

| Engine | Role | Signal |
|--------|------|--------|
| H1 reversal | Cross-sectional laggards | −C1_raw_cs_z |
| H2C diffusion | BTC-lagging assets | β×r_BTC,2h − r_i,2h |

**Combination:** `combined_return_t = (1 − f_t) × H1_ret_t + f_t × H2C_ret_t`

**Continuous allocation formula (failure-mode derived):**

```
f_t = f_max × btc_activity_t × stress_decay_t

btc_activity_t = min(1, |r_BTC,2h| / 0.003)   ← 0 when BTC flat; H2C signal undefined
stress_decay_t = max(0, 1 − vol_z / 2.0)      ← 0 when vol_z≥2.0σ; correlations spike in stress
```

Fixed parameters (not swept): btc_scale=0.003  z_scale=2.0  lookback=48h  n_train=2952h

---

## [G-0] Baseline — Standalone Engine Performance

| Engine | Total Return | Sortino | Calmar | MaxDD |
|--------|-------------|---------|--------|-------|
| H1 only | 38.0% | 2.69 | 11.73 | -13.6% |
| H2C only | 74.0% | 1.99 | 20.25 | -20.6% |

---

## [G-1] f_max Sweep (Continuous Allocation)

| f_max | Total Return | Sortino | Calmar | MaxDD | mean(f_t) | Δ Sortino vs H1 |
|-------|-------------|---------|--------|-------|-----------|----------------|
| 0.00 | 38.1% | 2.70 | 11.76 | -13.6% | 0.0% | +0.00 |
| 0.10 | 41.4% | 2.90 | 13.31 | -13.5% | 7.4% | +0.21 |
| 0.20 | 44.7% | 3.06 | 14.97 | -13.3% | 14.7% | +0.36 |
| 0.30 | 48.0% | 3.17 | 16.64 | -13.2% | 22.1% | +0.47 |
| 0.40 | 51.2% | 3.25 | 18.33 | -13.2% | 29.5% | +0.55 |
| 0.50 | 54.5% | 3.30 | 19.22 | -13.7% | 36.8% | +0.61 |
| 0.60 | 57.7% | 3.33 | 20.09 | -14.3% | 44.2% | +0.64 |
| 0.80 | 64.1% | 3.32 | 19.98 | -16.7% | 59.0% | +0.62 |
| 1.00 | 70.2% | 3.24 | 20.03 | -19.2% | 73.7% | +0.54 |

**Optimal: f_max_opt = 0.50  (mean active fraction ≈ 36.8%)**

Portfolio agg: ret=54.5%  Sortino=3.30  Calmar=19.22  MaxDD=-13.7%

---

## [G-2] OOS Holdout (Dec 2024 – Jan 2025)

| Metric | H1 only | H2C only | Portfolio agg |
|--------|---------|---------|---------------|
| Total Return | 8.2% | 0.1% | 9.3% |
| Sortino | 1.33 | 0.25 | 1.40 |
| Calmar | 4.32 | 0.03 | 5.04 |
| Max Drawdown | -13.6% | -20.6% | -13.7% |

---

## [G-3] Perturbation Robustness (±20% on f_max)

| Delta | f_max | Sortino | Calmar | MaxDD |
|-------|-------|---------|--------|-------|
| -20% | 0.40 | 3.25 | 18.33 | -13.2% |
| baseline | 0.50 | 3.30 | 19.22 | -13.7% |
| +20% | 0.60 | 3.33 | 20.09 | -14.3% |

Robustness criterion: Sortino positive and Calmar positive across all perturbations.

---

## [G-4] Activation Gates

- Gate 1 (Sortino ≥ 1.05×H1 = 2.83): **PASS** (achieved 3.30)
- Gate 2 (Calmar  ≥ 0.90×H1 = 10.56):  **PASS** (achieved 19.22)
- Gate 3 (OOS Sortino > H1-OOS = 1.33): **PASS** (achieved 1.40)
- **Overall: ALL PASS**

---

## Action

All gates passed. Update `config.py`:

```python
H2C_MAX_FRACTION: float = 0.50   # continuous allocation, f_max
H2C_BTC_SCALE:    float = 0.003       # btc_activity ramp threshold
H2C_Z_SCALE:      float = 2.0       # stress_decay zero point
```

Run full test suite: `python -X utf8 tests/test_engine_aggregator.py`

---

*Charts: `portfolio/charts/combined/portfolio_aggregation_equity.png`*
