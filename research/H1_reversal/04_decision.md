# H1 — Signal Promotion Decision

**Date:** 2026-03-17
**Decision:** PROMOTED
**Promoted formula:** `0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)`
**Name:** `H1_neg_c1_x07_H5_neg_vol`
**Status:** Live in `bot/strategy/signals.py`

---

## Economic Description

> "Buy cross-sectional laggards with low realized volatility."

- **High score:** recent laggard (below-median return) AND stable (low 6h realized vol) → expected mean-reversion recovery at 4h horizon
- **Low score:** recent winner OR high-vol meme-coin pump → expected to underperform

The signal inverts the C1 momentum composite (selecting laggards, not winners) and blends in a low-volatility preference that filters out noisy meme-coin moves.

---

## IC Evidence

### Individual Terminals

| Signal | Best IC | Best Horizon | t-stat | Decision |
|--------|---------|-------------|--------|----------|
| H1_neg_r1h | +0.049 | 1h | +10.75 | PROMOTE terminal |
| H1_neg_r2h | +0.047 | 1h | +10.33 | PROMOTE terminal |
| H1_neg_c1  | +0.043 | 1h | +9.36  | PROMOTE → GP input |
| H5_neg_vol | +0.076 | 24h | +13.26 | PROMOTE terminal |
| H5_sharpe_6h | −0.022 | — | — | FAIL (negative IC) |
| H5_sharpe_24h | — | — | — | FAIL (negative IC) |
| H5_sortino_6h | — | — | — | FAIL (negative IC) |

### GP Combination (train vs holdout)

| Split | Mean IC at 4h | IC-Sharpe | t-stat |
|-------|--------------|-----------|--------|
| Train (Oct–Nov 2024) | +0.047 | +0.190 | +7.22 |
| Holdout (Dec–Jan 2025) | +0.066 | — | +10.59 |

**Combined IC at 4h (full period):** +0.057 (t = 12.7)

---

## Promotion Criteria — All Met

| Criterion | Requirement | Result |
|-----------|-------------|--------|
| IC > 0 at primary horizon | IC > 0 at 4h | PASS (+0.047 train) |
| t-stat | t > 1.5 | PASS (t=7.22 train, 10.59 holdout) |
| Holdout gate | IC > 0 on holdout | PASS (+0.066) |
| Subperiod consistency | IC > 0 in both halves | PASS (+0.047 / +0.066) |
| Block-resample hit rate | >= 55% | PASS (97.2% of 500 windows) |
| Mechanism clarity | Statable in one sentence | PASS |
| Operational feasibility | Data live at 1-min | PASS (realized_vol from price cache) |

---

## Robustness Evidence

- **Block resampling:** 97.2% hit rate (486/500 10-day windows positive IC) — exceptional
- **Parameter perturbation:** IC positive at ALL weight combinations tested (w in 0.0–1.0)
  - w=0.0 (reversal only): IC = +0.042
  - w=0.3 (selected): IC = +0.057
  - w=1.0 (vol-only): IC = +0.049
- **GP-optimal weight:** w_H5 = 0.30, validated by IC-Sharpe maximization on training period

Full robustness: see [02_Candidates/Strategy/03_robustness.md](02_Candidates/Strategy/03_robustness.md).

---

## Why Combination Beats Individual Terminals

The H1 reversal peaks at 1–2h and decays slowly.
H5_neg_vol improves monotonically from 1h → 24h.
The signals are mechanistically independent (microstructure reversal vs low-vol stability).

At the 4h optimization horizon, the combination achieves IC-Sharpe = +0.190 vs +0.152 for H1_neg_c1 alone — a 25% improvement in information ratio.

---

## Vector Test Results (post-promotion sanity check)

| Metric | Bare signal | + C2 regime | + C2 + C3 | Sanity bar | Result |
|--------|-------------|-------------|-----------|-----------|--------|
| Sharpe (ann) | 1.87 | 3.02 | 3.16 | > 0 | PASS |
| MaxDD | −34.1% | −28.0% | −23.6% | ≥ −40% | PASS |
| Hit rate | 51.5% | — | — | > 50% | PASS |
| Total return | +59.4% | +73.8% | +75.8% | — | — |
| Calmar | 5.07 | 18.13 | 18.67 | — | — |
| Sortino | 2.31 | 3.94 | 4.33 | — | — |

Full vector tests: see [02_Candidates/Strategy/01_vector_tests.md](02_Candidates/Strategy/01_vector_tests.md).

---

## Key Finding from Signal Research

The original C1 signal (pre-research) had IC = −0.038 at 4h, selecting winners → underperformers.
Inverting C1 (selecting laggards) gives IC = +0.042 at 4h.

**The bot's original signal was anti-predictive at the signal level; its only real value was regime gating.**
The promoted formula retains the regime infrastructure and replaces the signal direction.

---

## Implementation

- **File:** `bot/strategy/signals.py`, function `compute_c1_scores()`
- **Formula change:** Returns `0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)` (was `CS_z(C1_raw)`)
- **Fallback:** If `realized_vol_6h` unavailable, stability component contributes 0 (reversal-only)
- **No other changes:** `ranking.py`, `allocator.py`, `risk/` are unaffected
- **config.py additions:** `ALPHA_WEIGHT_REVERSAL = 0.70`, `ALPHA_WEIGHT_STABILITY = 0.30`

---

## Navigation

| Step | File |
|------|------|
| Proxy universe | [01_Proxies/00_proxy_universe.md](01_Proxies/00_proxy_universe.md) |
| IC results (CS) | [02_Candidates/Signal/01_ic_results.md](02_Candidates/Signal/01_ic_results.md) |
| IC results (TS + H2) | [02_Candidates/Signal/05_ts_variant_search.md](02_Candidates/Signal/05_ts_variant_search.md) |
| GP combination search | [02_Candidates/Signal/04_combination_search.md](02_Candidates/Signal/04_combination_search.md) |
| Vector tests | [02_Candidates/Strategy/01_vector_tests.md](02_Candidates/Strategy/01_vector_tests.md) |
| Backtest | [02_Candidates/Strategy/02_backtest.md](02_Candidates/Strategy/02_backtest.md) |
| Robustness | [02_Candidates/Strategy/03_robustness.md](02_Candidates/Strategy/03_robustness.md) |
| Limitations | [05_limitations.md](05_limitations.md) |
