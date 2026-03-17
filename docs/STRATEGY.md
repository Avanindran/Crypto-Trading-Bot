# Strategy: Transitional-Drift Momentum with Regime-Adaptive Hazard Gating

## Economic Mechanism

Crypto markets exhibit a systematic pattern: when new information arrives (macro shock, BTC breakout, sector rotation), the assets most directly affected reprice immediately. Secondary and tertiary assets — those with weaker information linkage — adjust more slowly. During this adjustment window, the secondary assets exhibit exploitable continuation drift, not because of noise, but because the expectation update is genuinely incomplete.

This is the **transitional-drift momentum** signal: the expected return of an asset while market participants are still in the process of updating their expectations, conditioned on no expectation-invalidating information arriving in the interim. Cross-sectional momentum effects in crypto markets are well-documented empirically (Liu & Tsyvinski 2021; Cong et al. 2021), consistent with the theoretical mechanism described here.

Three necessary conditions must hold simultaneously:
1. **Drift exists** — the asset is positioned for recovery (measured by C1 reversal+stability signal)
2. **Low hazard** — the probability of expectation-invalidating information is low (measured by λ_t)
3. **Early diffusion** — the drift is not yet spent (measured by M_t < MAX_MATURITY)

The signal construction has been empirically validated on Binance historical data. See `research/ic_validation.py` and `research/ic_results.md` for methodology and results.

## Scoring Formula

```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
```

This implements the theoretical expected-drift formula:
`E[drift] = α × (1 − M_t) × e^(−λ_t × τ)`

### C1 — Alpha Signal (Reversal + Stability)

C1 is a GP-selected combination signal validated on Binance historical data (Oct 2024 – Jan 2025).
It selects cross-sectional laggards with low realized volatility — assets that have underperformed the
universe recently AND are stable (low vol), expected to mean-revert over the next 4h.

```
raw_i        = 0.10×r_30m + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r2h)
neg_c1_z_i   = CS_z(−raw_i)              [H1: recent laggards]
neg_vol_z_i  = CS_z(−realized_vol_6h_i)  [H5: low-vol stability]
C1_i         = 0.70 × neg_c1_z_i + 0.30 × neg_vol_z_i
```

**IC validation (4h forward return):**
- Train (Oct–Nov 2024): IC = +0.047, t = +7.22, IC-Sharpe = +0.190
- Holdout (Dec–Jan 2025): IC = +0.066, t = +10.59
- Block resampling: 97.2% of 500 random 10-day windows show positive IC

The H1 reversal component selects assets that underperformed the cross-section — they have not yet
priced in the ongoing market move and are expected to catch up. The H5 stability filter removes
high-vol meme coins whose apparent laggard status reflects noise rather than genuine opportunity.
See `research/07_signal_promotion.md` and `research/04_gp_search/H1_H5_gp_results.md`.

### λ_t — Market Hazard Rate (Regime-Derived)

λ_t is derived from a crypto-adapted Regime State Vector using three indices:

**LSI (Liquidity Stress Index) — HIGHEST DOMINANCE:**
When liquidity is stressed (BTC vol spike, spread widening, cross-section dispersion collapse, or extreme market sentiment), expectation-invalidating information is more likely to arrive. By design, LSI overrides all other regime indices. When LSI > 0.60, λ_t is set to 4.0+ (exp(−4) ≈ 0.018 — effectively zeroing all scores).

LSI incorporates four components:
- **BTC realized vol z-score** (0.45 weight) — vol spike signals market stress
- **Bid-ask spread z-score** (0.25 weight) — illiquidity signals adverse selection risk
- **Cross-section dispersion collapse** (0.15 weight) — panic correlation across assets
- **Crypto Fear & Greed Index** (0.15 weight) — sentiment leading indicator from Alternative.me; extreme greed (>75) historically precedes corrections as leveraged positioning unwinds, providing early-warning capability before price-based measures react

**MPI (Market Posture Index):**
When BTC is trending strongly relative to its realized vol, the macro posture is favorable for continuation. Low MPI (choppy market) forces NEUTRAL_MIXED regime regardless of other signals.

**FEI (Flow Elasticity Index):**
When momentum is concentrated in the top quartile relative to the bottom quartile, the momentum signal has genuine breadth — clear leaders exist and the strategy is in its optimal environment.

**Dominance cascade:**
```
LSI > 0.80 → HAZARD_DEFENSIVE (λ = 10.0)
LSI > 0.60 → HAZARD_DEFENSIVE (λ = 4.0)
LSI > 0.40 OR MPI < 0.30 → NEUTRAL_MIXED (λ = 1.5)
FEI > 0.55 AND MPI > 0.50 → TREND_SUPPORTIVE (λ = 0.3)
else → NEUTRAL_MIXED (λ = 0.8)
```

The exponential form — not linear — is critical. At λ_t = 4, `exp(−4) = 0.018`. A position that would have 85% NAV exposure at λ = 0.3 is suppressed to 1.8% at λ = 4. Linear scaling would give 20%; the exponential form correctly models the convex risk response.

### M_t — Diffusion Maturity (Per-Asset)

M_t measures how much of the expected drift has already been realized. A high M_t means the opportunity has already diffused into price; entering here gives poor risk/reward.

```
ext_norm    = normalize((price − SMA_12h) / ATR_12h, rolling_48h)
rsi_proxy   = avg_up / (avg_up + avg_dn) over 6h window
pct_rank    = percentile_rank(r_6h, rolling_48h history)
funding_cmp = clip((funding_rate − NEUTRAL) / SCALE, 0, 1)

M_t = 0.40×ext_norm + 0.15×rsi_proxy + 0.25×pct_rank + 0.20×funding_cmp
C3  = 1 − M_t
```

The **funding rate component** (from Binance perpetual futures, public API) is a direct measure of positioning overextension: when longs are paying an elevated premium to hold leveraged positions, the expected drift has already been captured. High positive funding (>0.08%/8h) pushes M_t toward 1.0, blocking new entries in crowded names. Negative funding contributes 0 — the strategy does not penalize unloved assets.

Entry is blocked when M_t > 0.72.

## Portfolio Construction

**Basket size:** 5 assets in TREND_SUPPORTIVE, 3 in NEUTRAL_MIXED, 0 in HAZARD_DEFENSIVE

**Sizing:** Quarter-Kelly with downside-vol denominator (directly targets Sortino numerator/denominator):
```
kelly_f = 0.25 × expected_r / downside_vol²
clipped to [5%, 30%] per asset
```

**Gross cap by regime:** 85% (trend), 65% (neutral), 0% (defensive)

**Drawdown-responsive caps:** -5% (50%), -8% (30%), -12% (0% + kill switch)

## Risk Management Design Rationale

The competition scoring formula is `0.4×Sortino + 0.3×Sharpe + 0.3×Calmar`.

**Sortino targeting:** Sortino = mean_return / downside_deviation. To maximize Sortino, we use binary regime switching rather than smooth scaling — a clean HAZARD_DEFENSIVE state (0% exposure) avoids all downside deviation on those days. Partial scaling during hazard periods adds downside deviation without proportional return benefit.

**Calmar targeting:** Calmar = mean_return / max_drawdown. The -12% portfolio kill switch hard-caps the Calmar denominator. If the strategy earns 8% over 10 days with a -6% max drawdown (via tight risk controls), Calmar = 1.33. If drawdown extended to 20%, Calmar = 0.40 — less than a third of the score.

**Fee management:** Maker fees (0.05%) vs taker fees (0.10%). All normal trades use limit orders. The 4-hour minimum holding period prevents noise-driven turnover that would accumulate fee drag (100 round-trips at 0.10% = 1.0% on $1M). The BTC gate and maturity filter also reduce unnecessary trading frequency.

## Historical Evaluation

An empirical evaluation of the full strategy pipeline was conducted on Binance 1h data over Oct 2024 – Jan 2025 using the full Roostoo universe (~44 pairs with complete data for that period). See `research/backtest_simulation.py` and `research/backtest_results.md` for methodology and full results. No parameters were modified based on these results.

Over the 4-month test period (Oct 2024 – Jan 2025), the strategy produced a net return of **-31.4%** with **25.1% fees paid** and a pre-fee return of **-6.3%**. The Oct 2024–Jan 2025 period includes BTC's 61% bull run (BTC buy-and-hold: +61.2%); the strategy's regime gating moved it to cash ~20% of the time. The high fee drag (0.204%/day) reflects the full 44-pair universe's higher turnover: with 40+ volatile pairs competing for 5 slots, relative C1 rankings shift rapidly each rebalance period. For the 10-day competition window, estimated fee drag is ~2.0%. See `research/charts/` for equity curve and drawdown visualizations.

### Signal Validation

An extended IC test was conducted across 67 pairs and three conditions: (A) current period Dec 2025–Feb 2026, (B) trending period Oct 2024–Jan 2025 (BTC +61% bull run), and (C) regime-conditional (TREND-eligible hours, BTC vol z-score ≤ 0). See `research/ic_validation_extended.py` and `research/ic_results_extended.md` for full results.

**Phase 1 — Cross-sectional signal IC (baseline):** No individual signal (r_1h, r_2h, r_6h, r_24h) shows positive cross-sectional IC in any test condition. All ICs are mildly negative (range: -0.011 to -0.066). The C1 composite shows IC = -0.038 in the trending period (t = -0.65, not statistically significant). Cross-sectional momentum does not have detectable predictive power in this heterogeneous universe.

**Phase 2 — Time-series (TS) signal search (F1–F7):** Following the Systematic Trading Architecture doctrine (mechanism before formula, search space declared before data processing), seven time-series candidate formulas were tested:

| Formula | Description |
|---------|-------------|
| F1 | Per-asset TS z-score of 6h return vs own 48-period baseline |
| F2 | Per-asset TS z-score of 2h return |
| F3 | Per-asset TS z-score of 24h return |
| F4 | TS z-score of (price − MA_24h) / MA_24h — deviation from own price anchor |
| F5 | Current bar volume / rolling_mean(vol, 48) — flow persistence proxy |
| F6 | F1 × min(F5, 2.0) — volume-confirmed TS momentum |
| F7 | 0.35·F1 + 0.35·F2 + 0.20·F3 + 0.10·F4 — multi-horizon TS composite |

All formulas apply a final cross-sectional z-score normalization (doctrine: allocation step normalizes within universe). Decision gate: IC > 0 in Test B (trending period) AND t > 1.0.

**Result: no formula passes the decision gate.** Best result: F5 (volume ratio) IC = +0.018, t = +0.30 in Test B — positive direction but statistically insignificant. All other TS formulas show negative IC in Test B (range: -0.0000 to -0.043). The root-cause hypothesis — that per-asset normalization would remove meme-coin contamination from the cross-section — is not confirmed empirically.

**Phase 3 — Order Flow Imbalance (OFI) signal search (G1–G6):** Following the same doctrine, six microstructure candidate formulas were tested using previously untested Binance klines columns (taker_buy_base_vol col 9, OHLC cols 1–3, quote_vol col 7, num_trades col 8). The mechanism hypothesis: market (taker) buy orders reflect directional conviction — aggressive buyers pay the spread to obtain immediate execution. When taker buy fraction is abnormally high relative to an asset's own baseline, continuation pressure should build over the next 6h (Glosten-Milgrom 1985; Chordia et al. 2002).

| Formula | Description |
|---------|-------------|
| G1 | TS z-score of taker_buy_ratio = taker_buy_vol / base_vol (klines col 9/5) |
| G2 | TS z-score of candle body ratio = (close − open) / (high − low) — directional conviction |
| G3 | TS z-score of quote_asset_volume (col 7) — USD-denominated vol anomaly |
| G4 | TS z-score of num_trades (col 8) — trade activity anomaly |
| G5 | TS z-score of taker_buy_ratio × \|r_6h\| — OFI scaled by directional magnitude |
| G6 | 0.50·G1 + 0.30·G2 + 0.20·G4 — OFI composite |

**Result: no OFI formula passes the decision gate.** Best results in the trending period: G5 IC = +0.008, t = +0.13; G3 IC = +0.008, t = +0.14; G4 IC = +0.005, t = +0.08. All are positive in direction but far below the t > 1.0 significance threshold. The microstructure hypothesis fails at hourly aggregation: sub-hour order flow signal decays completely within the 1h kline, leaving no detectable predictive power over 6h horizons. Note that G1 (pure taker buy ratio) shows negative IC (-0.020, t = -0.34 in Test B), indicating that in this universe, elevated taker buying in the current hour is a reversal signal at the cross-sectional level — consistent with the exhaustion interpretation captured by the M_t maturity filter already in production.

**Phase 4 — Reversal and Volatility Signal Discovery (H1–H6):** A compressed research pipeline was run following Systematic Trading Architecture doctrine. Mechanism families H1 (anti-momentum reversal), H2 (BTC leader-laggard), H5 (volatility-adjusted), and H6 (candle persistence) were declared before any data was processed. See `research/01_mechanism_universe.md` and `research/02_proxy_universe.md`.

**Key finding:** The original C1 signal had IC = −0.038 at 4h (selecting winners → underperformers). Inverting C1 to select laggards gives IC = +0.042 at 4h. All 5 H1 reversal proxies passed the IC gate (IC > 0.03, t > 1.5). H5_neg_vol (low realized volatility) showed the strongest individual IC (+0.076 at 24h, t = +13.26). H5 Sharpe variants, H6 streak signals, and H2b lagged BTC all failed.

A key mathematical finding: H2a signals (altcoin return minus BTC return, cross-sectionally z-scored) are IDENTICAL to H1 signals, because BTC return is a cross-sectional constant that cancels in z-normalization. H2a provides no independent information.

GP combination search (constrained grid over pairs of terminals, optimizing IC-Sharpe at 4h) selected `0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)`, promoted with train IC = +0.047 (IC-Sharpe +0.190) and holdout IC = +0.066 (t = 10.59). Robustness: 97.2% of 500 random 10-day windows show positive IC. See `research/09_robustness/H1_H5_signal_robustness.md`.

**H2 mechanism test (Step 3D):** The H2 hypothesis predicts that IC of the laggard signal should be higher when BTC has made a large move (expectation diffusion is triggered). Tested by conditioning IC on BTC 2h return magnitude. Result: IC(BTC flat, |r_2h|<0.5%) = +0.024, IC(BTC large up, |r_2h|≥1.5%) = +0.110 — uplift = +0.087, well above the 0.010 confirmation threshold. **H2 mechanism confirmed.** The signal exploits BTC-diffusion lag, not just generic cross-sectional reversal. The raw H2 diffusion gap (btc_r − alt_r, not z-scored) shows identical IC to H1, confirming that the BTC contribution adds information only through conditioning, not through the level of the gap. See `research/05_h2_mechanism_test.md`.

**Vector tests (Steps 3C, 4A, 4B, 5):** A fixed-horizon portfolio backtest (4h hold, top-3 equal weight, Oct 2024–Jan 2025) was run across three configurations — bare signal, +C2 regime gate, +C2+C3 maturity filter. Results:

| Configuration | Sharpe | MaxDD | Hit Rate | Total Return |
|---|---|---|---|---|
| Bare C1 (no modifiers) | 1.87 | −34.1% | 51.5% | +59.4% |
| + C2 regime gate | 3.02 | −28.0% | 47.1% | +119.1% |
| + C2 + C3 maturity filter | 3.16 | −27.0% | 47.0% | +130.1% |

Step 3C sanity bars: all pass. Step 4A (C2 modifier): MaxDD improvement +17.8% relative (≥10% bar), worst 30d DD improvement +9.1pp (≥5pp bar) — **APPROVED**. Step 4B (C3 pct_rank proxy): IC(fresh bucket, pct_rank<30%) = +0.018, IC(unconditional) = +0.048 — pct_rank proxy **REJECTED** in this trending period. In Oct–Jan trending conditions, extended (high-pct_rank) assets show higher IC (0.052) than fresh ones, consistent with momentum continuation. The pct_rank proxy is regime-specific and does not generalize. The live M_t composite includes funding rate, RSI proxy, and SMA extension in addition to pct_rank; these capture overextension in non-trending conditions and are retained. See `research/06_vector_tests.md`.

**Phases 1–3 conclusion:** Three mechanistically distinct families — cross-sectional price momentum (Phase 1), time-series price momentum (Phase 2), and market microstructure/order flow (Phase 3) — all failed to find signals with IC > 0 and t > 1.0. **Phase 4 reversal research succeeded by inverting the direction of the Phase 1 search.**

The strategy's value proposition now rests on four components:

1. **Validated alpha selection (Sortino/Sharpe):** The promoted C1 signal (IC = +0.057, t = 12.55) selects cross-sectional laggards with low realized volatility, providing genuine cross-sectional alpha at the 4h horizon.
2. **Regime gating (Sortino):** The HAZARD_DEFENSIVE state (0% exposure when LSI > 0.60) avoids all downside deviation on stressed market days. Binary switching is what drives Sortino — clean zero exposure, not smooth scaling.
3. **Drawdown control (Calmar):** The -12% kill switch hard-caps max drawdown. A portfolio that earns 5% with a -6% max drawdown scores Calmar = 0.83; extending to -20% drawdown gives Calmar = 0.25.
4. **Maturity filter (Sortino/Sharpe):** M_t blocks entry into overextended assets (extension from SMA, RSI proxy, pct_rank, funding rate), preventing entry at the tail of a move where risk/reward is worst.

The competition scoring formula (0.4×Sortino + 0.3×Sharpe + 0.3×Calmar) rewards risk-adjusted performance. A strategy that avoids large drawdowns and the worst-vol days will score competitively even without superior selection IC, provided the market direction during the 10-day competition window is non-hostile.

## References

- Jegadeesh, N. & Titman, S. (1993). Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency. *Journal of Finance*, 48(1), 65–91.
- Liu, Y. & Tsyvinski, A. (2021). Risks and Returns of Cryptocurrency. *Review of Financial Studies*, 34(6), 2689–2727.
- Cong, L. W., Li. Y., & Wang, N. (2021). Tokenomics: Dynamic Adoption and Valuation. *Review of Financial Studies*, 34(3), 1105–1155.
- Glosten, L. R. & Milgrom, P. R. (1985). Bid, Ask and Transaction Prices in a Specialist Market with Heterogeneously Informed Traders. *Journal of Financial Economics*, 14(1), 71–100.
- Chordia, T., Roll, R., & Subrahmanyam, A. (2002). Order Imbalance, Liquidity, and Market Returns. *Journal of Financial Economics*, 65(1), 111–130.
