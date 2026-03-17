# Portfolio Design — Signal Aggregation Philosophy

**Written:** 2026-03-17
**Status:** H1 live; H2 pending proxy validation

---

## Design Objective

The portfolio construction layer resolves three questions independently:

1. **What to buy?** — Signal layer: H1 (cross-sectional reversal) + H2 (BTC-diffusion, pending)
2. **When to buy?** — Regime layer: λ_t from LSI/MPI/FEI cascade
3. **How much to buy?** — Sizing layer: Quarter-Kelly, regime gross cap

Each layer operates independently. The signal does not need to know about regime; the regime does not need to know about sizing. This separation ensures each component can be validated and replaced without affecting the others.

---

## Position Scoring Formula

```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
```

| Component | Source | Role |
|-----------|--------|------|
| `C1_i` | H1 reversal + H5 stability blend | Signal: who to buy |
| `exp(−λ_t)` | Regime overlay (LSI → λ cascade) | Admissibility gate: when to buy |
| `(1 − M_t_i)` | Maturity overlay (overextension) | Entry timing: how early is the recovery |

The components multiply: a strong signal in a hazardous regime still produces near-zero score. An admissible regime with a weak signal also produces near-zero score. Both conditions must be favorable for a position to be sized meaningfully.

---

## Signal Layer Design

### Current State — Single Engine (H1 only)

```
C1_i = 0.70 × CS_z(−C1_raw_i) + 0.30 × CS_z(−realized_vol_6h_i)
    C1_raw_i = 0.10×r_30m + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r2h)
```

H1 is the only live signal. It selects cross-sectional laggards (reversal archetype) blended with low-volatility preference (stability filter).

### Target State — Dual Engine (H1 + H2)

When H2 proxy is implemented:

```
C1_i = w_H1 × H1_score_i + w_H2 × H2_score_i
    w_H1, w_H2 regime-conditional (see 01_signal_aggregation.md)
```

H1 and H2 are mechanistically distinct (reversal vs momentum) and should be regime-conditionally blended, not uniformly combined. See [01_signal_aggregation.md](01_signal_aggregation.md).

---

## Portfolio Construction Rules

### Step 1 — Score Filtering

```python
positive_scores = {i: score for i, score in scores.items() if score > SCORE_THRESHOLD}
```

Assets with non-positive combined score are excluded regardless of signal strength.

### Step 2 — Regime Gross Cap

```
TREND_SUPPORTIVE:  gross_exposure ≤ 85% NAV, max 5 positions
NEUTRAL_MIXED:     gross_exposure ≤ 65% NAV, max 3 positions
HAZARD_DEFENSIVE:  gross_exposure = 0% (no new entries)
```

### Step 3 — Quarter-Kelly Sizing

```
kelly_weight_i = 0.25 × IC_bar × score_i / var_forward_return
final_weight_i = clip(kelly_weight_i, MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT)
    MIN_POSITION_WEIGHT = 0.05 (5% NAV)
    MAX_POSITION_WEIGHT = 0.30 (30% NAV)
```

**Finding:** With MAX_POSITION_WEIGHT at 0.30, raw Kelly weights for top-K assets typically exceed the cap (Kelly weights ~3.0+ → all top-K hit the 30% cap). Quarter-Kelly effectively collapses to equal weight in normal operation. Both equal weight and Quarter-Kelly produce identical Sortino (10.48) in backtests.

### Step 4 — Score-Proportional Allocation (deployed)

```
raw_allocation_i = score_i / sum(score_j for top-K assets)
final_allocation_i = clip(raw_allocation_i, MIN_POSITION_WEIGHT, MAX_POSITION_WEIGHT)
```

Score-proportional produces marginally higher IC-Sharpe (11.35 vs 10.48) in portfolio tests. This is the deployed method.

---

## Navigation

| File | Content |
|------|---------|
| [01_signal_aggregation.md](01_signal_aggregation.md) | H1 + H2 dual-engine aggregation |
| [02_live_configuration.md](02_live_configuration.md) | Current live state |
| [../overlays/portfolio_construction/01_sizing_schemes.md](../overlays/portfolio_construction/01_sizing_schemes.md) | Portfolio sizing test results |
| [../overlays/portfolio_construction/02_regime_allocation.md](../overlays/portfolio_construction/02_regime_allocation.md) | Regime allocation ladder |
| [../H1_reversal/00_mechanism.md](../H1_reversal/00_mechanism.md) | H1 signal mechanism |
| [../H2_transitional_drift/00_mechanism.md](../H2_transitional_drift/00_mechanism.md) | H2 signal mechanism |
