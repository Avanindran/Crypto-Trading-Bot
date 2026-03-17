# Regime Overlay — Decision Record

**Date:** 2026-03-17
**Decision:** APPROVED
**Status:** Live in `bot/strategy/regime.py`

---

## Validation Gates

### Gate 1 — C2 MaxDD improvement (PASS)

Comparing bare signal (no regime gate) vs binary BTC vol z-score gate (LSI > threshold → skip entries):

| Config | MaxDD | Worst 30d DD | Sharpe |
|--------|-------|-------------|--------|
| No regime | −34.1% | −19.8% | 1.87 |
| Binary BTC vol gate | −28.0% | −10.7% | 3.02 |
| **Improvement** | **+17.8% relative** | **+9.1pp** | **+61%** |

Gate threshold: MaxDD improvement ≥ 10% relative.
**Result: PASS (17.8% ≥ 10%)**

Gate threshold: Worst 30d DD improvement ≥ 5pp.
**Result: PASS (+9.1pp ≥ 5pp)**

### Gate 2 — Robustness to LSI threshold perturbation

LSI threshold varied from 0.50 to 0.70:

| LSI Threshold | Time Defensive |
|---------------|---------------|
| 0.50 | 42.0% |
| 0.55 | 35.5% |
| **0.60** | **30.1% (PRODUCTION)** |
| 0.65 | 25.9% |
| 0.70 | 22.0% |

Gate: Regime filter qualitatively correct at all threshold values (no threshold where defense is worse than no defense).
**Result: PASS — robust across {0.50, 0.55, 0.60, 0.65, 0.70}**

Full robustness results: [02_results.md](02_results.md).

---

## Full 3-Regime Ladder vs Binary Gate

Adding MPI condition (TREND_SUPPORTIVE only when MPI > 0.50) on top of the binary gate:

| Config | Calmar | Sortino | MaxDD | Total Return |
|--------|--------|---------|-------|-------------|
| A: No regime | +5.07 | +2.31 | −37.6% | +42.9% |
| B: Binary BTC vol gate | +18.13 | +3.94 | −23.3% | +73.8% |
| C: Full 3-regime ladder | +18.67 | +4.33 | −23.6% | +75.8% |

Gate 1 (Calmar improvement C vs B): +3.0% (requirement: ≥ 10%) → **FAIL**
Gate 2 (MaxDD improvement C vs A): +37.2% (requirement: ≥ 10% relative) → **PASS**

**Overall verdict: PROVISIONAL**

The 3-regime ladder passes Gate 2 but fails Gate 1. It is retained in the live bot because:
1. Sortino improvement of +10% (3.94 → 4.33) favours retention
2. The MPI condition is qualitatively sound: do not allocate full TREND capital when BTC has had fewer than half positive hours in 48h
3. The cost of the Gate 1 failure is bounded by the HAZARD gate above it — even if MPI misclassifies, the LSI path provides the floor protection

Full regime allocation test: [../../overlays/portfolio_construction/02_regime_allocation.md](../../overlays/portfolio_construction/02_regime_allocation.md).

---

## Implementation Notes

- **Primary driver:** LSI (Liquidity Stress Index) dominates all regime decisions
- **Secondary driver:** MPI conditions TREND_SUPPORTIVE classification
- **Emergency protection:** `bot/risk/kill_switch.py` provides BTC-gate (−3% → block entries, −6% → emergency exit) as a faster-responding supplement to the LSI-based regime
- **Position scaling:** `exp(−λ_t)` applied multiplicatively in `bot/strategy/ranking.py:compute_position_scores()`

---

## Navigation

| File | Content |
|------|---------|
| [00_mechanism.md](00_mechanism.md) | λ_t as hazard rate, mechanism theory |
| [01_proxy_universe.md](01_proxy_universe.md) | LSI/MPI/FEI component specs |
| [02_results.md](02_results.md) | Threshold robustness test results |
| [../../overlays/portfolio_construction/02_regime_allocation.md](../../overlays/portfolio_construction/02_regime_allocation.md) | Full 3-regime ladder test |
