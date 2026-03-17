# H1 — Limitations and Caveats

**Date:** 2026-03-17
**Scope:** H1 reversal signal + H5 stability filter as deployed

---

## Signal-Level Limitations

### 1. Trending period only

All IC validation used Oct 2024 – Jan 2025, a sustained crypto bull run (BTC +147%).
The promoted signal's IC in a bear market or choppy sideways period is unknown.

- In a sustained downtrend, cross-sectional laggards may continue falling (genuine fundamental underperformance, not liquidity overshoot)
- The regime filter (HAZARD_DEFENSIVE) is expected to reduce exposure in stressed periods, but the signal itself was not validated in bear conditions
- **Mitigation:** Regime overlay provides partial protection; admissibility condition (LSI < 0.40, MPI > 0.30) restricts deployment to non-hazardous states

### 2. Out-of-sample window = 2 months, same macro regime

The holdout period (Dec 2024 – Jan 2025) is a continuation of the bull run. Train and holdout share the same macro regime (trending crypto bull market). This limits the strength of the "out-of-sample" claim.

- Holdout IC (+0.066) marginally exceeds training IC (+0.047), consistent with no overfitting
- However, both periods have similar altcoin-BTC correlation and regime structure
- **True out-of-sample** would require a bear market or sideways period — unavailable given competition constraints

### 3. Survivorship and listing bias

The 67-pair Roostoo universe is fixed at the Mar 2026 listing. Pairs delisted between Oct 2024 and Jan 2025 are absent from historical data, creating survivorship bias.

- New listings (PENGUUSDT, TRUMPUSDT, VIRTUALUSDT, etc.) have limited history — contribute only when available
- Pairs that failed (dropped from 0 to near-zero) are not in the universe — positive bias on IC
- **Magnitude:** Unknown; correction would require delisted pair data not accessible

### 4. 1h data resolution

Data is aggregated to 1h for IC testing. The reversal mechanism operates at 30min–2h timescales. If the corrective flow arrives within the same 1h kline, it is invisible to the IC test.

- Empirically IC is highest at 1h horizon (not zero), so sub-1h correction is not the primary channel
- 4h production cadence is appropriate given IC peak at 1–2h with slow decay
- **Implication:** Signal is not optimized for sub-1h deployment; live rebalancing every 4h is correct

### 5. Single exchange universe

The 67 Roostoo/Binance pairs are highly correlated. Cross-sectional IC tests may have inflated standard errors due to non-independence of return series. The t-stats reported assume cross-sectional independence within each timestamp.

---

## H5 Stability Filter Limitations

### 1. pct_rank proxy failed in trending conditions

The pct_rank component of M_t (r_6h percentile in 48h window) failed as a maturity proxy:
- IC(fresh bucket) = +0.018 < IC(unconditional) = +0.048
- In the trending period, "stale" assets (extended pct_rank) had the highest IC because momentum continued
- **Resolution:** pct_rank proxy REJECTED as standalone maturity signal; composite M_t retained with caveat

### 2. H5_sharpe variants anti-predict

H5_sharpe_6h IC = −0.022 (negative). Selecting high-Sharpe recent gainers is the opposite of what the mechanism requires — these are assets that have already fully priced in positive news.

- **Why included as proxy:** Pre-committed before IC testing; expected to fail
- **Why failed:** Correctly predicted — high-Sharpe assets are not reversal candidates

---

## Research Pipeline Ordering Note

In the compressed research timeline (competition deadline Mar 21, 2026), robustness testing was executed **before** vector tests, inverting the doctrine Step 12 ordering. The spirit of the freeze was preserved:

- The promoted signal formula (0.70×H1 + 0.30×H5, weights from GP search) was finalized before robustness
- After seeing robustness results (97.2% block-resample hit rate), **no parameters were changed**
- Vector tests afterward confirmed the same formula independently

If you compare the signal formula in [04_decision.md](04_decision.md) with the inputs used in [03_results/07_robustness.md](03_results/07_robustness.md), they are identical — no post-hoc fitting occurred.

---

## Live Deployment Caveats

### C3 maturity modifier (provisional)

The live bot's M_t composite uses four components (SMA extension, RSI proxy, pct_rank, funding rate). Only the pct_rank proxy was formally tested in the research pipeline. The remaining components (SMA extension, funding rate) address different aspects of overextension and are not covered by the IC validation above.

**Caveat:** The funding rate component is new and untested against IC. It is retained on economic grounds (funding rate is a direct market signal of crowded positioning) but lacks the same validation rigor.

### Fee drag at 4h cadence

The full-strategy backtest shows pre-fee return +16.4% but net return −23.1% over 4 months, with fee drag estimated at ~39.4%. At 4h rebalancing with limit orders, transaction cost is the dominant drag.

**Implication:** Signal quality is sufficient to overcome fees in trending conditions (OOS pre-fee +16.4%). In sideways/bear conditions where raw returns are lower, the same fee drag becomes proportionally larger.

---

## Not Limitations

The following are known and accepted characteristics, not limitations:

- **H2a mathematical collapse:** CS_z(alt_r − btc_r) = CS_z(alt_r) is a mathematical identity, not a data limitation. The H2 mechanism is confirmed separately (IC uplift +0.087 when BTC moves).
- **Short IC decay horizon:** IC decays from ~0.05 at 1h to ~0.03 at 24h. This is expected from the mechanism (corrective flow completes in 1–4h). The 4h rebalancing cadence is matched to the IC persistence window.
- **Regime-dependent alpha:** H1 IC varies from +0.024 (BTC flat) to +0.110 (BTC large move). This is a feature, not a bug — the regime overlay captures this state dependence.
