# GP Search Space — H1 Reversal + H5 Low-Vol

**Written:** 2026-03-17 | **Status:** FROZEN before gp_search.py first run

No combination test results have been observed at time of writing.
Search space declared from IC validation results and mechanism reasoning.

---

## Passing Signals Summary (from 03_validation/)

| Signal | Best IC | Best Horizon | t-stat | Gate |
|--------|---------|-------------|--------|------|
| `H1_neg_r1h` | +0.049 | 1h | +10.75 | PROMOTE |
| `H1_neg_r2h` | +0.047 | 1h | +10.33 | PROMOTE |
| `H1_neg_c1`  | +0.043 | 1h | +9.36  | PROMOTE |
| `H5_neg_vol` | +0.076 | 24h | +13.26 | PROMOTE |

## Key Structural Finding

**H2a is mathematically equivalent to H1** in a cross-sectional framework.
`CS_z(btc_r_Xh - alt_r_Xh) = CS_z(-alt_r_Xh)` because `btc_r_Xh` is a
cross-sectional constant that cancels in z-normalization. H2a provides no
independent signal beyond H1.

## Terminal Set (declared before combination testing)

| Terminal | Source | Mechanism |
|----------|--------|-----------|
| `H1_neg_r1h` | CS_z(-r_1h) | 1h reversal: recent 1h losers recover |
| `H1_neg_r2h` | CS_z(-r_2h) | 2h reversal: flatter decay, more stable |
| `H1_neg_c1`  | CS_z(-C1_raw) | Inverse of current bot signal; broad reversal |
| `H5_neg_vol` | CS_z(-realized_vol_6h) | Low-vol anomaly: stable coins outperform |

Note: `H1_neg_r6h` excluded from GP terminals — nearly collinear with H1_neg_r2h.

## Operator Set (declared before combination testing)

| Operator | Form | Notes |
|----------|------|-------|
| Linear blend | `w * T1 + (1-w) * T2` | w in {0.0, 0.1, ..., 1.0}, w1+w2=1 |

Depth limit: 1 (linear combination of 2 terminals only).
Complexity ceiling: 2 terminals, 1 operator.

## Test Pairs (all pairwise combinations of terminals)

1. `H1_neg_r1h + H5_neg_vol`  — reversal (1h) + stability (24h)
2. `H1_neg_r2h + H5_neg_vol`  — reversal (2h) + stability (24h)
3. `H1_neg_c1  + H5_neg_vol`  — composite reversal + stability
4. `H1_neg_r1h + H1_neg_r2h` — two reversal horizons combined
5. `H1_neg_r1h + H1_neg_c1`  — single + composite reversal
6. `H1_neg_r2h + H1_neg_c1`  — two composite-based reversal signals

## Objective Function

**Primary:** IC Sharpe = mean_IC / std_IC at the 4h forward horizon (matches
competition REBALANCE_HOURS and M_t maturity filter window).

**Secondary:** IC decay profile — does the combo outperform both terminals
at the 4h horizon?

## Selection Criteria (before testing)

A combination is selected over individual terminals only if:
1. IC Sharpe at 4h is > best individual terminal IC Sharpe at 4h
2. Mean IC at 4h is > IC_PROMOTE_MIN (0.03)
3. IC is positive at both the 2h and 6h horizons (not a one-horizon artifact)
4. Formula is statable in one sentence referencing both mechanisms

## Expected Outcome (declared before testing)

`H1_neg_r2h + H5_neg_vol` combination hypothesis:
- At 1-2h: dominated by H1_neg_r2h (reversal faster component)
- At 4-6h: transition zone, combo may outperform either alone
- At 12-24h: dominated by H5_neg_vol (quality, persistent)
- Expected: combo IC at 4h ≥ max(H1_neg_r2h at 4h, H5_neg_vol at 4h)
  because signals are mechanistically independent (low correlation)

If neither pair combination outperforms both individual terminals at 4h,
promote the better individual terminal (expected: H5_neg_vol at 4h ≥ H1).

## Holdout

Inner training: Oct 2024 – Nov 2024 (first 2 months of trending period).
Holdout: Dec 2024 – Jan 2025 (last 2 months).
A combination must show IC > 0 on holdout to be promoted.

## Interpretability Gate

Selected formula must be statable in one sentence:
- PASS example: "Buy stable low-volatility coins that have recently underperformed the cross-section."
- FAIL example: arbitrary 5-term weighted sum with no economic rationale.
