# Vector Tests — Steps 3C, 4A, 4B, 5

**Run:** 2026-03-17 06:18 UTC
**Period:** Oct 2024 – Jan 2025 (trending period)
**Hold horizon:** 4h | Top-N: 3 | Equal weight

## Part A — Step 3C: Bare Signal Vector

Fixed-horizon hold, no C2/C3 modifiers.

| Metric | Value | Sanity Bar | Result |
|--------|-------|------------|--------|
| Gross Sharpe (ann) | 1.872 | > 0 | PASS |
| Max Drawdown | −34.09% | >= −40% | PASS |
| Period Hit Rate | 51.50% | > 50% | PASS |
| Total Return (4m) | 59.42% | — | — |
| Mean IC@4h | 0.0477 | — | — |
| N periods | 732 | — | — |

**Step 3C verdict: PASS — proceed to modifier screens**

## Part B — Step 4A: C2 Regime Modifier Screen

C2 gate: BTC realized-vol z-score (48h) > 1.5 → skip all new entries (hold cash).

| Metric | Bare C1 | + C2 gate | Improvement | Bar | Result |
|--------|---------|-----------|-------------|-----|--------|
| Max Drawdown | −34.09% | −28.00% | 17.84% | >= 10% | PASS |
| Worst 30d DD | −19.82% | −10.69% | 9.13% | >= 5pp | PASS |
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

IC uplift (fresh vs unconditional): −0.0298 (−2.98%)

**Step 4B verdict: REJECTED — fresh signals do not outperform unconditional IC**

## Part D — Step 5: Full Signal Vector (Sequential Improvement)

| Configuration | Sharpe | MaxDD | Hit Rate | Total Return | IC@4h |
|---------------|--------|-------|----------|--------------|-------|
| Bare C1 | 1.872 | −34.09% | 51.50% | 59.42% | 0.0477 |
| + C2 regime gate | 3.015 | −28.00% | 47.13% | 119.05% | 0.0477 |
| + C2 + C3 | 3.160 | −27.00% | 46.99% | 130.05% | 0.0477 |

Monotone Sharpe improvement: 1.87 → 3.02 → 3.16

## Summary

| Step | Test | Result |
|------|------|--------|
| 3C | Bare signal sanity bars | PASS |
| 4A | C2 regime modifier approved | PASS |
| 4B | C3 maturity modifier (pct_rank proxy) | FAIL |
| 5  | Full signal vector produces best Sharpe | PASS |

---

## Interpretation

### Step 3C — Bare signal is real

Gross Sharpe 1.87, MaxDD −34%, hit rate 51.5% over 732 independent 4h periods confirms
the promoted signal (0.70×H1_reversal + 0.30×H5_low_vol) has positive expected value
on its own. The MaxDD of −34% is below the −40% sanity bar but not comfortable — it
underscores why C2 is needed.

### Step 4A — C2 regime gate is the primary risk control

Adding the BTC vol z-score hazard gate (threshold z > 1.5) produces the largest single
improvement: MaxDD shrinks from −34% to −28% (−18% relative), worst 30d DD halves from
−19.8% to −10.7%, and Sharpe nearly doubles (1.87 → 3.01). Total return also doubles
because the strategy is not holding positions through volatile drawdown periods.

**Mechanism:** BTC vol spikes precede broad altcoin drawdowns. Exiting to cash when
BTC z-vol > 1.5 avoids precisely the periods where mean-reversion briefly fails and
sustained sell-offs occur. This is direct empirical confirmation of the regime filter's
economic rationale.

### Step 4B — C3 maturity proxy fails IC gate in trending conditions

IC(fresh, pct_rank<30%) = 0.018 vs IC(unconditional) = 0.048. Stale signals
(pct_rank > 70%) have the **highest** IC at 0.052.

**Why this happens:** In the Oct–Jan 2024 trending bull run, assets that had already
extended their moves continued outperforming. The pct_rank proxy mislabels "already
moved a lot" as stale, but these are precisely the assets with the most regime-consistent
continuation. The proxy correctly rejects them by IC gate.

**Why the backtest still improves marginally with C3 (+0.15 Sharpe, −1pp MaxDD):**
Filtering out high-pct_rank (stale) assets also removes the highest realized-vol assets.
Even with lower mean IC, the portfolio vol reduction mechanically lifts Sharpe. This is
a risk-reduction effect, not an alpha effect.

**Decision on C3 for live bot:** The live M_t in `maturity.py` uses a multi-component
composite (SMA extension, RSI proxy, pct_rank, funding rate). The pct_rank alone fails
the IC gate. The funding rate and SMA extension components are retained on economic grounds.
See [../../overlays/maturity/03_decision.md](../../overlays/maturity/03_decision.md).

*Equity curves: see `research/charts/06_vector_tests/equity_curves.png`*
*Drawdown profile: see `research/charts/06_vector_tests/drawdown.png`*
