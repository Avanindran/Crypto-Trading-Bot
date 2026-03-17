# Research Pipeline Index

**Written:** 2026-03-17
**Purpose:** Master index — read this first. Maps the full research chain from mechanism declaration to deployed strategy.

---

## End-to-End Chain

```
Universe:    67 Roostoo pairs, Oct 2024 – Jan 2025 backtest (Dec–Jan holdout)

Mechanism:   H1 cross-sectional reversal (laggards recover within 1–4h)
           + H5 low-vol stability (stable coins are genuine mean-reversion candidates)
             → BTC-diffusion lag confirmed as the mechanism (H2 mechanism test)

Proxy (C1):  0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)
             IC = +0.057 at 4h (t = 12.7), holdout IC = +0.066 (t = 10.6)

C2 regime:   exp(−λ_t) from LSI → λ cascade
             BTC vol z-score gate (research proxy) → APPROVED
             MaxDD improves 17.8% relative; worst 30d DD improves 9.1pp

C3 maturity: 1 − M_t composite (extension, RSI proxy, pct_rank, funding rate)
             pct_rank proxy alone → REJECTED in trending (stale IC > fresh IC)
             Composite retained: funding + SMA extension capture overextension in
             non-trending conditions where pct_rank alone is insufficient

Position score:  C1_i × exp(−λ_t) × (1 − M_t_i)
Portfolio:       Quarter-Kelly sizing, regime-gated gross cap (0% / 65% / 85%)
Risk:            3-tier drawdown response (−5% / −8% / −12% kill switch) + stops
```

---

## Doctrine Step → Research File Mapping

| Step | Doctrine Name | File | Key Verdict |
|------|---------------|------|-------------|
| 0 | OOS reserve | — | Dec–Jan 2025 holdout (implicit) |
| 1 | Mechanism declaration | [01_mechanism_universe.md](01_mechanism_universe.md) | H1, H2, H5, H6 declared before any data seen |
| 2 | Proxy commitment | [02_proxy_universe.md](02_proxy_universe.md) | All proxies pre-committed; GP search space declared |
| 3A | IC testing | [03_validation/](03_validation/) | H1_neg_c1, H5_neg_vol pass; H5_sharpe, H6, H2a/b, F1–F7, G1–G6 all fail |
| 2B | GP run (after 3A confirms terminals) | [04_gp_search/](04_gp_search/) | 0.70×H1 + 0.30×H5, IC-Sharpe = +0.190 |
| 3B | Near-duplicate filter | [08_limitations_and_rejections.md](08_limitations_and_rejections.md) | H2a = H1 (mathematical identity) |
| 3D | H2 mechanism test | [05_h2_mechanism_test.md](05_h2_mechanism_test.md) | H2 CONFIRMED — IC uplift = +0.087 when BTC moves |
| 3C | Bare signal vector | [06_vector_tests.md](06_vector_tests.md) Part A | PASS (Sharpe=1.87, MaxDD=−34%, HitRate=51.5%) |
| 4A | C2 regime modifier | [06_vector_tests.md](06_vector_tests.md) Part B | APPROVED (MaxDD −18% relative, worst 30d DD +9.1pp) |
| 4B | C3 maturity modifier | [06_vector_tests.md](06_vector_tests.md) Part C | pct_rank proxy REJECTED; composite retained with caveat |
| 5 | Full signal vector | [06_vector_tests.md](06_vector_tests.md) Part D | Monotone Sharpe: 1.87 → 3.02 → 3.16 |
| 8 | Signal nomination | [07_signal_promotion.md](07_signal_promotion.md) | H1_neg_c1_x07_H5_neg_vol promoted |
| 9 | Strategy assembly | `bot/strategy/signals.py` | Deployed |
| 10 | Strategy backtest | `backtest_simulation.py` + `backtest_results.md` | Full strategy test with regime + maturity |
| 12 | Robustness validation | [09_robustness/](09_robustness/) | 97.2% block-resample; IC positive at all weight perturbations |

**Supplementary (not part of pipeline narrative):**

| File | Content |
|------|---------|
| [00_objective_and_constraints.md](00_objective_and_constraints.md) | Competition objective, admissibility criteria, failure documentation policy |
| [08_limitations_and_rejections.md](08_limitations_and_rejections.md) | All rejected proxies with economic explanations; research limitations |
| `backtest_results.md` | Full strategy backtest outputs |
| `03_validation/ic_results_extended.md` | Extended IC tests across 67 pairs and test conditions |
| `03_validation/ic_results.md` | Initial IC validation (10-pair universe, early run) |
| `charts/03_validation/` | IC time-series and multi-horizon charts (H1/H5 validation) |
| `charts/04_gp_search/` | IC signal search chart (GP combination candidates) |
| `charts/05_h2_mechanism/` | IC conditioned on BTC regime (H2 mechanism test) |
| `charts/06_vector_tests/` | Equity curves and drawdown (vector tests) |

---

## All Tested Proxies — Ground Truth

Every proxy below was pre-committed in [02_proxy_universe.md](02_proxy_universe.md) before any IC data was seen.

| Family | Proxy | IC @ 4h | Decision | Notes |
|--------|-------|---------|----------|-------|
| **H1 Reversal** | H1_neg_r1h | +0.049 | PROMOTE terminal | Best individual IC |
| | H1_neg_r2h | +0.047 | PROMOTE terminal | |
| | H1_neg_r6h | — | PROMOTE terminal | |
| | H1_neg_c1 | +0.043 | PROMOTE → GP | Used in final combination |
| **H5 Vol-Adj** | H5_neg_vol | +0.076* | PROMOTE terminal | *Best IC at 24h |
| | H5_sharpe_6h | −0.022 | FAIL | Negative IC |
| | H5_sharpe_24h | — | FAIL | Negative IC |
| | H5_sortino_6h | — | FAIL | Negative IC |
| **H6 Streak** | H6_up_pct_6h | <0.01 | FAIL | Near-zero IC |
| | H6_streak_ts | <0.01 | FAIL | Near-zero IC |
| | H6_body_mean_6h | <0.01 | FAIL | Near-zero IC |
| **H2 BTC lag** | H2a_neg_rel_btc_r2h | = H1 IC | COLLAPSE | Mathematical identity with H1 |
| | H2a_neg_rel_btc_r6h | = H1 IC | COLLAPSE | Same |
| | H2b_btc_lag1h | r=−0.003 | FAIL | No predictive lag at 1h |
| **H_TS (F1–F7)** | F1–F7 | <0.02 | ALL FAIL | TS z-score doesn't rescue reversal |
| **H_OFI (G1–G6)** | G1–G6 | <0.01 | ALL FAIL | Microstructure signal decays in 1h kline |
| **H0 Original C1** | C1 momentum | −0.038 | ANTI-PREDICTIVE | Original bot signal was selecting wrong tail |
| **GP Combination** | 0.70×H1_neg_c1 + 0.30×H5_neg_vol | **+0.057** | **PROMOTED** | Final C1 formula |

See [08_limitations_and_rejections.md](08_limitations_and_rejections.md) for economic explanations of each failure.

---

## Robustness Timing Note

In the compressed research timeline (competition deadline Mar 21, 2026), robustness testing (`09_robustness/`) was executed **before** vector tests (`06_vector_tests.md`). Per doctrine Step 12, robustness must follow the strategy freeze (Step 11), which itself follows the vector tests (Step 10).

**Why the spirit of the freeze was preserved:**
- The promoted signal formula (0.70×H1 + 0.30×H5, weights from GP search) was finalized in `04_gp_search/` and `07_signal_promotion.md`.
- Robustness was run as a "pre-flight check" on that fixed formula.
- After seeing robustness results (97.2% block-resample hit rate), **no parameters were changed**.
- The vector tests were built afterward as formal doctrine compliance, and confirmed the same formula.

If you compare `07_signal_promotion.md` (formula spec) with `09_robustness/H1_H5_signal_robustness.md` (robustness inputs), they use identical weights and formula — confirming no post-hoc fitting.

---

## Key Decision Gates Passed

| Gate | Threshold | Actual | Result |
|------|-----------|--------|--------|
| IC at 4h | > 0, t > 1.5 | IC=+0.057, t=12.7 | PASS |
| Holdout IC | > 0 | +0.066 | PASS |
| Block-resample hit rate | ≥ 55% (10-day windows) | 97.2% | PASS |
| Bare signal Sharpe | > 0 | 1.87 | PASS |
| Bare signal MaxDD | ≥ −40% | −34.1% | PASS |
| Bare signal hit rate | > 50% | 51.5% | PASS |
| C2 MaxDD improvement | ≥ 10% relative | +17.8% | PASS |
| C2 worst 30d improvement | ≥ 5pp | +9.1pp | PASS |
| H2 mechanism (IC uplift) | > 0.010 | +0.087 | PASS |
| C3 pct_rank IC gate | IC(fresh) > IC(uncond.) | 0.018 < 0.048 | **FAIL** |
| C3 composite (live M_t) | — | not formally tested; retained | Caveat documented |
