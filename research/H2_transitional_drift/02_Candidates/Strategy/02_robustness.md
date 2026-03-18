# H2C Engine Robustness — BTC-Diffusion Signal

**Run:** 2026-03-18 00:36 UTC
**Signal:** CS_z(β_i × r_BTC,2h − r_i,2h), β from rolling 48h OLS
**Evaluation horizon:** 4h forward return

## Full-Period IC

| Period | Mean IC | t-stat | n |
|--------|---------|--------|---|
| Oct 2024 – Jan 2025 | 0.0291 | 6.9297 | 2924 |
| Oct–Nov 2024 | 0.0276 | 4.6790 | 1440 |
| Dec 2024–Jan 2025 | 0.0311 | 5.1518 | 1461 |

## Block Resampling

**Method:** 500 random 10-day windows from Oct 2024–Jan 2025.
Each window uses a 48h pre-window warm-up to build β_hist without look-ahead.
Gate: hit rate (fraction of windows with positive mean IC) ≥ 55%.

| Metric | Value |
|--------|-------|
| Valid windows | 500 |
| Positive IC windows | 443 |
| Hit rate | 88.6% |
| Gate (≥55%) | **PASS** |

## Parameter Perturbation

Testing 9 combinations of β_window ∈ {24, 48, 72}h × r_BTC horizon ∈ {1, 2, 4}h.
Confirms no cliff edges around the baseline configuration.

| β_window | BTC horizon | Mean IC | t-stat | Notes |
|----------|-------------|---------|--------|-------|
| 24h | 1h | 0.0256 | 6.1853 |  |
| 24h | 2h | 0.0289 | 6.9074 |  |
| 24h | 4h | 0.0247 | 5.8013 |  |
| 48h | 1h | 0.0247 | 5.9378 |  |
| 48h | 2h | 0.0291 | 6.9297 | **BASELINE** |
| 48h | 4h | 0.0259 | 6.0822 |  |
| 72h | 1h | 0.0246 | 5.9501 |  |
| 72h | 2h | 0.0298 | 7.1060 |  |
| 72h | 4h | 0.0285 | 6.6577 |  |

## Robustness Kill Criteria

| Criterion | Threshold | Result |
|-----------|-----------|--------|
| Subperiod sign flip (Oct–Nov) | IC > 0 | **PASS** |
| Subperiod sign flip (Dec–Jan) | IC > 0 | **PASS** |
| Block-resample hit rate | ≥ 55% | **PASS** |
| Parameter sensitivity | Baseline IC ≥ 50% of median across grid | **PASS** |

## Conclusion

**ROBUST — all kill criteria pass.**
H2C BTC-diffusion signal retained for portfolio combination.
