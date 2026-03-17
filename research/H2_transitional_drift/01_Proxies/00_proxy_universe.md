# H2 Transitional Drift — Proxy Universe (Scope Inventory)

**Status:** FROZEN before IC testing (pre-committed 2026-03-17)
**Mechanism:** H2 Expectation Diffusion via BTC — see [../00_mechanism.md](../00_mechanism.md)

All proxies are C1 (alpha direction). H2 tests whether BTC-driven diffusion can be operationalised as a distinct signal from H1 reversal.

---

## C1 — Alpha Direction Proxies (4 total)

| Proxy ID | Formula | Status | IC_best | Notes |
|----------|---------|--------|---------|-------|
| `H2A_CS_RELATIVE` | `CS_z(r_i − r_BTC)` | **COLLAPSED** | N/A | Mathematical identity with H1 |
| `H2B_BTC_LAG` | `r_BTC,t−1h` (market predictor) | **FAILED** | Pearson r ≈ −0.003 | No lag at 1h resolution |
| `H2C_BETA_ADJ_GAP` | `CS_z(β_i×r_BTC,2h − r_i,2h)` | **PROMOTED** | +0.042 @ 1h | Non-collapsed; β_i varies per asset |
| `H2D_BTCGATED_H1` | `CS_z(−r_2h) × I(\|r_BTC,2h\| > 0.5%)` | **PASS** | +0.019 @ 1h | Diluted by gating; candidate C2 modifier |

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
