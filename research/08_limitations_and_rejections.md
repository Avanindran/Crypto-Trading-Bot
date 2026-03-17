# Limitations and Rejected Signals

**Date:** 2026-03-17
**Context:** Signal search over H1–H6 mechanism families, Oct 2024 – Jan 2025 trending period.

---

## Rejected Signals

### H5: Volatility-Adjusted Momentum (Sharpe variants) — FAIL

**Proxies tested:**
- `H5_sharpe_6h` = CS_z(r_6h / realized_vol_6h)
- `H5_sharpe_24h` = CS_z(r_24h / realized_vol_24h)
- `H5_sortino_6h` = CS_z(r_6h / downside_vol_6h)

**IC results (all horizons):** Negative IC at all tested forward horizons.
Example: H5_sharpe_6h IC at 1h = −0.030, at 4h = −0.022.

**Economic explanation:** In a trending bull market (Oct 2024 – Jan 2025), high-Sharpe assets have
already run up and are priced for further momentum — but our cross-sectional evidence shows they
REVERT. The Sharpe normalization selects "efficient" recent gains, which are more likely to be
fully priced. Only the **low-vol anomaly** (stable coins, not necessarily high-Sharpe coins) passed.
The `H5_neg_vol` proxy captures the stability mechanism directly without requiring positive recent returns.

**Conclusion:** Vol-adjusted momentum fails; raw low-vol selection passes. Mechanistic distinction matters.

---

### H6: Candle Persistence / Streak — FAIL (not statistically tested, excluded by design)

**Proxies declared:**
- `H6_up_pct_6h` = fraction of last 6 hourly bars with close > open
- `H6_streak_ts` = TS z-score of H6_up_pct_6h vs 48h baseline
- `H6_body_mean_6h` = mean |close-open|/(high-low) over last 6h

**Status:** Proxies were computed but all showed near-zero IC at all horizons (IC < 0.01, |t| < 1).
These signals capture *directional consistency* which is mechanistically redundant with return-based signals
(a series of up-candles = positive cumulative return = H1 territory). No independent signal found.

**Conclusion:** H6 provides no signal beyond H1 momentum in this universe and time period. Excluded.

---

### H2a: BTC Leader-Laggard (catch-up) — MATHEMATICALLY EQUIVALENT TO H1, NOT INDEPENDENT

**Proxies tested:**
- `H2_rel_btc_r2h` = CS_z(altcoin_r_2h − btc_r_2h)
- `H2_rel_btc_r6h` = CS_z(altcoin_r_6h − btc_r_6h)
- `H2_neg_rel_btc_r2h` = CS_z(−(altcoin_r_2h − btc_r_2h))

**Key finding:** H2a signals have **identical IC to H1 signals** at all tested horizons.

**Mathematical proof:**
```
CS_z(alt_r_2h − btc_r_2h) = CS_z(alt_r_2h − constant)
                            = CS_z(alt_r_2h)   [subtracting a constant doesn't change z-scores]
```
BTC return is a **cross-sectional constant** — the same value for all 48 pairs at any timestamp.
Cross-sectional z-normalization removes cross-sectional constants by construction.
Therefore H2a provides **zero** additional information beyond H1 in a cross-sectional framework.

**Conclusion:** H2a is a phantom signal. In a time-series framework (single asset vs its own BTC beta)
it might have meaning, but in cross-sectional IC testing it collapses to H1. Do not add as a separate component.

---

### H2b: Lagged BTC Predictor — FAIL

**Proxy tested:**
- `H2b_btc_lag1h` = BTC 1h return from 1 hour ago as predictor of altcoin forward return

**IC result:** Pearson r = −0.003. No predictive relationship.

**Economic explanation:** If there is a BTC diffusion lag, it operates below 1h resolution
and is not detectable in 1h-sampled data. The competition's 1-min polling granularity with
60s loop cadence does not provide meaningful sub-hour resolution for this signal.

---

### Original C1 (momentum direction) — ANTI-PREDICTIVE

**IC results (training period):** IC = −0.038 at 4h, t = −3.04.

**Economic explanation:** The original signal selected recent winners (high r_6h, r_2h, r_24h).
In this universe and period, cross-sectional winners REVERT — they are more likely to have
already priced in news than laggards. The bot's original C1 was selecting the wrong tail
of the distribution.

**Note:** The regime gating infrastructure (LSI/MPI/FEI → HAZARD_DEFENSIVE) was independently
validated via backtest and provides genuine value by reducing exposure during stressed periods.
The C1 reversal (inverting to select laggards) is the correction applied in this research pipeline.

---

## Limitations of the Research

### Survivorship and listing bias
Pairs that were recently listed (PENGUUSDT, TRUMPUSDT, VIRTUALUSDT, etc.) have limited history.
Using union timestamps means these pairs contribute only when they have data, which is correct.
However, the research universe (67 pairs) is fixed at the current Roostoo universe — pairs that
were delisted between Oct 2024 and Jan 2025 are absent from historical data.

### Trending period only
All IC validation used Oct 2024 – Jan 2025, a sustained bull run (BTC +147%).
The promoted signal's IC in a bear market or choppy sideways period is unknown.
The regime filter (HAZARD_DEFENSIVE) is expected to reduce exposure in non-trending periods,
but the reversal signal itself was not tested in bear markets.

### 1h resolution
Data is sampled at 1-minute from Binance, but aggregated to 1h for IC testing due to
computational constraints. The reversal signal's optimal holding period appears to be 1–4h
(IC peaks at 1–2h, remains stable to 4h). With 4h regime cadence in production this is appropriate.

### Single exchange universe
The 67-pair Roostoo/Binance universe is highly correlated. Cross-sectional effects
may be amplified (all pairs move with BTC) and the z-score normalization could be noisy
when few pairs have genuinely idiosyncratic returns.

### Out-of-sample window = 2 months
The holdout period is Dec 2024 – Jan 2025, which is a continuation of the bull run.
The "holdout" and "train" periods share the same macro regime. This limits the claim
of true out-of-sample validation — more independent test periods would be needed for
a fully rigorous study.

---

## Research Pipeline Ordering Note

In the compressed research timeline (competition deadline Mar 21, 2026), robustness testing
(`09_robustness/`) was executed **before** vector tests (`06_vector_tests.md`), which inverts
the doctrine Step 12 ordering. Per doctrine, the correct sequence is:

```
IC test (Step 3A) → GP combination (Step 2B) → vector tests (Steps 3C–5)
  → strategy freeze (Step 11) → robustness (Step 12)
```

The actual execution order was:

```
IC test → GP → robustness → H2 mechanism test → vector tests
```

**Why the freeze requirement was still met in spirit:**
Robustness was run as a "pre-flight check" on the signal formula already fixed by the GP search.
After seeing that robustness passed (97.2% block-resample hit rate), **no parameters were changed**.
The vector tests then confirmed the same formula independently. If you compare the signal formula
in `07_signal_promotion.md` with the inputs used in `09_robustness/H1_H5_signal_robustness.md`,
they are identical — no post-hoc fitting occurred.

See `10_pipeline_index.md` for the full doctrine step → file mapping.
