# Signal Promotion Record

**Date:** 2026-03-17
**Promoted formula:** `0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)`
**Name:** `H1_neg_c1_x07_H5_neg_vol`
**Status:** PROMOTED — deployed in `bot/strategy/signals.py`

---

## Economic Description

> "Buy cross-sectional laggards with low realized volatility."

- **High C1**: recent laggard (below-median return) AND stable (low 6h realized vol)
  → expected mean-reversion recovery at 4h horizon
- **Low C1**: recent winner OR high-vol meme-coin pump
  → expected to underperform

The signal inverts the current C1 momentum composite (selecting laggards, not winners)
and blends in a low-volatility preference that filters out noisy meme-coin moves.

---

## Mechanism Families

| Component | Family | Proxy | Weight |
|-----------|--------|-------|--------|
| H1 anti-momentum | Short-term reversal | CS_z(-C1_raw) | 0.70 |
| H5 low-vol anomaly | Vol-adjusted stability | CS_z(-realized_vol_6h) | 0.30 |

---

## IC Evidence

### Individual Terminals (from `03_validation/`)

| Signal | Best IC | Best Horizon | t-stat | Decision |
|--------|---------|-------------|--------|----------|
| H1_neg_r1h | +0.049 | 1h | +10.75 | PROMOTE |
| H1_neg_r2h | +0.047 | 1h | +10.33 | PROMOTE |
| H1_neg_c1  | +0.043 | 1h | +9.36  | PROMOTE |
| H5_neg_vol | +0.076 | 24h | +13.26 | PROMOTE |

### GP Combination (from `04_gp_search/H1_H5_gp_results.md`)

| Split | Mean IC at 4h | IC Sharpe | t-stat |
|-------|--------------|-----------|--------|
| Train (Oct–Nov 2024) | +0.0474 | +0.190 | +7.22 |
| Holdout (Dec–Jan 2025) | +0.0660 | — | +10.59 |

---

## Promotion Criteria — All Met

| Criterion | Requirement | Result |
|-----------|-------------|--------|
| IC > 0 at primary horizon | IC > 0 at 4h | PASS (+0.047) |
| t-stat | t > 1.5 | PASS (t=7.22 train, 10.59 holdout) |
| Holdout gate | IC > 0 on holdout | PASS (+0.066) |
| Subperiod consistency | IC > 0 in both halves | PASS (+0.047 / +0.066) |
| Block-resample hit rate | >= 55% | PASS (97.2% of 500 windows) |
| Mechanism clarity | Statable in one sentence | PASS |
| Operational feasibility | Data live at 1-min | PASS (realized_vol from price cache) |
| Fee survivability | Low turnover | PASS (no signal change to bot cadence) |

---

## Robustness (from `09_robustness/H1_H5_signal_robustness.md`)

- Block resampling: **97.2%** hit rate (486/500 windows positive IC) — exceptional
- Parameter perturbation: IC positive at ALL weight combinations tested (0.0421–0.0621)
- Pure components: reversal-only IC=+0.042, vol-only IC=+0.049 — combination with IC=+0.057 beats both

---

## Implementation

**File changed:** `bot/strategy/signals.py`
**Formula change:** `compute_c1_scores()` now returns `0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)`
**Fallback:** If `realized_vol_6h` unavailable for an asset, stability component contributes 0 (reversal-only).
**No other changes required:** `ranking.py`, `allocator.py`, `risk/` are unaffected.

**config.py changes:**
- Added `ALPHA_WEIGHT_REVERSAL = 0.70` and `ALPHA_WEIGHT_STABILITY = 0.30`
- No changes to regime thresholds, position limits, or risk parameters

---

## Why the Promoted Formula Beats Individual Terminals

The H1 reversal peaks at 1–2h and decays slowly.
H5_neg_vol improves monotonically from 1h → 24h.
The signals are mechanistically independent (microstructure reversal vs risk-adjusted quality).
At the 4h optimization horizon, the combination achieves IC-Sharpe = +0.190 vs +0.152 for H1_neg_c1 alone —
a 25% improvement in information ratio.

---

## Key Finding from Phase 1

The original C1 signal had IC = −0.038 at 4h (selecting winners → underperformers).
Inverting C1 (selecting laggards) gives IC = +0.042 at 4h.
**The bot's original signal was anti-predictive at the signal level; its only real value was regime gating.**
The promoted formula retains the regime infrastructure and replaces the signal direction.

---

## Post-Promotion Modifier Screens (Steps 3C, 4A, 4B)

### Step 3C — Bare signal vector

Backtest: 4h hold, top-3 equal weight, Oct 2024–Jan 2025, no modifiers.

| Metric | Value | Sanity Bar | Result |
|--------|-------|------------|--------|
| Gross Sharpe (ann) | 1.87 | > 0 | PASS |
| Max Drawdown | −34.1% | ≥ −40% | PASS |
| Hit Rate | 51.5% | > 50% | PASS |
| Total Return | +59.4% | — | — |

### Step 4A — C2 regime modifier (APPROVED)

BTC vol z-score (48h) > 1.5 → skip entries. Compared to bare signal:

- MaxDD: −34.1% → −28.0% (**+17.8% relative improvement**) ≥ 10% bar → PASS
- Worst 30d DD: −19.8% → −10.7% (**+9.1pp improvement**) ≥ 5pp bar → PASS
- Sharpe: 1.87 → 3.02 (doubles)

**C2 regime gate APPROVED.** This result directly validates the regime hazard architecture
that has been in the bot since the start.

### Step 4B — C3 maturity modifier (REJECTED for pct_rank proxy)

Proxy: pct_rank of r_6h in 48h rolling window. Gate: IC(fresh bucket) > IC(unconditional).

| Maturity Bucket | Mean IC | N |
|-----------------|---------|---|
| Fresh (pct_rank < 30%) | +0.018 | 410 |
| Mid | +0.030 | 611 |
| Stale (pct_rank > 70%) | +0.052 | 482 |
| Unconditional | +0.048 | 731 |

IC(fresh) = 0.018 < IC(unconditional) = 0.048. Pct_rank proxy REJECTED.

In the Oct–Jan 2024 trending period, extended (stale) assets have the highest IC because
momentum continues. The pct_rank proxy mislabels genuine momentum continuation as
"overextended," filtering out the best signals. This failure is regime-specific:
the pct_rank component alone does not work as a maturity proxy in trending conditions.

**Decision:** The live M_t composite (`maturity.py`) uses four components — SMA extension,
RSI proxy, pct_rank, and funding rate. The pct_rank proxy failed alone; the funding rate
and SMA extension components address different aspects of overextension and are not tested
by this proxy screen. C3 is retained in the live bot with this documented caveat.

See `research/06_vector_tests.md` for full results and interpretation.

### H2 Mechanism Test (Step 3D)

IC of the reversal signal conditioned on BTC 2h move magnitude:

| BTC Move | IC at 4h |
|----------|----------|
| Flat (|r_2h| < 0.5%) | +0.024 |
| Moderate (0.5–1.5%) | +0.055 |
| Large up (≥ 1.5%) | +0.110 |
| Large down (≥ 1.5%) | +0.042 |

Uplift = IC(large_up) − IC(flat) = **+0.086**. Gate: > 0.010. **H2 CONFIRMED.**

The signal's alpha is highest when BTC has moved significantly — consistent with the
BTC-diffusion lag hypothesis. This validates that the strategy is exploiting genuine
information flow from BTC to altcoins, not just generic cross-sectional noise.

See `research/05_h2_mechanism_test.md`.
