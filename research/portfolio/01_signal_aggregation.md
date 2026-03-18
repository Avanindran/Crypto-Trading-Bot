# Portfolio — H1 + H2 Signal Aggregation Framework

**Written:** 2026-03-17
**Status:** H1 live; H2c deployed via continuous allocation (engine_aggregator.py)

---

## Architectural Overview

H1 (Reversal archetype) and H2 (Momentum/Transitional Drift archetype) are mechanistically distinct:

| Property | H1 Reversal | H2 Transitional Drift |
|----------|-------------|----------------------|
| Archetype | Reversal (reaction magnitude error) | Momentum (updating speed error) |
| Selection criterion | Cross-sectional laggards (overshoot downward) | BTC-relative laggards (diffusion gap) |
| Admissible state | Non-trending, non-hazardous (LSI < 0.40) | BTC has made directional move |
| Not admissible | HAZARD regime; strong downtrend | BTC flat; alt-season |
| IC at BTC flat | +0.024 | Near zero |
| IC at BTC large up | +0.110 | Expected high |
| Signal formula | `0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−rvol)` | Δᵢ = βᵢ · r_BTC − r_i (pending) |

In a BTC uptrend where some altcoins lag, BOTH mechanisms can fire simultaneously (the same laggard is both an overshoot candidate AND a BTC-diffusion candidate). The dual-engine aggregation must handle this overlap.

---

## Current State — H1 + H2C (Continuous Allocation)

```python
# engine_aggregator.py
w_h2c = f_t  # = f_max × btc_activity × stress_decay
C1_i = (1 - w_h2c) * H1_score_i + w_h2c * H2C_score_i
```

The continuous allocation formula allocates to H2C dynamically — zero when BTC is flat (btc_activity=0) or market is stressed (stress_decay=0), up to f_max=0.50 when both conditions are favorable. Mean active H2C fraction ≈ 36.8%.

---

## Target State — Regime-Conditional Dual Engine

When H2 proxy is validated, the aggregation should be regime-conditional:

### TREND regime (BTC moving, low hazard, MPI > 0.50)

Both mechanisms are active simultaneously:
- H2 has higher expected IC (BTC move provides the information event to diffuse)
- H1 provides the cross-sectional ranking of which altcoins are the best diffusion targets

```
C1_i = α_TREND × H2_score_i + (1 − α_TREND) × H1_score_i
    α_TREND = 0.65    (H2-weighted: BTC diffusion dominates in trend)
    1−α_TREND = 0.35  (H1 provides asset selection filter)

regime_scale = exp(−λ_TREND) = exp(−0.3) = 0.74
gross_cap = 85% NAV, max 5 positions
```

### NEUTRAL regime (BTC choppy, no strong directional move)

H2 has near-zero IC (BTC hasn't moved → no diffusion to exploit). H1 dominates.

```
C1_i = α_NEUTRAL × H2_score_i + (1 − α_NEUTRAL) × H1_score_i
    α_NEUTRAL = 0.20    (H2 minimal weight: no BTC signal)
    1−α_NEUTRAL = 0.80  (H1 primary: cross-sectional reversal)

regime_scale = exp(−λ_NEUTRAL) = exp(−0.8) = 0.45
gross_cap = 65% NAV, max 3 positions
```

### HAZARD regime (LSI > 0.60)

Both signals suppressed. The corrective flow H1 relies on has withdrawn; the BTC-diffusion transmission H2 relies on is contaminated by stress-driven flows.

```
C1_i = 0    (signal irrelevant — regime gate dominates)
regime_scale = exp(−λ_HAZARD) = exp(−4.0) = 0.018
gross_cap = 0% (no new entries), emergency exits above DD threshold
```

---

## Overlap Handling

In TREND regime, H1 and H2 often select the same assets (BTC-relative laggards that have also underperformed the cross-section). The weighted blend handles this correctly:

- The asset gets high score from both H1 and H2
- The blend amplifies the score (not double-counts it, because both are normalized to [−1, +1] via CS_z)
- The regime gross cap limits the total exposure regardless of signal strength

The overlap is a feature, not a bug: in TREND conditions, an asset that is lagging both in absolute terms (H1) and relative to BTC (H2) has stronger expected forward return than an asset identified by only one mechanism.

---

## Implementation Readiness

| Component | Status | Required before deployment |
|-----------|--------|--------------------------|
| H1_score_i | Live | — |
| H2_score_i (Δᵢ proxy) | **Deployed** | H2c (beta-adjusted gap) — IC=+0.042 @ 1h (t=+9.85) |
| f_t allocation weight | **Deployed** | Continuous: f_max × btc_activity × stress_decay |
| Alt-season regime detector | Addressed | stress_decay=0 when vol_z ≥ 2σ (correlation regime shift) |

**Timeline:** H2c deployed in Round 1. Combined result: Sortino=3.30, Calmar=19.22, OOS Sortino=1.40 (Section [G]). See `research/portfolio/05_dual_portfolio_backtest.md`.

**Note:** The discrete regime-conditional blend (α_TREND=0.65) described in "Target State" above was evaluated but superseded by the continuous allocation approach, which does not require discrete regime classification for H2C weighting.

---

## Empirical Basis for Proposed Weights

The proposed weights (α_TREND = 0.65, α_NEUTRAL = 0.20) are derived from the H2 mechanism test:

```
IC(H1 | BTC_flat)  = +0.024    → H2 contributes ~20% of total IC in neutral conditions
IC(H1 | BTC_large) = +0.110    → H2 mechanism responsible for ~78% of IC uplift

Proposed α_TREND = 0.65 reflects ~2:1 H2:H1 weighting in high-BTC-move conditions
Proposed α_NEUTRAL = 0.20 reflects H2 near-zero contribution when BTC is flat
```

These weights are provisional — they will require IC-Sharpe optimization on a training split once H2 proxy is validated.
