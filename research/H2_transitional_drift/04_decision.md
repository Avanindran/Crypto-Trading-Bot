# H2 — Decision Record

**Date:** 2026-03-17
**Decision:** MECHANISM CONFIRMED — H2c PROMOTED, H2d PASS
**Deployed:** No — only H1 live. H2c eligible for GP terminal set inclusion.

---

## Summary

| Component | Outcome | Evidence |
|-----------|---------|----------|
| H2a proxy (CS_z framework) | **COLLAPSED** — mathematical identity with H1 | IC_H2a = IC_H1 at all horizons; proof below |
| H2b proxy (lagged BTC return) | **FAILED** — no predictive lag at 1h | Pearson r ≈ −0.003 |
| H2c proxy (beta-adjusted gap) | **PROMOTED** — IC=+0.042 @ 1h, t=+9.85 | Non-collapsed; β_i varies per asset |
| H2d proxy (BTC-gated H1) | **PASS** — IC=+0.019 @ 1h, t=+5.32 | Diluted by gating; strong conditional IC |
| H2 mechanism (BTC-conditional IC uplift) | **CONFIRMED** — IC uplift = +0.087 | Gate > 0.010 → PASS |

---

## H2a Collapse — Mathematical Proof

Proxy: `CS_z(alt_r_2h − btc_r_2h)`

BTC return at timestamp t is a **cross-sectional constant** — the same scalar value for all 48 pairs:

```
btc_r_2h(t) = c_t    (same for all pairs i)

In cross-sectional z-normalization:
  z_i = (x_i − mean(x)) / std(x)

Subtracting a constant c from every x_i:
  (x_i − c) − mean(x − c)  =  x_i − mean(x)

So CS_z(x_i − c) = CS_z(x_i) for any constant c.

Therefore: CS_z(alt_r_2h − btc_r_2h) = CS_z(alt_r_2h)
```

This is a **mathematical identity**, not an empirical finding. H2a provides zero independent signal beyond H1.

**IC validation:** H2a IC at all horizons equals H1 IC within numerical precision (difference < 0.001).
Confirmed in [02_Candidates/Signal/01_ic_results.md](02_Candidates/Signal/01_ic_results.md).

---

## H2b Failure

Proxy: `r_BTC,t−1h` as predictor of mean altcoin forward return.

Pearson r = −0.003 (not significant). No predictive lag at 1h resolution.

**Economic explanation:** Any BTC-to-altcoin diffusion lag at sub-1h timescales is fully arbitraged within the 1h kline aggregation window. The competition's 60-second loop does not provide sub-hour resolution to exploit this.

---

## H2c — Beta-Adjusted Gap (PROMOTED)

Proxy: `CS_z(β_i × r_BTC,2h − r_i,2h)` where β_i = rolling 48h OLS slope.

**Why it survives CS normalization:** β_i × r_BTC varies per asset — assets with higher BTC sensitivity receive a larger expected return target. The gap `β_i × r_BTC − r_i` discriminates between assets in a way that survives CS normalization, unlike H2a.

**IC results:**

| Horizon | IC | t-stat | Gate |
|---------|----|--------|------|
| 1h | +0.042 | +9.85 | PROMOTE |
| 2h | +0.036 | — | — |
| 4h | +0.029 | — | — |

**Decision: PROMOTED** — IC=+0.042 @ 1h, t=+9.85. Eligible as GP terminal in the H2 expansion of gp_search.py.

Full results: [01_Proxies/Alpha_C1/H2C_BETA_ADJ_GAP/01_ic_test.md](01_Proxies/Alpha_C1/H2C_BETA_ADJ_GAP/01_ic_test.md)

---

## H2d — BTC-Gated H1 (PASS)

Proxy: `CS_z(−r_2h) × I(|r_BTC,2h| > 0.5%)`

**IC results:**

| Horizon | IC | t-stat | Gate |
|---------|----|--------|------|
| 1h | +0.019 | +5.32 | PASS (not PROMOTE) |

**Unconditional IC dilution:** When BTC is flat (~40–50% of periods), signal = 0. These periods contribute noise to the unconditional IC, diluting it from the conditional +0.110 down to +0.019.

**Decision: PASS** — passes minimum gate but does not reach PROMOTE. Better framed as a C2 modifier (active only when BTC moves) than a standalone C1 alpha.

Full results: [01_Proxies/Alpha_C1/H2D_BTCGATED_H1/01_ic_test.md](01_Proxies/Alpha_C1/H2D_BTCGATED_H1/01_ic_test.md)

---

## Mechanism Confirmation — BTC-Conditional IC

IC of the H1 reversal signal conditioned on preceding BTC 2h move magnitude:

| BTC Move Bucket | IC at 4h | N |
|-----------------|----------|---|
| Flat (|r_2h| < 0.5%) | +0.024 | ~180 timestamps |
| Moderate (0.5–1.5%) | +0.055 | ~320 timestamps |
| Large up (≥ 1.5%) | +0.110 | ~140 timestamps |
| Large down (≥ 1.5%) | +0.042 | ~90 timestamps |

**IC uplift = IC(large_up) − IC(flat) = +0.086**

Gate: > 0.010 → **PASS** (8.6× gate threshold)

Full mechanism test: [02_Candidates/Signal/02_mechanism_test.md](02_Candidates/Signal/02_mechanism_test.md).

---

## Implications for Live Bot

H2c/H2d are not yet deployed in the live bot. The mechanism is captured implicitly:
- BTC gate in `bot/risk/kill_switch.py` gates entries when BTC drops > 3%
- MPI (momentum persistence index) uses BTC hourly returns for trend quality
- LSI incorporates BTC vol as a primary component

**Deployment path for H2c:** Include in next GP search terminal set. Requires computing rolling β_i live in `bot/data/feature_builder.py` and passing to `signals.py`. Flag to user before Mar 28 deadline — this is a separate commit.

---

## Navigation

| File | Content |
|------|---------|
| [00_mechanism.md](00_mechanism.md) | H2 mechanism theory (Δᵢ formalism) |
| [01_Proxies/00_proxy_universe.md](01_Proxies/00_proxy_universe.md) | All H2 proxy specs and verdicts |
| [01_Proxies/Alpha_C1/H2A_CS_RELATIVE/](01_Proxies/Alpha_C1/H2A_CS_RELATIVE/) | Collapsed proxy (mathematical identity) |
| [01_Proxies/Alpha_C1/H2B_BTC_LAG/](01_Proxies/Alpha_C1/H2B_BTC_LAG/) | Failed lag proxy |
| [01_Proxies/Alpha_C1/H2C_BETA_ADJ_GAP/](01_Proxies/Alpha_C1/H2C_BETA_ADJ_GAP/) | PROMOTED — beta-adjusted gap |
| [01_Proxies/Alpha_C1/H2D_BTCGATED_H1/](01_Proxies/Alpha_C1/H2D_BTCGATED_H1/) | PASS — BTC-gated H1 |
| [02_Candidates/Signal/01_ic_results.md](02_Candidates/Signal/01_ic_results.md) | H2a collapse + H2b failure data |
| [02_Candidates/Signal/02_mechanism_test.md](02_Candidates/Signal/02_mechanism_test.md) | BTC-conditional IC uplift (+0.087) |
| [05_limitations.md](05_limitations.md) | H2-specific caveats and open problems |
| [../H1_reversal/04_decision.md](../H1_reversal/04_decision.md) | H1 promotion (deployed signal) |
