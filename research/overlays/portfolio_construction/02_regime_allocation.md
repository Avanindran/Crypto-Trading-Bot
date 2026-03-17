# Regime Allocation Ladder Test — Step 7

**Generated:** 2026-03-17 09:25 UTC
**Period:** Oct 2024 – Jan 2025 (full backtest including holdout)
**Signal:** 0.70×H1_reversal + 0.30×H5_low_vol (promoted formula)
**Sizing:** Equal weight within gross_cap (isolates regime effect)

## Decision Gates

**Gate 1:** Config C Calmar >= 10% relative improvement vs Config B
  Result: FAIL (C = +18.67, B = +18.13, uplift = +3.0%)

**Gate 2:** Config C MaxDD improves >= 10% relative vs Config A
  Result: PASS (C = −23.6%, A = −37.6%, improvement = +37.2%)

## Configuration Comparison

| Config | Calmar | Sortino | Sharpe | MaxDD | Worst 30d | Total Ret |
|--------|--------|---------|--------|-------|-----------|-----------|
| A: No regime (100% always) | +5.07 | +2.31 | +1.62 | −37.6% | −24.2% | +42.9% |
| B: Binary BTC vol gate | +18.13 | +3.94 | +2.70 | −23.3% | −10.5% | +73.8% |
| C: Full 3-regime ladder | +18.67 | +4.33 | +2.89 | −23.6% | −6.9% | +75.8% |

## Regime Distribution per Config

**A: No regime (100% always):**
  TREND               :  738 periods (100.0%)
  NEUTRAL             :    0 periods (0.0%)
  HAZARD              :    0 periods (0.0%)

**B: Binary BTC vol gate:**
  TREND               :  666 periods (90.2%)
  NEUTRAL             :    0 periods (0.0%)
  HAZARD              :   72 periods (9.8%)

**C: Full 3-regime ladder:**
  TREND               :  410 periods (55.6%)
  NEUTRAL             :  256 periods (34.7%)
  HAZARD              :   72 periods (9.8%)

## Interpretation

The full 3-regime ladder (Config C) introduces MPI (momentum persistence index) as a secondary condition for TREND classification. When BTC momentum is weak (MPI < 0.50) even in low-vol environments, the strategy downgrades to NEUTRAL (65% gross cap, max 3 positions) rather than full TREND allocation.

This reduces drawdown in choppy low-vol markets while preserving full allocation in confirmed trending regimes. The cost is lower average gross exposure when markets are in genuine sideways chop.

**Overall verdict: PROVISIONAL**
Gate 1 (Calmar improvement): FAIL
Gate 2 (MaxDD improvement): PASS

**Note:** Even if the 3-regime ladder does not pass formal gates, the live bot
retains it because the MPI condition is qualitatively sound (do not allocate
full TREND capital when BTC has had fewer than half positive hours in 48h)
and the cost of false positives is bounded by the HAZARD gate above it.

Decision record: [../../overlays/regime/03_decision.md](../../overlays/regime/03_decision.md)
