# H2 — Limitations and Open Problems

**Date:** 2026-03-17
**Status:** Mechanism confirmed; proxy pending. No live deployment.

---

## Known Failures

### 1. Proxy collapse in cross-sectional framework

All H2a proxies (CS_z(alt_r − btc_r)) are mathematical identities of H1 in cross-sectional z-normalization. This is not a data finding — it is a structural property of the CS_z framework.

**Why this matters:** Any H2 proxy formulated as `CS_z(f(alt_r, btc_r))` will collapse if `f` is a linear function with a btc_r term, because btc_r is cross-sectionally constant.

**Constraint on future proxies:** Valid H2 proxies must either:
- Avoid cross-sectional z-normalization entirely (use raw or time-series normalized signals), OR
- Include a nonlinear function of btc_r that creates genuine cross-sectional variation (e.g., β_i · r_BTC where β_i differs across assets)

### 2. No detectable lag at 1h resolution

H2b (lagged BTC return) has Pearson r ≈ 0. If the diffusion lag exists at sub-30-minute timescales, it is not measurable in 1h-aggregated data.

**Implication:** The bot's 60s polling loop with 1h kline aggregation may be too coarse to capture the BTC-diffusion transmission. The mechanism may operate primarily at 5–15 minute frequencies.

---

## Structural Open Problems

### 1. Beta instability

The beta-adjusted proxy `signal_i = β_i · r_BTC − r_i` requires a reliable estimate of β_i (the altcoin's BTC loading). Rolling 48h beta estimates will be:
- Noisy for pairs with thin order books (wide spreads → price-reporting lag)
- Unstable during regime transitions (alt-season, BTC dominance shifts)
- Biased upward when altcoin-BTC correlation is temporarily high due to a shared catalyst

**Resolution needed:** Test whether 48h rolling beta estimates are stable enough to produce reliable signal_i estimates. This requires ~200 hours of data per pair to estimate with reasonable precision.

### 2. Alt-season regime detection

The H2 mechanism assumes positive, stable BTC-altcoin correlation. In alt-season (when altcoins decouple from BTC), the mechanism breaks:
- βᵢ collapses toward zero for many altcoins
- r_BTC no longer serves as the primary information state variable
- Δᵢ = βᵢ · r_BTC − r_i becomes noise-dominated

**Resolution needed:** A correlation regime filter (30-day rolling altcoin-BTC correlation < threshold → H2 not admissible) would be required before H2 can be deployed safely.

### 3. BTC reversal risk

If BTC overshoots and corrects within the holding period, Δᵢ becomes misdirected. The BTC gate in `kill_switch.py` provides partial protection (emergency exit when BTC drops > 6%) but does not handle the case where BTC overshoots upward.

**Resolution needed:** A BTC momentum persistence filter — only deploy H2 when BTC's recent move appears directionally stable (MPI high, no immediate reversal pattern).

---

## Implications for Portfolio Architecture

Until a non-collapsed H2 proxy is implemented and validated:

1. The live bot runs H1 only
2. H2 mechanism conditioning is implicit through the regime overlay (BTC vol z-score in LSI)
3. The Δᵢ-based scoring is not used in position scoring

See [../portfolio/02_live_configuration.md](../portfolio/02_live_configuration.md) for current live state.

---

## Research Priority

H2 implementation requires two validated components before deployment:
1. A proxy that preserves Δᵢ structure without cross-sectional collapse (technical problem)
2. An alt-season/correlation regime detector (admissibility filter)

Neither component requires changes to the current live bot architecture. H2 can be added as an additional score component without modifying H1's regime gating or portfolio construction.

**Estimated work:** ~40h of research and testing. Out of scope for Round 1 deadline (Mar 28).
