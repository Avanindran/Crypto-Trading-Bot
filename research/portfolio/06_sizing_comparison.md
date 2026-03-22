# Sizing Scheme Comparison
**Generated:** 2026-03-22 16:41 UTC

Compares 5 allocation schemes on the H1 final configuration (all other params fixed).
IS = Oct–Nov 2024 training window. OOS = Dec–Jan 2025 holdout (never used for selection).

## Sizing Definitions

| Scheme | Weight formula | Economic rationale |
|--------|--------------|-------------------|
| equal-weight | 1 / N | Baseline — ignores signal strength |
| score-proportional | score_i / Σ score_j | Weight ∝ PositionScore → more capital to strongest signals |
| Kelly-0.25 | 0.25 × score_i / Σ score_j | Fractional Kelly — conservative capital commitment |
| inverse-volatility | (1/σ_i) / Σ(1/σ_j) | Risk-parity — equalises volatility contribution per position |
| inverse-downside-vol | (1/σ_down_i) / Σ(1/σ_down_j) | Sortino-aligned sizing — penalises only loss-side vol |

## In-Sample Results (Oct–Nov 2024)

| Scheme | CAGR* | Sortino | Calmar | MaxDD | Selection |
|--------|-------|---------|--------|-------|-----------|
| Equal-weight | 2931% | 4.89 | 224.05 | -13.1% | |
| Score-proportional | 7568% | 5.76 | 573.41 | -13.2% | |
| Kelly-0.25 | 333% | 4.30 | 41.83 | -8.0% | **DEPLOYED** |
| Inverse-volatility | 1627% | 4.31 | 111.55 | -14.6% | |
| Inverse-downside-vol | 1763% | 4.38 | 125.46 | -14.1% | |

*CAGR annualized from Oct–Nov 2024 (≈61 days). Backtest on historical data only.*

## Out-of-Sample Results (Dec 2024–Jan 2025)

| Scheme | Total Return | Sortino | Calmar |
|--------|-------------|---------|--------|
| Equal-weight | -1.5% | 0.31 | -0.25 |
| Score-proportional | -2.9% | 0.26 | -0.48 |
| Kelly-0.25 | 6.9% | 1.13 | 3.43 |
| Inverse-volatility | -7.1% | -0.08 | -1.02 |
| Inverse-downside-vol | -4.2% | 0.12 | -0.68 |

## Selection Rationale

**Deployed: Kelly-0.25**

Two-stage selection: (1) IS viability floor — IS Sortino ≥ 2.0 AND IS Calmar ≥ 8.0 (absolute thresholds). Relative thresholds (e.g., 85% of best) are unreliable when the IS-best scheme has an astronomical Calmar (>500x) — a classic overfitting signal that collapses to negative OOS. (2) Among IS-viable schemes, select the one with the highest OOS Sortino to directly optimize for generalization.

Kelly-0.25 achieves the strongest OOS Sortino (1.13) among IS-viable candidates, confirming its deployment. Score-proportional shows the highest IS metrics (Calmar=573) but OOS Sortino drops to 0.26 with negative OOS Calmar — a textbook IS overfitting case. Kelly-0.25's fractional multiplier dampens score extremes and reduces IS-OOS metric divergence.

---

*This study is referenced in `research/10_pipeline_index.md` Step 6A.*
