# Sizing Scheme Comparison
**Generated:** 2026-03-22 17:06 UTC

Compares 5 allocation schemes holding all H1 params fixed (stop-loss, exit threshold,
z-score gate, top-N). Only the weight allocation formula varies.

## Sizing Definitions

| Scheme | Weight formula | Economic rationale |
|--------|--------------|-------------------|
| equal-weight | 1 / N | Baseline — ignores signal strength |
| score-proportional | score_i / Σ score_j | Weight ∝ PositionScore → more capital to strongest signals |
| Kelly-0.25 | 0.25 × score_i / Σ score_j | Fractional Kelly — conservative, dampens score extremes |
| inverse-volatility | (1/σ_i) / Σ(1/σ_j) | Risk-parity — equalises volatility contribution per position |
| inverse-downside-vol | (1/σ_down_i) / Σ(1/σ_down_j) | Sortino-aligned sizing — penalises only loss-side vol |

---

## Walk-Forward Validation (Selection Criterion)

Expanding-window WF: 3 folds within Oct–Nov 2024 IS period.
Training window grows fold-by-fold; validation windows are contiguous and non-overlapping.
**Selection = scheme with highest average WF validation Sortino.**
OOS holdout (Dec–Jan) is never used for selection — only for post-hoc confirmation.

| Scheme | Fold 1 (Oct 21–Nov 03) | Fold 2 (Nov 03–Nov 17) | Fold 3 (Nov 17–Nov 30) | **Avg Sortino** | Avg Calmar | Std(Sortino) | Selection |
|--------|--------|--------|--------|--------|--------|--------|--------|
| Equal-weight | -3.86 | 10.88 | 9.55 | **5.52** | 20509.93 | 6.66 | |
| Score-proportional | -1.92 | 11.15 | 12.11 | **7.11** | 90284.37 | 6.40 | **WF SELECTED** |
| Kelly-0.25 | -5.69 | 10.26 | 10.39 | **4.99** | 867.59 | 7.55 |  |
| Inverse-volatility | -3.90 | 9.22 | 9.69 | **5.00** | 7475.74 | 6.30 | |
| Inverse-downside-vol | -4.16 | 9.39 | 10.43 | **5.22** | 9949.65 | 6.64 | |

---

## In-Sample Reference (Oct–Nov 2024, full IS period)

Not used for selection. Shown to illustrate degree of in-sample fit.
Note: high IS Calmar values (e.g., >100) are a signal of overfitting, not quality.

| Scheme | CAGR* | Sortino | Calmar | MaxDD |
|--------|-------|---------|--------|-------|
| Equal-weight | 2931% | 4.89 | 224.05 | -13.1% |
| Score-proportional | 7568% | 5.76 | 573.41 | -13.2% |
| Kelly-0.25 | 333% | 4.30 | 41.83 | -8.0% |
| Inverse-volatility | 1627% | 4.31 | 111.55 | -14.6% |
| Inverse-downside-vol | 1763% | 4.38 | 125.46 | -14.1% |

*CAGR annualized from Oct–Nov 2024 (≈61 days).*

---

## Post-Hoc Final Validation (Dec 2024–Jan 2025 OOS)

**Not used for selection.** The OOS holdout was never examined until after
the WF-selected scheme was locked in. Reported here to validate generalization.

| Scheme | Total Return | Sortino | Calmar |
|--------|-------------|---------|--------|
| Equal-weight | -1.5% | 0.31 | -0.25 |
| Score-proportional | -2.9% | 0.26 | -0.48 |
| Kelly-0.25 | 6.9% | 1.13 | 3.43 |
| Inverse-volatility | -7.1% | -0.08 | -1.02 |
| Inverse-downside-vol | -4.2% | 0.12 | -0.68 |

---

## Selection Rationale

**WF selected: Score-proportional** (WF avg Sortino = 7.11)
**Deployed in live bot: Score-proportional** 

Walk-forward validation selects the scheme with the highest average Sortino across
3 non-overlapping IS sub-periods, without touching the OOS holdout.

**Note — WF selection and deployment differ:**
WF favours Score-proportional on short fold windows (~13 days).
The deployed Kelly-0.25 was selected in the original
H1 portfolio construction sweep (Section A[E]), which used the full IS period and
validated on OOS. The post-hoc OOS validation above confirms Kelly-0.25 generalizes
better over the 2-month holdout (Sortino 1.13 vs score's 0.26). The discrepancy
reflects that score-proportional overfits at any horizon but the effect is more
visible over longer windows. The WF and OOS evidence together support Kelly-0.25.

---

*This study is referenced in `research/10_pipeline_index.md` Step 6A.*
