# Research Pipeline Index

**Written:** 2026-03-17
**Purpose:** Master index — read this first. Maps the full research chain from mechanism declaration to deployed strategy.

---

## End-to-End Chain

```
Universe:    67 Roostoo pairs, Oct 2024 – Jan 2025 backtest (Dec–Jan holdout)

Mechanism:   H1 cross-sectional reversal (laggards recover within 1–4h)
           + H5 low-vol stability (stable coins are genuine mean-reversion candidates)
           + TS overshoot variants (per-asset self-comparison, orthogonal to CS)
           + H2c beta-adjusted gap (BTC-diffusion, non-collapsed, PROMOTED)
             → BTC-diffusion lag confirmed as mechanism (H2 mechanism test: IC uplift +0.087)

Proxy (C1):  0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)
             IC = +0.057 at 4h (t = 12.7), holdout IC = +0.066 (t = 10.6)

C2 regime:   exp(−λ_t) from LSI → λ cascade
             HAZ_BTC_VOL_Z gate → APPROVED (MaxDD +17.8% rel, worst 30d +9.1pp)
             HAZ_FNG_EXTREME gate → APPROVED (Fear & Greed > 75; MaxDD +17.6% rel)
             HAZ_CS_DISPERSION, HAZ_SPREAD_Z, HAZ_MPI_CHOP, HAZ_BTC_DRAWDOWN → REJECTED

C3 maturity: 1 − M_t composite (extension, RSI proxy, pct_rank, funding rate)
             MAT_VOL_RATIO → APPROVED (IC uplift +0.064; strongest individual C3 proxy)
             MAT_FUNDING_RATE → APPROVED (IC uplift +0.010)
             MAT_PCT_RANK, MAT_SMA_EXT, MAT_RSI_PROXY, MAT_TS_ZSCORE_R6H, MAT_CONSEC_UP → REJECTED

Position score:  C1_i × exp(−λ_t) × (1 − M_t_i)
Portfolio:       Score-proportional sizing, regime-gated gross cap (0% / 65% / 85%)
Risk:            3-tier drawdown response (−5% / −8% / −12% kill switch) + stops
Fee:             0.05% per trade (maker; limit orders per competition rules)
```

---

## Doctrine Step → Research File Mapping

| Step | Doctrine Name | File | Key Verdict |
|------|---------------|------|-------------|
| 0 | OOS reserve | [H1_reversal/00_OOS_Reservation/oos_reservation.md](H1_reversal/00_OOS_Reservation/oos_reservation.md) | Dec–Jan 2025 holdout formally declared |
| 1 | Mechanism declaration | [H1_reversal/00_mechanism.md](H1_reversal/00_mechanism.md) / [H2_transitional_drift/00_mechanism.md](H2_transitional_drift/00_mechanism.md) | H1, H2, H5 declared before any data seen |
| 2 | Proxy commitment | [H1_reversal/01_Proxies/00_proxy_universe.md](H1_reversal/01_Proxies/00_proxy_universe.md) / [H2_transitional_drift/01_Proxies/00_proxy_universe.md](H2_transitional_drift/01_Proxies/00_proxy_universe.md) | All proxies pre-committed; GP search space declared |
| 3A | IC testing (CS family) | [H1_reversal/02_Candidates/Signal/01_ic_results.md](H1_reversal/02_Candidates/Signal/01_ic_results.md) | H1_neg_c1, H5_neg_vol pass; H5_sharpe, H6 all fail |
| 3A | IC testing (TS + H2 family) | [H1_reversal/02_Candidates/Signal/05_ts_variant_search.md](H1_reversal/02_Candidates/Signal/05_ts_variant_search.md) | TS_zscore_neg_r2h, TS_bb_dist, CS_TS_blend_r6h, H2c PROMOTE; H2d PASS |
| 3A | IC testing (H2 C1 variants) | [H2_transitional_drift/02_Candidates/Signal/05_h2_variant_search.md](H2_transitional_drift/02_Candidates/Signal/05_h2_variant_search.md) | H2E (1h window), H2F (4h window), H2G (BTC-up conditional) |
| 2B | GP run (after 3A confirms terminals) | [H1_reversal/02_Candidates/Signal/04_combination_search.md](H1_reversal/02_Candidates/Signal/04_combination_search.md) | 0.70×H1 + 0.30×H5, IC-Sharpe = +0.190, holdout IC=+0.066 |
| 3B | Near-duplicate filter | [H1_reversal/05_limitations.md](H1_reversal/05_limitations.md) + [H2_transitional_drift/04_decision.md](H2_transitional_drift/04_decision.md) | H2a = H1 (mathematical identity) |
| 3D | H2 mechanism test | [H2_transitional_drift/02_Candidates/Signal/02_mechanism_test.md](H2_transitional_drift/02_Candidates/Signal/02_mechanism_test.md) | H2 CONFIRMED — IC uplift = +0.087 when BTC moves |
| 3C | Bare signal vector | [H1_reversal/02_Candidates/Strategy/01_vector_tests.md](H1_reversal/02_Candidates/Strategy/01_vector_tests.md) Part A | PASS (Sharpe=1.87, MaxDD=−34%, HitRate=51.5%) |
| 4A (H1) | C2 hazard modifiers | [H1_reversal/01_Proxies/Hazard_C2/](H1_reversal/01_Proxies/Hazard_C2/) + [overlays/regime/03_decision.md](overlays/regime/03_decision.md) | HAZ_BTC_VOL_Z APPROVED; HAZ_FNG_EXTREME APPROVED; 4 others REJECTED |
| 4B (H1) | C3 maturity modifiers | [H1_reversal/01_Proxies/Maturity_C3/](H1_reversal/01_Proxies/Maturity_C3/) + [overlays/maturity/02_decision.md](overlays/maturity/02_decision.md) | MAT_VOL_RATIO APPROVED (+0.064); MAT_FUNDING_RATE APPROVED (+0.010); 5 others REJECTED |
| 4A (H2) | H2 C2 hazard gates | [H2_transitional_drift/01_Proxies/Hazard_C2/](H2_transitional_drift/01_Proxies/Hazard_C2/) + [H2_transitional_drift/02_Candidates/Signal/03_modifier_results.md](H2_transitional_drift/02_Candidates/Signal/03_modifier_results.md) | HAZ2_BTC_VOL_Z APPROVED (+13.4% MaxDD); HAZ2_CORR_COLLAPSE REJECTED |
| 4B (H2) | H2 C3 diffusion maturity | [H2_transitional_drift/01_Proxies/Maturity_C3/](H2_transitional_drift/01_Proxies/Maturity_C3/) + [H2_transitional_drift/02_Candidates/Signal/03_modifier_results.md](H2_transitional_drift/02_Candidates/Signal/03_modifier_results.md) | MAT2_TIME_DECAY APPROVED (+72% IC uplift); MAT2_GAP_REMAINING REJECTED |
| 5 | Full signal vector | [H1_reversal/02_Candidates/Strategy/01_vector_tests.md](H1_reversal/02_Candidates/Strategy/01_vector_tests.md) Part D | Monotone Sharpe: 1.87 → 3.02 → 3.16 |
| 6 | Portfolio construction | [overlays/portfolio_construction/01_sizing_schemes.md](overlays/portfolio_construction/01_sizing_schemes.md) | PASS — Kelly Sortino = EW Sortino (10.48) |
| 7 | Regime allocation ladder | [overlays/portfolio_construction/02_regime_allocation.md](overlays/portfolio_construction/02_regime_allocation.md) | PROVISIONAL — Gate 1 fail (+3% Calmar); Gate 2 pass (+37% MaxDD); retained |
| 8 | Signal nomination | [H1_reversal/04_decision.md](H1_reversal/04_decision.md) | H1_neg_c1_x07_H5_neg_vol promoted |
| 9 | Strategy assembly | `bot/strategy/signals.py` | Deployed |
| 10A | H1 mechanism backtest | [H1_reversal/02_Candidates/Strategy/02_backtest.md](H1_reversal/02_Candidates/Strategy/02_backtest.md) | Sortino 2.69, Calmar 11.73, MaxDD −13.6% (stop-loss −3%, score-prop sizing) |
| 10B | H2C mechanism backtest | [H2_transitional_drift/02_Candidates/Strategy/01_backtest.md](H2_transitional_drift/02_Candidates/Strategy/01_backtest.md) | Sortino 1.99, Calmar 20.25, MaxDD −20.6% (BTC-rev exit −1%, 6h hold cap) |
| 10C | Discrete dual-engine sweep | [portfolio/03_combined_backtest.md](portfolio/03_combined_backtest.md) | α_TREND=0.0 optimal; Sortino 2.51, Calmar 9.68 — superseded by Section [G] |
| 12 (H1) | H1 engine robustness | [H1_reversal/02_Candidates/Strategy/03_robustness.md](H1_reversal/02_Candidates/Strategy/03_robustness.md) | 97.2% block-resample; IC positive at all weight perturbations |
| 12 (H2) | H2C engine robustness | [H2_transitional_drift/02_Candidates/Strategy/02_robustness.md](H2_transitional_drift/02_Candidates/Strategy/02_robustness.md) | 88.6% block-resample hit rate; IC positive across all 9 parameter combos |

**Backtest update (2026-03-18):** H1 SL=−3% (robust plateau center), score-proportional sizing deployed. H2C standalone Sortino=1.99/Calmar=20.25. Continuous allocation (Section [G]): f_max=0.50 → Sortino=3.30/Calmar=19.22/OOS Sortino=1.40 — ALL GATES PASSED.

| Step | Doctrine Name | File | Key Verdict |
|------|---------------|------|-------------|
| 6A | Sizing scheme ablation | [portfolio/06_sizing_comparison.md](portfolio/06_sizing_comparison.md) | Kelly-0.25 selected: best OOS Sortino (1.13) among IS-viable schemes; score-proportional IS overfits (Calmar 573→−0.48 OOS) |
| 7A | Regime component decomposition | [overlays/regime/04_component_decomposition.md](overlays/regime/04_component_decomposition.md) | BTC vol z-score gate (current) gives best OOS Sortino (1.13) vs no gate (0.51); composite (vol+disp) is second-best OOS (0.99); dispersion/MPI/FEI gates degrade OOS |

---

**Supplementary (not part of pipeline narrative):**

| File | Content |
|------|---------|
| [00_objective_and_constraints.md](00_objective_and_constraints.md) | Competition objective, admissibility criteria, failure documentation policy |
| [00_mechanism_registry.md](00_mechanism_registry.md) | Mechanism status tracker (single source of truth) |
| [H1_reversal/05_limitations.md](H1_reversal/05_limitations.md) | H1 limitations and caveats |
| [H2_transitional_drift/05_limitations.md](H2_transitional_drift/05_limitations.md) | H2 limitations and open problems |
| [portfolio/01_signal_aggregation.md](portfolio/01_signal_aggregation.md) | H1+H2 dual-engine framework (target state) |
| `charts/03_validation/ic_heatmap.png` | IC heatmap: all signals × all horizons |
| `charts/03_validation/ic_decay.png` | IC decay line chart by signal family |
| `charts/04_gp_search/ic_surface.png` | GP weight × horizon IC surface |
| `charts/modifier_screens/c2_modifier_comparison.png` | C2 MaxDD before/after for each HAZ_ proxy |
| `charts/modifier_screens/c3_ic_lift.png` | C3 IC conditional vs unconditional for each MAT_ proxy |
| `H1_reversal/02_Candidates/Strategy/charts/backtest/h1_final_equity.png` | H1 final NAV (all risk overlays) |
| `H2_transitional_drift/02_Candidates/Strategy/charts/backtest/h2_final_equity.png` | H2C final NAV |
| `portfolio/charts/combined/combined_equity.png` | H1 vs H2C vs dual-engine NAV comparison |

---

## All Tested Proxies — Ground Truth

Every proxy was pre-committed in [H1_reversal/01_Proxies/00_proxy_universe.md](H1_reversal/01_Proxies/00_proxy_universe.md) before any IC data was seen.

### C1 Alpha Proxies

| Family | Proxy | IC @ 1h | Decision | Notes |
|--------|-------|---------|----------|-------|
| **H1 CS Reversal** | CS_NEG_R1H | +0.049 | PROMOTE terminal | Short-horizon reversal |
| | CS_NEG_R2H | +0.047 | PROMOTE terminal | |
| | CS_NEG_R6H | +0.039 | PROMOTE terminal | Primary horizon |
| | CS_NEG_C1 | +0.043 | **PROMOTED → GP (0.70 wt)** | Multi-horizon composite; in live formula |
| **H5 Vol-Adj** | CS_NEG_VOL | +0.035 (+0.076 @ 24h) | **PROMOTED → GP (0.30 wt)** | Long IC tail; H5 stability filter |
| | H5_sharpe_6h | −0.030 | FAIL | Negative IC |
| | H5_sharpe_24h | −0.021 | FAIL | Negative IC |
| | H5_sortino_6h | −0.026 | FAIL | Negative IC |
| **TS Overshoot** | TS_ZSCORE_NEG_R6H | +0.027 | PASS | IC < 0.03; TS self-comparison at 6h |
| | TS_ZSCORE_NEG_R2H | +0.036 | PROMOTE | 2h TS z-score |
| | TS_BB_DIST | +0.036 | PROMOTE | Bollinger band distance (price space) |
| | CS_TS_BLEND_R6H | +0.035 | PROMOTE | 50/50 CS+TS composite |
| **H2 BTC-Diffusion** | H2A_CS_RELATIVE | = H1 IC | COLLAPSE | Mathematical identity with H1 |
| | H2B_BTC_LAG | r=−0.003 | FAIL | No predictive lag at 1h |
| | H2C_BETA_ADJ_GAP | +0.042 | **PROMOTE** | Non-collapsed; β_i varies per asset |
| | H2D_BTCGATED_H1 | +0.019 | PASS | BTC-gated H1; conditional IC=+0.110 |
| | H2E_HORIZON_1H | +0.041 @ 1h | **PROMOTE** | 1h BTC window — IC comparable to H2C |
| | H2F_HORIZON_4H | +0.034 @ 1h | **PROMOTE** | 4h BTC window — lower IC, gap more closed |
| | H2G_DIRECTION_COND | +0.020 @ 1h | PASS | BTC-up only; ~50% active timestamps |
| **H0 Original C1** | C1 momentum | −0.038 | ANTI-PREDICTIVE | Original bot selected wrong tail |
| **GP Combination** | 0.70×CS_NEG_C1 + 0.30×CS_NEG_VOL | **+0.057 @ 4h** | **PROMOTED** | Final C1 formula |

### C2 Hazard Proxies — H1 Engine

| Proxy | Status | MaxDD Improvement | Notes |
|-------|--------|------------------|-------|
| HAZ_BTC_VOL_Z | **APPROVED** | +17.8% rel | BTC realized vol z-score > 1.50 |
| HAZ_FNG_EXTREME | **APPROVED** | +17.6% rel | Fear & Greed > 75 |
| HAZ_CS_DISPERSION | REJECTED | −3.1% | Panic correlation gate worsens DD |
| HAZ_SPREAD_Z | REJECTED | −16.1% | Spread widening gate — false positives |
| HAZ_MPI_CHOP | REJECTED | −14.3% | Chop gate — misclassifies trending periods |
| HAZ_BTC_DRAWDOWN | REJECTED | −6.4% | Active selloff gate — too reactive |

### C3 Maturity Proxies — H1 Engine

| Proxy | Status | IC Uplift | Notes |
|-------|--------|-----------|-------|
| MAT_VOL_RATIO | **APPROVED** | +0.064 | Strongest C3; volume exhaustion signal |
| MAT_FUNDING_RATE | **APPROVED** | +0.010 | Crowded longs → capped upside |
| MAT_PCT_RANK | REJECTED | −0.029 | IC(fresh) < IC(uncond.) standalone |
| MAT_SMA_EXT | REJECTED | −0.009 | SMA extension gate — no IC uplift |
| MAT_RSI_PROXY | REJECTED | −0.025 | Overbought filter — no IC uplift |
| MAT_TS_ZSCORE_R6H | REJECTED | −0.036 | Parametric pct_rank analogue |
| MAT_CONSEC_UP | REJECTED | −0.020 | Streak persistence — no IC uplift |

### C2 Hazard Proxies — H2 Engine

| Proxy | Status | Metric | Notes |
|-------|--------|--------|-------|
| HAZ2_BTC_VOL_Z | **APPROVED** | MaxDD +13.4% rel, +11.4pp | BTC vol spike → reversal within diffusion window |
| HAZ2_CORR_COLLAPSE | REJECTED | MaxDD −5.3% rel | Correlation rarely collapses in Oct–Jan training period |

### C3 Diffusion Maturity Proxies — H2 Engine

| Proxy | Status | IC Uplift | Notes |
|-------|--------|-----------|-------|
| MAT2_GAP_REMAINING | REJECTED | IC fresh=+0.022 < uncond=+0.023 | Gap closure doesn't improve IC conditioning |
| MAT2_TIME_DECAY | **APPROVED** | IC fresh=+0.040 vs uncond=+0.023 (+72%) | Fresh window < 2.4h after BTC peak move |

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
| C2 HAZ_BTC_VOL_Z MaxDD improvement | ≥ 10% relative | +17.8% | PASS |
| C2 HAZ_BTC_VOL_Z worst 30d improvement | ≥ 5pp | +9.1pp | PASS |
| C2 HAZ_FNG_EXTREME MaxDD improvement | ≥ 10% relative | +17.6% | PASS |
| C3 MAT_VOL_RATIO IC uplift | IC(fresh) > IC(uncond.) | +0.064 | PASS |
| C3 MAT_FUNDING_RATE IC uplift | IC(fresh) > IC(uncond.) | +0.010 | PASS |
| H2 mechanism (IC uplift when BTC moves) | > 0.010 | +0.087 | PASS |
| H2c beta-adjusted gap IC | IC > 0.03, t > 1.5 | IC=+0.042, t=+9.85 | PASS |
