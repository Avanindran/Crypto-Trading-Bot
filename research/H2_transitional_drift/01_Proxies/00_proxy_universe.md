# H2 Transitional Drift — Proxy Universe (Scope Inventory)

**Status:** C1 variants screened 2026-03-18; C2/C3 screened 2026-03-18
**Mechanism:** H2 Expectation Diffusion via BTC — see [../00_mechanism.md](../00_mechanism.md)

C1 tests whether BTC-driven diffusion can be operationalised as a distinct signal from H1 reversal.
C2 gates H2C entries based on conditions that invalidate the BTC-diffusion channel.
C3 filters H2C entries based on diffusion window exhaustion (how much catch-up has already propagated).

---

## C1 — Alpha Direction Proxies (7 total)

| Proxy ID | Formula | Status | IC_best | Notes |
|----------|---------|--------|---------|-------|
| `H2A_CS_RELATIVE` | `CS_z(r_i − r_BTC)` | **COLLAPSED** | N/A | Mathematical identity with H1 |
| `H2B_BTC_LAG` | `r_BTC,t−1h` (market predictor) | **FAILED** | Pearson r ≈ −0.003 | No lag at 1h resolution |
| `H2C_BETA_ADJ_GAP` | `CS_z(β_i×r_BTC,2h − r_i,2h)` | **PROMOTED** | +0.042 @ 1h | Non-collapsed; β_i varies per asset |
| `H2D_BTCGATED_H1` | `CS_z(−r_2h) × I(\|r_BTC,2h\| > 0.5%)` | **PASS** | +0.019 @ 1h | Diluted by gating; candidate C2 modifier |
| `H2E_HORIZON_1H` | `CS_z(β_i×r_BTC,1h − r_i,1h)` | **PROMOTE** | +0.041 @ 1h | Tighter window; IC comparable to H2C |
| `H2F_HORIZON_4H` | `CS_z(β_i×r_BTC,4h − r_i,4h)` | **PROMOTE** | +0.034 @ 1h | Wider window; lower IC than H2C |
| `H2G_DIRECTION_COND` | `CS_z(β_i×r_BTC,2h − r_i,2h) × I(r_BTC,2h > 0)` | **PASS** | +0.020 @ 1h | BTC-up only; ~50% active timestamps |

---

## C2 — Hazard Gate Proxies (2 total)

Block H2C entries when the BTC-diffusion channel is invalidated.

| Proxy ID | Formula | Status | Notes |
|----------|---------|--------|-------|
| `HAZ2_BTC_VOL_Z` | BTC 6h realized vol z-score > 1.50 | **APPROVED** | MaxDD +13.4% rel, worst 30d +11.4pp |
| `HAZ2_CORR_COLLAPSE` | 48h median Spearman ρ(r_BTC, r_i) < 0.40 | **REJECTED** | MaxDD −5.3% rel; correlation rarely collapses in training period |

See [Hazard_C2/00_proxy_universe.md](Hazard_C2/00_proxy_universe.md).

---

## C3 — Maturity Scalers (2 total)

Block H2C entries when the diffusion window has already propagated.

| Proxy ID | Formula | Status | Notes |
|----------|---------|--------|-------|
| `MAT2_GAP_REMAINING` | `\|r_i,2h\| / \|β_i×r_BTC,2h\|` gap closure fraction | **REJECTED** | IC(fresh)=+0.022 < IC(uncond)=+0.023; no uplift |
| `MAT2_TIME_DECAY` | `(t − t_peak_BTC) / 6h` time since BTC peak 1h move | **APPROVED** | IC(fresh)=+0.040 vs IC(uncond)=+0.023; +72% uplift |

See [Maturity_C3/00_proxy_universe.md](Maturity_C3/00_proxy_universe.md).

---

## Mechanism Status

| Test | Outcome | Evidence |
|------|---------|----------|
| H2 mechanism (BTC-conditional uplift) | **CONFIRMED** | IC uplift = +0.087 (flat BTC: +0.024 → large BTC move: +0.110) |
| H2c non-collapsed proxy | **PROMOTED** | IC=+0.042 @ 1h, t=+9.85 |
| H2d BTC-gated H1 | **PASS** | IC=+0.019 @ 1h (diluted); conditional IC = +0.110 when active |

**Key insight:** The H2 diffusion mechanism is real and strongly confirmed (IC uplift 8.6× gate threshold). The challenge is operationalising it without CS collapse (H2a) or kline-resolution dilution (H2b). H2c solves this by making BTC-sensitivity asset-specific via rolling β.

---

## Notes on H2D as C2 Modifier

H2D passes as a standalone signal but is better framed as a C2 hazard gate or C1 amplifier:
- Signal is active ~50–60% of periods (when BTC moves)
- When active, conditional IC = +0.110 (vs unconditional H1 IC = +0.024 in flat periods)
- This operationalises the mechanism test finding directly as a trade filter

See [../04_decision.md](../04_decision.md) for full analysis and future path.

---

## Architecture Note

H2's C2 and C3 are **mechanism-specific** — they live inside the H2 mechanism folder,
not in `overlays/`. The sole cross-mechanism overlay is `overlays/regime/` (λ_t hazard rate),
which determines how much portfolio weight to allocate between H1 and H2 based on BTC
regime state and known failure modes of each engine.

H2's C3 (diffusion maturity) is conceptually parallel to H1's C3 (reversal maturity) but
measures a completely different phenomenon: diffusion window propagation vs mean-reversion lifecycle.
