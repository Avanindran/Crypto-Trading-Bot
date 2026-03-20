# Mechanism Registry — Status Tracker

**Written:** 2026-03-17
**Purpose:** Single source of truth for mechanism status. Read before doing research.

All mechanisms pre-committed before IC data was seen (see `00_objective_and_constraints.md`).

---

## Status Summary

| Mechanism | Archetype | Proxy Status | Live? | Folder |
|-----------|-----------|-------------|-------|--------|
| **H1** Transient Expectation Overshoot | Reversal | PROMOTED | Yes | [H1_reversal/](H1_reversal/) |
| **H2** Expectation Diffusion via BTC | Momentum | PROMOTED (H2c) | Yes | [H2_transitional_drift/](H2_transitional_drift/) |
| **H5** Low-Vol Stability Filter | (H1 companion) | PROMOTED (as H1 blend) | Yes | [H1_reversal/](H1_reversal/) |
| **H6** Streak Persistence | (rejected) | FAILED — near-zero IC | No | [H1_reversal/02_Candidates/Signal/03_rejected_proxies.md](H1_reversal/02_Candidates/Signal/03_rejected_proxies.md) |
| **Regime** λ_t Hazard Rate | Overlay | APPROVED | Yes | [overlays/regime/](overlays/regime/) |
| **Maturity** M_t Drift Capacity | Overlay | PROVISIONAL | Yes | [overlays/maturity/](overlays/maturity/) |

---

## H1 — Transient Expectation Overshoot

**Archetype:** Reversal (reaction magnitude error)
**Status:** PROMOTED — live in `bot/strategy/signals.py`

**Mechanism:** Short-horizon price moves driven by liquidity shocks push P_t > E[P_t|I_t]. Corrective flow from market makers and arbitrageurs restores price toward equilibrium → E[r_forward] > 0 for laggards.

**Live formula:**
```
C1_i = 0.70 × CS_z(−C1_raw_i) + 0.30 × CS_z(−realized_vol_6h_i)
C1_raw_i = 0.10×r_30m + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r2h)
```

**Key metrics:** IC = +0.057 at 4h (t=12.7), holdout IC = +0.066 (t=10.6), block-resample 97.2%

**References:** De Bondt-Thaler (1985), Lehmann (1990), Jegadeesh (1990), Frazzini-Pedersen (2014)

**Docs:** [H1_reversal/00_mechanism.md](H1_reversal/00_mechanism.md)

---

## H2 — Expectation Diffusion via BTC

**Archetype:** Momentum (expectation updating speed error)
**Status:** MECHANISM CONFIRMED — H2c (beta-adjusted gap) PROMOTED and DEPLOYED

**Mechanism:** E[r_i|I_t] ≈ βᵢ · r_BTC (shared factor exposure). When BTC reprices but altcoin has not yet adjusted: Δᵢ = βᵢ · r_BTC,h − r_i,h > 0 → unrealized expected return.

**Why H2a/H2b failed:**
- H2a: CS_z(alt_r − btc_r) = CS_z(alt_r) — mathematical identity (btc_r is cross-sectional constant)
- H2b: lagged BTC return Pearson r ≈ −0.003 (diffusion < 1h resolution)

**Why mechanism is confirmed:**
- H1 IC @ BTC flat = +0.024 vs H1 IC @ BTC large move = +0.110
- IC uplift = +0.087 >> gate of 0.010 → BTC-diffusion mechanism confirmed

**Live proxy (H2c):** `CS_z(β_i · r_BTC,2h − r_i,2h)` — IC=+0.042 @ 1h (t=+9.85). Deployed via continuous allocation: f_t = f_max × btc_activity × stress_decay (f_max=0.50). See `research/portfolio/05_dual_portfolio_backtest.md`.

**References:** Kyle (1985), Grossman-Stiglitz (1980), Hou (2007), Lo-MacKinlay (1990)

**Docs:** [H2_transitional_drift/00_mechanism.md](H2_transitional_drift/00_mechanism.md)

---

## Regime Overlay — λ_t Hazard Rate

**Status:** APPROVED — live in `bot/strategy/regime.py`
**Validation:** MaxDD improvement +17.8% relative (gate ≥ 10%), threshold-robust at {0.50…0.70}

**Mechanism:** LSI → λ_t → exp(−λ_t) position scaling. At λ=4: exp(−4) = 1.8% exposure.

**Docs:** [overlays/regime/00_mechanism.md](overlays/regime/00_mechanism.md)

---

## Maturity Overlay — M_t Drift Capacity

**Status:** APPROVED — MAT_VOL_RATIO (+0.064 IC uplift) and MAT_FUNDING_RATE (+0.010 IC uplift) formally validated; pct_rank standalone REJECTED; composite retained

**Mechanism:** Measures remaining correction potential. M_t ∈ [0,1]; (1−M_t) scales position size.

**Key finding:** IC(fresh, pct_rank < 30%) = 0.018 < IC(unconditional) = 0.048 → pct_rank FAILS in trending period. MAT_FUNDING_RATE APPROVED (IC uplift +0.010); MAT_VOL_RATIO APPROVED (strongest C3 proxy, IC uplift +0.064). Remaining components (SMA extension, pct_rank) retained on composite economic grounds.

**Docs:** [overlays/maturity/00_mechanism.md](overlays/maturity/00_mechanism.md)

---

## Portfolio Layer

**Status:** H1 live; H2C live (continuous allocation, f_max=0.50)

**Live formula:** `PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)`

**Target (dual-engine):** Regime-conditional H1/H2 blend — see [portfolio/01_signal_aggregation.md](portfolio/01_signal_aggregation.md)

**Docs:** [portfolio/00_portfolio_design.md](portfolio/00_portfolio_design.md)

---

## Research Pipeline Cross-Reference

Full doctrine step → file mapping: [10_pipeline_index.md](10_pipeline_index.md)

| Gate | Threshold | Actual | Result |
|------|-----------|--------|--------|
| IC at 4h | > 0, t > 1.5 | IC=+0.057, t=12.7 | PASS |
| Holdout IC | > 0 | +0.066 | PASS |
| Block-resample hit rate | ≥ 55% | 97.2% | PASS |
| Bare signal Sharpe | > 0 | 1.87 | PASS |
| C2 MaxDD improvement | ≥ 10% relative | +17.8% | PASS |
| H2 mechanism uplift | > 0.010 | +0.087 | PASS |
| C3 pct_rank IC gate | IC(fresh) > IC(uncond.) | 0.018 < 0.048 | **FAIL** |
