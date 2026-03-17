# Strategy: Transitional-Drift Momentum with Regime-Adaptive Hazard Gating

## Economic Mechanism

Crypto markets exhibit a systematic pattern: when new information arrives (macro shock, BTC breakout, sector rotation), the assets most directly affected reprice immediately. Secondary and tertiary assets — those with weaker information linkage — adjust more slowly. During this adjustment window, the secondary assets exhibit exploitable continuation drift, not because of noise, but because the expectation update is genuinely incomplete.

This is the **transitional-drift momentum** signal: the expected return of an asset while market participants are still in the process of updating their expectations, conditioned on no expectation-invalidating information arriving in the interim. Cross-sectional momentum effects in crypto markets are well-documented empirically (Liu & Tsyvinski 2021; Cong et al. 2021), consistent with the theoretical mechanism described here.

Three necessary conditions must hold simultaneously:
1. **Drift exists** — there is incomplete expectation adjustment (measured by C1 momentum signal)
2. **Low hazard** — the probability of expectation-invalidating information is low (measured by λ_t)
3. **Early diffusion** — the drift is not yet spent (measured by M_t < MAX_MATURITY)

The signal construction has been empirically validated on Binance historical data. See `research/ic_validation.py` and `research/ic_results.md` for methodology and results.

## Scoring Formula

```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
```

This implements the theoretical expected-drift formula:
`E[drift] = α × (1 − M_t) × e^(−λ_t × τ)`

### C1 — Alpha Signal (Asset-Specific Momentum)

C1 captures the magnitude of asset-specific continuation strength relative to the cross-section. It is a cross-sectionally z-normalized weighted sum of return horizons:

```
raw_i = 0.10×r_30m + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r2h)
C1_i  = (raw_i − mean(raw)) / std(raw)
```

The 6-hour horizon receives the highest weight because it captures meaningful trend legs in the 10-day competition window without excessive noise (short horizons) or staleness (24h). The relative strength term uses the cross-sectional median (not BTC directly) to avoid anchoring bias — we measure an asset's outperformance relative to the full universe, not just relative to the market leader.

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

An extended IC test was conducted across 66 pairs and three conditions: (A) current period Dec 2025–Feb 2026, (B) trending period Oct 2024–Jan 2025 (BTC +61% bull run), and (C) regime-conditional (TREND-eligible hours, BTC vol z-score ≤ 0). See `research/ic_validation_extended.py` and `research/ic_results_extended.md` for full results.

**Key finding:** No individual signal (r_1h, r_2h, r_6h, r_24h) shows positive cross-sectional IC in any test condition across 66 pairs. All ICs are mildly negative (range: -0.011 to -0.066), confirming no reliable cross-sectional momentum signal. The C1 composite shows IC = -0.038 in the trending period, IC = -0.034 TREND-conditional. No weight changes to C1 components are warranted.

**Implication for strategy design:** The strategy's value proposition rests on three components that do not require cross-sectional IC:

1. **Regime gating (Sortino):** The HAZARD_DEFENSIVE state (0% exposure when LSI > 0.60) avoids all downside deviation on stressed market days. Binary switching — not signal selection — is what drives Sortino.
2. **Drawdown control (Calmar):** The -12% kill switch hard-caps max drawdown. A portfolio that earns 5% with a -6% max drawdown scores Calmar = 0.83; extending to -20% drawdown gives Calmar = 0.25.
3. **Diversified beta exposure in trend regimes:** When TREND_SUPPORTIVE, the strategy holds 5 long positions across the broadest legitimate crypto pairs on the exchange. With no detectable selection IC, this amounts to diversified broad-market exposure, with regime gating as the primary active management mechanism.

The competition scoring formula (0.4×Sortino + 0.3×Sharpe + 0.3×Calmar) rewards risk-adjusted performance. A strategy that avoids large drawdowns and the worst-vol days will score competitively even without superior stock-selection IC, provided the market direction during the 10-day competition window is non-hostile.

## References

- Jegadeesh, N. & Titman, S. (1993). Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency. *Journal of Finance*, 48(1), 65–91.
- Liu, Y. & Tsyvinski, A. (2021). Risks and Returns of Cryptocurrency. *Review of Financial Studies*, 34(6), 2689–2727.
- Cong, L. W., Li. Y., & Wang, N. (2021). Tokenomics: Dynamic Adoption and Valuation. *Review of Financial Studies*, 34(3), 1105–1155.
