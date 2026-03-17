# Research Pipeline — Overview and Script Guide

Run all scripts from the `Crypto-Trading-Bot/` directory with `python -X utf8`.

## Folder Structure

```
research/
├── 00_objective_and_constraints.md   Competition objective, admissibility criteria
├── 00_mechanism_registry.md          Status tracker for all mechanisms (read this first)
├── 10_pipeline_index.md              Master index: doctrine step → file → verdict
│
├── H1_reversal/                      H1 = Transient Expectation Overshoot (Reversal archetype)
│   ├── 00_mechanism.md               Mechanism theory (expectation overshoot, corrective flow)
│   ├── 01_Proxies/                   Per-proxy folders — 00_mechanism.md + result records
│   │   ├── 00_proxy_universe.md      Scope inventory (all C1/C2/C3 proxies)
│   │   ├── Alpha_C1/                 9 alpha direction proxies (CS and TS family)
│   │   │   ├── CS_NEG_R1H/           {00_mechanism.md, 01_ic_test.md}
│   │   │   ├── CS_NEG_R2H/
│   │   │   ├── CS_NEG_R6H/
│   │   │   ├── CS_NEG_C1/            in final GP formula (0.70 weight)
│   │   │   ├── CS_NEG_VOL/           H5 stability (0.30 weight in final formula)
│   │   │   ├── TS_ZSCORE_NEG_R6H/    [NEW] TS z-score vs own 48h history (PASS)
│   │   │   ├── TS_ZSCORE_NEG_R2H/    [NEW] TS z-score 2h horizon (PROMOTE)
│   │   │   ├── TS_BB_DIST/           [NEW] Bollinger band distance (PROMOTE)
│   │   │   └── CS_TS_BLEND_R6H/      [NEW] 50/50 CS+TS composite (PROMOTE)
│   │   ├── Hazard_C2/                6 hazard gate proxies — each individually screened
│   │   │   ├── HAZ_BTC_VOL_Z/        {00_mechanism.md, 02_modifier_screen.md} APPROVED
│   │   │   ├── HAZ_CS_DISPERSION/    REJECTED
│   │   │   ├── HAZ_SPREAD_Z/         REJECTED
│   │   │   ├── HAZ_FNG_EXTREME/      [NEW] APPROVED (Fear & Greed > 75)
│   │   │   ├── HAZ_MPI_CHOP/         REJECTED
│   │   │   └── HAZ_BTC_DRAWDOWN/     REJECTED
│   │   └── Maturity_C3/              7 maturity filter proxies — each individually screened
│   │       ├── MAT_PCT_RANK/         {00_mechanism.md, 02_modifier_screen.md} REJECTED
│   │       ├── MAT_SMA_EXT/          REJECTED
│   │       ├── MAT_RSI_PROXY/        REJECTED
│   │       ├── MAT_FUNDING_RATE/     APPROVED (IC uplift +0.010)
│   │       ├── MAT_TS_ZSCORE_R6H/    [NEW] REJECTED
│   │       ├── MAT_VOL_RATIO/        [NEW] APPROVED (IC uplift +0.064 — strongest C3 signal)
│   │       └── MAT_CONSEC_UP/        [NEW] REJECTED
│   ├── 03_results/                   Script-generated result records
│   │   ├── 01_ic_results.md          H1 CS proxy IC results
│   │   ├── 02_stability_screen.md    H5 stability proxy results
│   │   ├── 03_rejected_proxies.md    H6 streak rejection record
│   │   ├── 04_combination_search.md  GP combination results (0.70×H1 + 0.30×H5)
│   │   ├── 05_ts_variant_search.md   [NEW] TS + H2c/H2d IC results
│   │   ├── 05_vector_tests.md        Bare → +C2 → +C3 sequential improvement
│   │   ├── 06_backtest.md            Full strategy backtest (maker fee 0.05%)
│   │   └── 07_robustness.md          Block-resample 97.2%; weight-perturbation
│   ├── 03_OOS_Reservation/           [NEW] OOS holdout formal declaration
│   │   └── oos_reservation.md        Dec–Jan holdout documented
│   ├── 04_decision.md                Promotion record — PROMOTED
│   └── 05_limitations.md             H1-specific limitations and caveats
│
├── H2_transitional_drift/            H2 = Expectation Diffusion via BTC (Momentum archetype)
│   ├── 00_mechanism.md               Mechanism theory (Δᵢ = βᵢ·r_BTC − rᵢ)
│   ├── 01_Proxies/                   Per-proxy folders
│   │   └── Alpha_C1/
│   │       ├── H2A_CS_RELATIVE/      {00_mechanism.md} — COLLAPSED (= H1 identity)
│   │       ├── H2B_BTC_LAG/          {00_mechanism.md} — FAILED (no lag)
│   │       ├── H2C_BETA_ADJ_GAP/     [NEW] {00_mechanism.md} — PROMOTED (IC=+0.042)
│   │       └── H2D_BTCGATED_H1/      [NEW] {00_mechanism.md} — PASS (IC=+0.019)
│   ├── 03_results/
│   │   ├── 01_ic_results.md          H2a collapse + H2b failure + H2c/H2d results
│   │   └── 02_mechanism_test.md      BTC-conditional IC uplift (+0.087)
│   ├── 04_decision.md                H2a COLLAPSED, H2c PROMOTED, mechanism CONFIRMED
│   └── 05_limitations.md             H2-specific open problems
│
├── overlays/
│   ├── regime/                       λ_t hazard rate (live in bot)
│   │   ├── 00_mechanism.md
│   │   ├── 01_proxy_universe.md      LSI/MPI/FEI component specs
│   │   ├── 02_results.md             LSI threshold robustness
│   │   └── 03_decision.md            APPROVED
│   ├── maturity/                     M_t drift capacity (live in bot)
│   │   ├── 00_mechanism.md
│   │   ├── 01_proxy_universe.md      M_t component specs
│   │   └── 03_decision.md            pct_rank REJECTED; composite PROVISIONAL
│   └── portfolio_construction/
│       ├── 01_sizing_schemes.md      Portfolio sizing test (EW vs Kelly vs score-prop)
│       └── 02_regime_allocation.md   Regime ladder (no-regime vs binary vs 3-regime)
│
├── portfolio/                        How H1 + H2 combine in the allocation layer
│   ├── 00_portfolio_design.md
│   ├── 01_signal_aggregation.md      H1+H2 regime-conditional dual-engine framework
│   └── 02_live_configuration.md      Current live state (H1 only; H2 pending)
│
└── charts/
    ├── 03_validation/                ic_heatmap.png, ic_decay.png
    ├── 04_gp_search/                 ic_surface.png
    ├── 06_vector_tests/              equity_curves.png
    ├── 06_backtest/                  equity_curve.png, drawdown.png, monthly_pnl.png
    └── modifier_screens/             c2_modifier_comparison.png, c3_ic_lift.png
```

---

## Pipeline Execution Order

| Step | Script | Output | Purpose |
|------|--------|--------|---------|
| 3A | `research/signal_search.py` | `H1_reversal/03_results/01_ic_results.md` + `05_ts_variant_search.md` | All proxy IC validation (CS + TS families + H2c/H2d) |
| 4A/4B | `research/modifier_screen.py` | `H1_reversal/01_Proxies/Hazard_C2/*/02_modifier_screen.md` + C3 screens | Individual C2/C3 modifier screens |
| 2B | `research/gp_search.py` | `H1_reversal/03_results/04_combination_search.md` | GP linear weight search (expanded terminal set incl. TS) |
| 3D | `research/h2_mechanism_test.py` | `H2_transitional_drift/03_results/02_mechanism_test.md` | BTC-conditional IC uplift |
| 3C-5 | `research/vector_tests.py` | `H1_reversal/03_results/05_vector_tests.md` | Bare → +C2 → +C3 improvement |
| 6 | `research/portfolio_tests.py` | `overlays/portfolio_construction/01_sizing_schemes.md` | Sizing scheme comparison |
| 7 | `research/regime_tests.py` | `overlays/portfolio_construction/02_regime_allocation.md` | Regime ladder comparison |
| 12 | `research/robustness.py` | `H1_reversal/03_results/07_robustness.md` | Robustness checks |
| 10 | `research/backtest_simulation.py` | `H1_reversal/03_results/06_backtest.md` | Full strategy simulation (maker fee 0.05%) |

## Script Dependencies

```
ic_validation_extended.py   (data library — imported by all other scripts)
    |
    +-- signal_search.py         (C1 alpha: CS + TS family, H2c/H2d)
    +-- modifier_screen.py       (C2 hazard + C3 maturity individual screens)   [NEW]
    +-- gp_search.py             (GP combination search, expanded terminal set)
    +-- h2_mechanism_test.py     (BTC-conditional IC uplift)
    +-- vector_tests.py          (Bare → +C2 → +C3 backtest)
    |     |
    |     +-- portfolio_tests.py
    |     +-- regime_tests.py
    +-- backtest_simulation.py   (full strategy backtest, fee sensitivity)
    +-- robustness.py            (block-resample + weight perturbation)
```

## Key Findings (2026-03-17)

| Finding | Value | Source |
|---------|-------|--------|
| Promoted C1 formula | 0.70×CS_z(−C1_raw) + 0.30×CS_z(−vol_6h) | gp_search.py |
| IC @ 4h | +0.057, t=12.7 | signal_search.py |
| H2c beta-adjusted gap | IC=+0.042, t=+9.85 | signal_search.py NEW |
| TS_BB_DIST | IC=+0.036, PROMOTE | signal_search.py NEW |
| TS_ZSCORE_NEG_R2H | IC=+0.036, PROMOTE | signal_search.py NEW |
| HAZ_FNG_EXTREME | MaxDD improv +17.6%, APPROVED | modifier_screen.py NEW |
| MAT_VOL_RATIO | IC uplift +0.064, APPROVED | modifier_screen.py NEW |
| Fee (corrected) | 0.05% maker (was 0.10% taker) | competition rules |

## Key Doctrine Files

| File | Content |
|------|---------|
| `research/00_mechanism_registry.md` | Mechanism status tracker — read this first |
| `research/00_objective_and_constraints.md` | Competition objective and admissibility criteria |
| `research/10_pipeline_index.md` | Master index — every doctrine step → file → verdict |
| `research/H1_reversal/00_mechanism.md` | Live signal mechanism (Reversal archetype) |
| `research/H2_transitional_drift/00_mechanism.md` | H2 mechanism (Momentum archetype) |
