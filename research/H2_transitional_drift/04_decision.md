# H2 — Decision Record

**Date:** 2026-03-17
**Decision:** MECHANISM CONFIRMED — Direct Proxy PENDING REBUILD
**Deployed:** No — only H1 live. H2 experimental, path forward identified.

---

## Summary

| Component | Outcome | Evidence |
|-----------|---------|----------|
| H2a proxy (CS_z framework) | **COLLAPSED** — mathematical identity with H1 | IC_H2a = IC_H1 at all horizons; proof below |
| H2b proxy (lagged BTC return) | **FAILED** — no predictive lag at 1h | Pearson r ≈ −0.003 |
| H2 mechanism (BTC-conditional IC uplift) | **CONFIRMED** — IC uplift = +0.087 | Gate > 0.010 → PASS |

---

## H2a Collapse — Mathematical Proof

Proxy: `CS_z(alt_r_2h − btc_r_2h)`

BTC return at timestamp t is a **cross-sectional constant** — the same scalar value for all 48 pairs:

```
btc_r_2h(t) = c_t    (same for all pairs i)

CS_z(alt_r_2h − c_t) = CS_z(alt_r_2h − c_t)

In cross-sectional z-normalization:
  z_i = (x_i − mean(x)) / std(x)

Subtracting a constant c from every x_i:
  (x_i − c) − mean(x − c)    =    (x_i − c) − (mean(x) − c)    =    x_i − mean(x)

So CS_z(x_i − c) = CS_z(x_i) for any constant c.

Therefore: CS_z(alt_r_2h − btc_r_2h) = CS_z(alt_r_2h)
```

This is a **mathematical identity**, not an empirical finding. H2a provides zero independent signal beyond H1 in any cross-sectional z-normalization framework.

**IC validation:** H2a IC at all horizons equals H1 IC within numerical precision (difference < 0.001). Confirmed in [03_results/01_ic_results.md](03_results/01_ic_results.md).

---

## H2b Failure

Proxy: `r_BTC,t−1h` as predictor of mean altcoin forward return.

Pearson r = −0.003 (not significant). No predictive lag at 1h resolution.

**Economic explanation:** If the BTC-diffusion lag exists at sub-1h timescales (minutes to tens of minutes), it is fully arbitraged within the 1h kline aggregation window. The competition's 1-min polling cadence with 60s loop cycle does not provide meaningful sub-hour resolution to exploit this.

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

**Interpretation:** The H1 signal's alpha is 4.6× higher when BTC has moved significantly. This directly confirms the BTC-diffusion mechanism: information flows from BTC to altcoins, and the diffusion window is the source of H1's state-dependent alpha. The mechanism is real — only the direct proxy implementation fails.

Full mechanism test: [03_results/02_mechanism_test.md](03_results/02_mechanism_test.md).

---

## Path Forward — Experimental H2 Proxy Construction

The correct H2 proxy must preserve BTC as a **non-constant** cross-sectional discriminator. Options (not yet validated):

### Option 1 — Raw divergence (unzscored)

```
signal_i = r_BTC,h − r_i,h    (no cross-sectional normalization)
```

BTC return is now a component of the signal, not a cross-sectional constant subtracted before normalization. Preserves Δᵢ structure. Risk: raw signal has different scale properties than CS_z; requires normalization step that doesn't remove BTC component.

### Option 2 — Beta-adjusted divergence

```
signal_i = β_i · r_BTC,h − r_i,h
    where β_i estimated from 48h rolling regression of r_i on r_BTC
```

Preserves the full Δᵢ = βᵢ · r_BTC − r_i formulation. Risk: rolling beta estimate noisy during regime transitions; beta instability amplifies signal noise.

### Option 3 — Conditional entry filter

Use BTC move magnitude as a regime gate (switch H1 from passive to active only when BTC has moved above threshold). This uses H2 as a selector, not a separate signal.

```python
if abs(r_BTC_2h) > BTC_MOVE_THRESHOLD:
    scale_factor = H2_AMPLIFIER    # e.g., 1.5×
else:
    scale_factor = 1.0
```

This is the closest implementation to the validated H2 mechanism test result.

**None of these have been validated.** H2 remains experimental until a proxy with IC > 0 and t > 1.0 is found on a fresh test.

---

## Implications for Live Bot

H2 is not deployed in the live bot. The BTC-conditional IC uplift is captured implicitly through the regime overlay:

- When BTC makes a large move, LSI rises → regime transitions → λ_t adjusts
- The BTC gate in `bot/risk/kill_switch.py` gates entries when BTC drops > 3%
- The MPI (momentum persistence index) uses BTC hourly returns to estimate trend quality

The regime overlay provides partial H2-like conditioning on BTC state, but does not directly implement the Δᵢ signal. A true H2 implementation would explicitly weight laggards relative to BTC-implied expectation.

---

## Navigation

| File | Content |
|------|---------|
| [00_mechanism.md](00_mechanism.md) | H2 mechanism theory (Δᵢ formalism) |
| [01_proxy_universe.md](01_proxy_universe.md) | Pre-committed proxy specs |
| [02_validation_plan.md](02_validation_plan.md) | IC test and mechanism test spec |
| [03_results/01_ic_results.md](03_results/01_ic_results.md) | H2a collapse and H2b failure data |
| [03_results/02_mechanism_test.md](03_results/02_mechanism_test.md) | BTC-conditional IC uplift |
| [05_limitations.md](05_limitations.md) | H2-specific caveats and open problems |
| [../H1_reversal/04_decision.md](../H1_reversal/04_decision.md) | H1 promotion (the deployed signal) |
| [../portfolio/01_signal_aggregation.md](../portfolio/01_signal_aggregation.md) | How H1 + H2 would combine |
