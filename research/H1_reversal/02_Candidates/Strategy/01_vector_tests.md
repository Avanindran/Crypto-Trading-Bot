# Vector Tests — Steps 3C, 4A, 4B, 5

**Run:** 2026-03-17 14:48 UTC  
**Period:** Oct 2024 – Jan 2025 (trending period)  
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Part A — Step 3C: Bare Signal Vector

Fixed-horizon hold, no C2/C3 modifiers.

| Metric | Value | Sanity Bar | Result |
|--------|-------|------------|--------|
| Gross Sharpe (ann) | 1.872 | > 0 | PASS |
| Max Drawdown | -34.09% | ≥ −40% | PASS |
| Period Hit Rate | 51.50% | > 50% | PASS |
| Total Return (4m) | 59.42% | — | — |
| Mean IC@4h | 0.0477 | — | — |
| N periods | 732 | — | — |

**Step 3C verdict: PASS — proceed to modifier screens**

## Part B — Step 4A: C2 Regime Modifier Screen

C2 gate: BTC realized-vol z-score (48h) > 1.5 → skip all new entries (hold cash).

| Metric | Bare C1 | + C2 gate | Improvement | Bar | Result |
|--------|---------|-----------|-------------|-----|--------|
| Max Drawdown | -34.09% | -28.00% | 17.84% | ≥ 10% | PASS |
| Worst 30d DD | -19.82% | -10.69% | 9.13% | ≥ 5pp | PASS |
| Sharpe (ann) | 1.872 | 3.015 | — | — | — |
| Total Return | 59.42% | 119.05% | — | — | — |

**Step 4A verdict: APPROVED — C2 clears both improvement gates**

## Part C — Step 4B: C3 Maturity Modifier Screen

Maturity proxy: pct_rank of r_6h in 48h rolling history.  
Gate: IC(fresh, pct_rank < 30%) > IC(unconditional).

| Maturity Bucket | Mean IC | t-stat | N |
|-----------------|---------|--------|---|
| Fresh | 0.0179 | 1.03 | 410 |
| Mid | 0.0302 | 2.33 | 611 |
| Stale | 0.0525 | 3.03 | 482 |
| Unconditional | 0.0477 | 5.16 | 731 |

IC uplift (fresh vs unconditional): -0.0298 (-2.98%)

**Step 4B verdict: REJECTED — fresh signals do not outperform unconditional IC**

## Part D — Step 5: Full Signal Vector (Sequential Improvement)

| Configuration | Sharpe | MaxDD | Hit Rate | Total Return | IC@4h |
|---------------|--------|-------|----------|--------------|-------|
| Bare C1 | 1.872 | -34.09% | 51.50% | 59.42% | 0.0477 |
| + C2 regime gate | 3.015 | -28.00% | 47.13% | 119.05% | 0.0477 |
| + C2 + C3 | 3.160 | -27.00% | 46.99% | 130.05% | 0.0477 |

## Summary

| Step | Test | Result |
|------|------|--------|
| 3C | Bare signal sanity bars | PASS |
| 4A | C2 regime modifier approved | PASS |
| 4B | C3 maturity modifier approved | FAIL |
| 5  | Full signal vector produces best Sharpe | PASS |

**Overall: ONE OR MORE STEPS FAILED — review individual sections above**

*Equity curves: see `research/H1_reversal/02_Candidates/Strategy/charts/vector_tests/equity_curves.png`*
