# H2 — Limitations and Open Problems

**Date:** 2026-03-17
**Status:** H2c (beta-adjusted gap) PROMOTED and DEPLOYED. Limitations below remain valid for the deployed proxy.

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

H2c (`CS_z(β_i · r_BTC,2h − r_i,2h)`) is DEPLOYED via continuous allocation. How the known limitations are addressed in the live implementation:

1. **Beta instability** — mitigated by 48h rolling OLS window (H2C_BETA_WINDOW=48) and H2C_BETA_MIN_OBS=24 minimum observations before beta is used
2. **Alt-season risk** — mitigated by stress_decay factor: `max(0, 1 − vol_z / 2.0)` — when correlation spikes (vol_z ≥ 2σ), H2C capital fraction decays to 0
3. **BTC reversal risk** — mitigated by BTC reversal exit rule: exit H2C position if BTC 2h return drops below −1% (H2C_BTC_REV_EXIT=−0.01)

See [../portfolio/02_live_configuration.md](../portfolio/02_live_configuration.md) for current live state.

---

## Research Priority — Resolved

Both deployment prerequisites were resolved before Round 1:
1. **Non-collapsed proxy** — H2c (beta-adjusted gap `CS_z(β_i · r_BTC,2h − r_i,2h)`) satisfies this: β_i varies per asset, surviving CS normalization. IC=+0.042 @ 1h (t=+9.85). See `02_Candidates/Strategy/01_backtest.md`.
2. **Admissibility filter** — stress_decay and btc_activity factors in the continuous allocation formula act as the regime detector: H2C capital fraction scales to 0 when market is stressed or BTC is flat.

**Deployed:** H2c live in `bot/strategy/h2_signals.py` + `bot/strategy/engine_aggregator.py`. Portfolio result: Sortino=3.30, Calmar=19.22, OOS Sortino=1.40 (Section [G]).
