# H2 — Expectation Diffusion via BTC (Transitional Drift Archetype)

**Archetype:** Momentum (Transitional Drift) — see `Systematic Trading Architecture/01_strategy_archetypes.md`
**Status:** MECHANISM CONFIRMED — direct proxy PENDING rebuild
**Last updated:** 2026-03-17

---

## Mechanism Statement

Crypto markets are governed by a **partially shared expectation structure** where BTC serves as the primary state variable for market-wide information.

When new information arrives (macro event, institutional flow, derivatives trigger), the conditional expectation of returns updates first in BTC due to its superior liquidity and information aggregation capacity:

```
E[r_BTC | I_t] updates immediately as information is reflected in BTC price
E[r_i   | I_t] for altcoin i updates with delay τ_i > 0
```

During the delay window, a **temporary expectation inconsistency** exists:

```
E[r_i | I_t] ≈ βᵢ · r_BTC    (altcoin should track BTC given shared factor exposure)
but observed:    r_i < βᵢ · r_BTC   (altcoin has not yet repriced)
```

The **expectation gap** represents unrealized expected return:

```
Δᵢ = βᵢ · r_BTC,h − r_i,h    (BTC-adjusted divergence)
```

When Δᵢ > 0 (altcoin has underperformed its expected BTC-linked return), the asset has positive expected forward return as the gap closes.

---

## What Is Mispriced

The mispriced quantity is the **incomplete expectation update**:

```
Drift_i = E[r_i | I_t] − r_i,0 = βᵢ · r_BTC − r_i,0
```

The altcoin price reflects stale information (pre-BTC-move expectation). As altcoin market participants observe BTC's repricing and update their own expectations, the drift is realized.

This is **Momentum**, not Reversal:
- The expected direction is the SAME as BTC's move (lagged, not corrective)
- The mechanism is expectation updating speed error (BTC updates faster, alts lag)
- Contrast with H1: H1 exploits magnitude error (overshoot, then correction opposite to move)

---

## Return Engine

The return driver is the **propagation of BTC-originated information to altcoin prices**:

1. New information (macro, regulatory, institutional) hits BTC order books first
2. BTC reprices within minutes via derivatives arbitrage (CME, Binance futures)
3. Altcoin-USD pairs adjust through BTC-USD / BTC-ALT cross-pair flows
4. This transmission has finite bandwidth — creates the 1–6h diffusion window
5. As altcoin participants observe BTC and update, the altcoin price closes the gap

**Why BTC leads:**
- BTC has the deepest order books and tightest spreads of any crypto asset
- CME futures provide 24h institutional participation (processes macro news overnight)
- Grossman-Stiglitz (1980): acquiring information about 67 altcoins is costly; rational traders use BTC as a sufficient statistic for market-wide crypto sentiment
- Kyle (1985): the highest-liquidity asset processes market information first (best price discovery)
- Hou (2007): large-cap equities lead small-cap in incorporating market-wide information by up to 1 week; BTC-to-altcoin is the direct crypto analogue

---

## State Dependence and Admissibility

H2 is admissible only when:
1. BTC has made a **non-trivial directional move** (providing the information event to diffuse)
2. The altcoin has **not yet fully repriced** (divergence window is open)
3. BTC's move is **not immediately reversed** (hazard: if BTC overshoots and corrects, Δᵢ becomes misdirected)

Not admissible:
- BTC flat (no information event → no diffusion to exploit)
- BTC volatile and directionless (chop → signal degrades)
- Altcoin-BTC correlation collapsed (alt-season regime → mechanism breaks)
- High hazard (LSI > 0.60) — information events causing BTC to move strongly also carry high reversal risk

**Relationship to H1:** Both mechanisms can be active simultaneously, but they target different components of the return:
- H1 selects laggards that have overshot downward (corrective flow upward)
- H2 selects laggards that have not yet tracked BTC's upward move (catch-up flow upward)
In an uptrend where BTC moves up and some altcoins lag, BOTH H1 and H2 identify the same laggards — but for different reasons. The portfolio aggregation layer resolves this overlap.

---

## Economic Theory

**Kyle (1985, Econometrica) — Sequential information arrival:**
Informed traders arrive sequentially; the most liquid asset processes market-wide information first. BTC is the most liquid crypto asset on every venue; macro news hits BTC-USD before any altcoin pair.

**Grossman & Stiglitz (1980, American Economic Review) — Rational inattention:**
Acquiring and processing information about 67 altcoins is costly. Rational traders use BTC as a sufficient statistic for market-wide crypto sentiment, checking altcoin-specific prices only after BTC has repriced. This delay creates the diffusion window our signal exploits.

**Hou (2007, Review of Financial Studies) — Lead-lag in equity markets:**
Large-cap US stocks lead small-cap stocks by up to 1 week in incorporating market-wide information. BTC-to-altcoin is the direct crypto analogue: BTC (largest cap, deepest liquidity, highest institutional participation) leads all altcoins.

**Lo & MacKinlay (1990, Review of Financial Studies) — Non-synchronous trading:**
Returns of infrequently traded assets exhibit lead-lag relationships relative to frequently traded index components. Altcoin-USD pairs are less frequently observed/updated by market participants relative to BTC-USD.

---

## Current Proxy Status

**The mechanism is empirically CONFIRMED. The direct proxy FAILED.**

Mechanism confirmation (H2 mechanism test, `03_results/02_mechanism_test.md`):
```
IC of H1 signal conditioned on BTC move magnitude:
  BTC flat (|r_2h| < 0.5%):       IC = +0.024
  BTC large up (|r_2h| >= 1.5%):  IC = +0.110
  Uplift = +0.087 >> gate of 0.010
```

The H1 signal's alpha is 4.6× higher when BTC has moved significantly. This directly confirms the BTC-diffusion mechanism: information flows from BTC to altcoins, and the diffusion window is the source of H1's alpha.

**Why H2a proxy collapsed:**
`H2a = CS_z(alt_r_h − btc_r_h)`. In cross-sectional z-normalization, BTC return is a constant subtracted from every element before z-scoring. Constants cancel in z-normalization:

```
CS_z(alt_r − btc_r) = CS_z(alt_r − c) = CS_z(alt_r)  for any constant c
```

H2a is therefore **mathematically identical to H1** in the cross-sectional framework. This is not a data finding — it is a mathematical identity.

**Why H2b proxy failed:**
`H2b = lagged BTC return as market-timing predictor`. At 1h resolution, any predictive value from the previous hour's BTC return has already been arbitraged away within the same 1h kline aggregation. Pearson r ≈ −0.003 across all tested lags.

**Path forward (experimental):**
The correct H2 proxy must preserve BTC as a **non-constant** cross-sectional discriminator. Options:
1. **Raw divergence:** `signal_i = r_BTC − r_i` (unzscored — preserves BTC level)
2. **Beta-adjusted:** `signal_i = β_i · r_BTC − r_i` where β_i estimated from rolling 48h regression
3. **Conditional entry:** Use BTC move > threshold as an entry trigger (switches H1 from passive to active)

None of these have been validated. H2 remains experimental until a proxy with IC > 0 and t > 1.0 is found.

---

## Necessary Conditions

1. BTC leads altcoins in incorporating market-wide information (validated — IC uplift confirmed)
2. The diffusion window is long enough to exploit at hourly frequency (validated — IC decays over 1–4h not instantaneously)
3. A non-collapsed proxy for Δᵢ can be constructed (not yet validated — H2a collapses, H2b fails)
4. Altcoin-BTC correlation is positive and stable enough for signal to be directionally consistent

---

## Failure Modes

1. **Alt-season regime:** Altcoin-BTC correlation collapses; BTC is no longer the shared state variable. H2 mechanism breaks entirely. Requires correlation regime detection.

2. **BTC reversal within holding period:** If BTC overshoots and corrects within 4h, Δᵢ becomes misdirected. The BTC stability gate in the regime overlay (BTC gate in `bot/risk/kill_switch.py`) provides partial protection.

3. **Proxy collapse:** All H2a proxies are mathematical identities of H1 in cross-sectional space. Any H2 proxy must avoid cross-sectional normalization of the BTC-relative divergence.

4. **Beta instability:** The 48h rolling beta estimate will be noisy during regime transitions. Beta-adjusted proxies require stable correlation windows.

---

## Navigation

| Step | File |
|------|------|
| Proxy universe | [01_proxy_universe.md](01_proxy_universe.md) |
| Validation plan (IC conditioning test spec) | [02_validation_plan.md](02_validation_plan.md) |
| IC results (H2a collapse, H2b failure) | [03_results/01_ic_results.md](03_results/01_ic_results.md) |
| Mechanism test (BTC-conditional IC uplift) | [03_results/02_mechanism_test.md](03_results/02_mechanism_test.md) |
| Decision memo | [04_decision.md](04_decision.md) |
| H1 mechanism (the deployed signal) | [../H1_reversal/00_mechanism.md](../H1_reversal/00_mechanism.md) |
| Portfolio aggregation (how H1+H2 combine) | [../portfolio/01_signal_aggregation.md](../portfolio/01_signal_aggregation.md) |
