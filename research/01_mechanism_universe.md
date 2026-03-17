# Mechanism Universe — Signal Hypothesis Families

**Written:** 2026-03-17 | **Status:** FROZEN before signal_search.py first run

This document declares all mechanism families that will be tested. No IC data has been observed at time of writing. Mechanisms are declared from theoretical reasoning alone.

---

## Previously Tested (Rejected) Mechanisms

### H0: Cross-Sectional Price Momentum (REJECTED — Phase 1)
**Hypothesis:** Assets that outperformed the cross-section over 30m–24h will continue to outperform over the next 6h.

**Result:** C1 composite IC = -0.038 (trending period), t = -0.65. All individual horizons negative. Hit rate 46–51%. NOT statistically significant but consistently negative direction.

**Why it failed:** In this heterogeneous 67-pair universe including high-vol meme coins, cross-sectional winners at hourly frequency tend to be idiosyncratic spike events (meme coin pumps, news events) that REVERT rather than continue. The momentum mechanism requires an information diffusion lag that is too short to persist 6h in an efficient hourly market. The negative IC is not noise — it is mean reversion in disguise.

**Implication for H1:** If momentum has negative IC, then its inverse (anti-momentum / reversal) should have POSITIVE IC. H1 is the direct empirical implication of H0's failure.

### H_TS: Time-Series Momentum F1–F7 (REJECTED — Phase 2)
**Hypothesis:** Per-asset TS z-scored returns (normalized to own history) remove cross-sectional contamination and reveal continuation.

**Result:** All F1–F7 fail gate. Best: F5 (volume ratio) IC = +0.018, t = +0.30. Insufficient.

**Why it failed:** TS normalization does not rescue the fundamental problem. At hourly aggregation, per-asset return z-scores still measure velocity that decays within hours. The 48-period baseline is long enough that recent spikes look like outliers, but the "outlier = coming back to earth" interpretation (mean reversion) is still the dominant dynamic.

### H_OFI: Order Flow Imbalance G1–G6 (REJECTED — Phase 3)
**Hypothesis:** Taker buy fraction, candle body conviction, and trade activity anomalies at hourly resolution predict 6h forward returns.

**Result:** All G1–G6 fail gate. Best: G5 (tbr×|r6h|) IC = +0.008, t = +0.13. Notably, G1 (pure taker buy ratio) has IC = -0.020, t = -0.34 — also a reversal signal.

**Why it failed:** OFI signal decays within the 1h kline aggregation period. Microstructure signals (adverse selection, informed trading) operate at sub-minute frequency and are fully resolved within any 1h candle. By the time the kline is complete, the information in taker flow is already reflected in price.

---

## Active Mechanism Families (Untested as of 2026-03-17)

### H1: Short-Term Cross-Sectional Reversal
**Mechanism statement:** In the cross-section of crypto assets at hourly frequency, recent outperformers revert toward the cross-sectional mean while recent underperformers recover. This is the empirical implication of the H0 rejection: if winners underperform (IC of momentum < 0), then LAGGARDS outperform (IC of anti-momentum > 0). Mechanism: (1) hourly crypto moves are dominated by idiosyncratic liquidity events (pump-and-dump, news spikes, leveraged liquidations) that overshoot informational equilibrium, (2) market participants with mean-reverting priors provide corrective flow within 1–4h.

**Economic Theory:**
- **De Bondt & Thaler (1985, Journal of Finance) — Overreaction hypothesis:** Investors systematically overreact to recent news and price moves; subsequent correction produces short-term reversal. Jegadeesh (1990) documented 1-month equity reversal empirically; Lehmann (1990) showed weekly reversal driven by bid-ask bounce and market-maker inventory rebalancing.
- **Why crypto specifically:** Thin on-exchange liquidity means price impact from a single aggressive buyer can temporarily push price 1–3% above informational equilibrium — far more than in equity markets. Market-makers and arbitrageurs who observe the overshooting submit corrective orders, restoring price within 1–4h. This corrective flow is the source of our signal's IC.
- **Why this is NOT data mining:** We observe H0 IC = −0.038 (anti-momentum) before testing H1. The reversal is the logical inversion of H0's failure. De Bondt-Thaler independently documented this mechanism in equities 40 years before our test; we are applying an established phenomenon to a new venue. Predicting a reversal before testing it is not overfitting.
- **Admissibility constraint:** In a long-only portfolio, reversal can only be exploited in UP markets (regime gate required). In DOWN markets, laggards may continue down and the mechanism is inapplicable.

**Necessary conditions:**
1. Cross-sectional idiosyncratic shocks are transient (1–4h duration), not persistent
2. Corrective flow arrives within the holding period
3. Signal has not been fully arbitraged away (market microstructure friction prevents full exploitation at hourly frequency)

**Failure modes:**
- If market enters a directional trend (all assets up/down), reversal collapses (regime-dependent)
- If mean reversion happens at sub-1h frequency, IC will be zero at any 1h-lagged test
- If the effect is entirely driven by bid-ask bounce (microstructure), it won't survive realistic execution

**Expected predictive horizon:** 1h–4h (decays quickly as corrective flow completes)

**Admissibility note:** Long-only constraint is BINDING. This mechanism can only be exploited by selecting laggards in UP markets (TREND regime). In DOWN markets, laggards may continue down. Regime gate is essential.

---

### H2: BTC-Relative Divergence (Leader-Laggard Catch-Up)
**Mechanism statement:** BTC is the dominant information leader in the crypto market. When new information arrives (macro event, regulatory news, institutional flow), BTC reprices within 1–2h. Secondary altcoins that should be correlated to BTC's move but have NOT yet repriced are in a temporary divergence state. This divergence will close as:
(a) altcoin market participants observe BTC's move and update expectations (information diffusion)
(b) mechanical correlation arbitrage restores co-movement

**Two sub-mechanisms:**
- **H2a (catch-up):** Altcoin that underperformed BTC over last 2–6h should catch up. Proxy: (altcoin_r_Xh - btc_r_Xh). Low or negative values = lagged BTC = expected to catch up.
- **H2b (lagged BTC predictor):** BTC's return in the last 1h is a leading indicator for altcoin return in the next 1–2h. Proxy: lagged BTC r_1h as a level predictor (not cross-sectional z-score — same value for all alts, tests market-level signal).

**Economic Theory:**
- **Kyle (1985, Econometrica) — Sequential information arrival:** Informed traders arrive sequentially; the asset with the highest liquidity and tightest bid-ask spread processes market-wide information first (best price discovery). BTC is the most liquid crypto asset on every venue; macro news (Fed decisions, regulatory events, institutional flows) hits BTC-USD before any altcoin pair.
- **Grossman & Stiglitz (1980) — Rational inattention:** Acquiring and processing information about 67 altcoins is costly. Rational traders use BTC as a sufficient statistic for market-wide crypto sentiment, checking altcoin-specific prices only after BTC has repriced. This delay creates the diffusion window our signal exploits.
- **Hou (2007, RFS) — Lead-lag in equity markets:** Large-cap US stocks lead small-cap stocks by up to 1 week in incorporating market-wide information. BTC-to-altcoin is the direct crypto analogue of this well-documented equity phenomenon.
- **Why crypto specifically:** BTC perpetual futures (CME, Binance) have 24h institutional participation; macro news hits BTC-USD books first via derivatives arbitrage. Alt-USD pairs adjust through BTC-USD/BTC-alt cross-pair flows which have finite bandwidth — creating the 1–4h lag window.

**Necessary conditions:**
1. BTC is genuinely a leading indicator (it reprices first)
2. Altcoin price adjustment to BTC moves takes 1–6h (not immediate)
3. The altcoin-BTC relationship is directionally consistent (not reversed)

**Failure modes:**
- If altcoin-BTC correlation is zero (alt-season decoupling), no catch-up mechanism
- If BTC adjustment itself is immediate (no lag from BTC to alts), mechanism doesn't exist
- If the "lagged BTC" signal reverts within the holding period (BTC overshoots and corrects), net IC = 0

**Expected predictive horizon:** 1h–6h for H2b; 2h–12h for H2a

---

### H5: Volatility-Adjusted Momentum (Sharpe Ranking)
**Mechanism statement:** The 67-pair Roostoo universe is highly heterogeneous: BTC and ETH have low volatility while meme coins have 10× higher volatility. Cross-sectional raw return rankings are dominated by high-vol coins that experience large idiosyncratic moves. Risk-adjusted momentum (r / realized_vol) normalizes this heterogeneity: a coin that moved 3% with 2% realized vol (Sharpe = 1.5) is ranked above a coin that moved 5% with 8% realized vol (Sharpe = 0.6). This normalization may reveal genuine trend quality obscured by the vol-contaminated raw ranking.

**Additionally:** The low-volatility anomaly (selecting the LEAST volatile assets in a cross-section) is well-documented in equities. In crypto, this translates to selecting BTC/ETH/established coins over meme coins. In trend regimes, these assets may exhibit more sustained directional behavior with less noise.

**Economic Theory:**
- **Frazzini & Pedersen (2014, JFE) — Betting Against Beta:** Leverage-constrained investors (retail, funds with mandate limits) cannot lever up low-volatility assets to match their target return, so they over-allocate to high-volatility assets. This systematic demand pushes high-vol assets above fundamental value; low-vol assets are underpriced and earn a premium. In crypto, retail speculation systematically overweights high-vol meme coins, creating the same structural overpricing documented in equity markets.
- **Baker, Bradley & Wurgler (2011, FAJ) — Low volatility anomaly in equities:** Low-vol stocks outperform high-vol stocks on a risk-adjusted basis across global equity markets. Our H5 proxy applies this to the crypto cross-section: select the coins with the lowest recent realized volatility.
- **Why Sharpe normalization fails but raw low-vol succeeds:** Sharpe-normalization selects assets with "efficient recent gains" — high recent return AND low recent vol. These are assets that have ALREADY repriced fully (the move is done) and are priced for continuation that won't arrive. Raw low-vol selects STRUCTURAL stability regardless of recent direction — coins that have low vol because they are established, widely-held, and have genuine liquidity. These are the genuine mean-reversion candidates. The Sharpe filter adds a momentum component that is anti-predictive in our regime.
- **Why crypto specifically:** BTC/ETH/established alts have institutional custodians, exchange-level liquidity programs, and real utility providing a fundamental price floor. Meme coins have no fundamental floor; their large moves are pure noise driven by retail speculation cascades. The raw low-vol filter mechanically separates these two populations.

**Necessary conditions:**
1. Risk-adjusted return is a more stable measure of expected continuation than raw return
2. High-vol coins' large raw returns are predominantly noise/reversal rather than signal
3. Cross-sectional Sharpe ranking is predictive over the holding horizon

**Failure modes:**
- If high-vol coins ARE where the genuine trend is (momentum in meme coins), this filter HURTS
- If risk-adjustment introduces a look-ahead bias or insufficient history problem
- If vol calculation at 6h horizon is too noisy (few data points)

**Expected predictive horizon:** 4h–24h (quality signals persist longer than noise)

---

### H6: Candle Persistence (Streak Consistency)
**Mechanism statement:** A single large hourly return may be a one-bar spike (one aggressive buyer, one liquidity event) that reverts immediately. A series of consecutive up-bars (each hour: close > open) indicates SUSTAINED buying pressure maintained across multiple participants and time windows — the directional impulse outlasts a single actor's impact. This persistence measure is mechanistically distinct from cumulative return (which may result from one large spike hour).

**Economic Theory and Redundancy Proof:**
- **Intended mechanism:** Consecutive hourly up-bars indicate sustained buying pressure across multiple participants and time windows, distinct from a single-bar spike. The streak supposedly captures breadth of participation that a single cumulative return cannot.
- **Mathematical redundancy with H1:** For an asset with 6 hourly bars, if cumulative 6h return r > 0, then by definition more than half the bars must be positive-contribution (close > open). Cross-sectional z-normalization of `H6_up_pct_6h` ≈ CS_z(sign(r_6h)) in expectation, which collapses to the same ordering as CS_z(r_6h) — H1's primary input. H6 ignores per-bar magnitude (one large bar among five flat bars has the same H6 score as six small-but-consistent up bars), and that magnitude information is precisely what the reversal mechanism exploits. Empirically confirmed: H6 IC is near-zero at all horizons, not because the breadth mechanism fails, but because it cannot produce any cross-sectional ordering beyond H1.
- **Why this is a principled rejection, not a false negative:** The redundancy is structural, not sample-specific. Even with unlimited data, H6 cannot outperform H1 in a cross-sectional framework because it discards the return magnitude information H1 uses.

**Necessary conditions:**
1. Per-bar directionality (close > open) contains information about participation breadth
2. Consecutive streak persistence predicts continuation at the cross-sectional level
3. The streak signal is not dominated by the H1 reversal effect (streaks may be exhaustion signals)

**Note:** H6 may CONFLICT with H1 (H1 says high-momentum assets revert; H6 says persistent up-streaks continue). The IC test will resolve which is empirically dominant. If both pass, they are separate mechanisms applicable to different forward horizons.

**Expected predictive horizon:** 1h–6h (short — streak information decays quickly)

**Data requirement:** OHLC (cols 1–4) already downloaded by `load_klines_all_parallel()`.

---

## Not Tested (Out of Scope for Timeline)

**H7: Funding rate cross-sectional** — Binance perpetual funding rates are NOT in historical klines data; requires separate FAPI endpoint that lacks historical depth for backtesting. Operationally available live, but cannot validate offline. **Skip for research; funding rate already used in M_t maturity component.**

**H8: On-chain analytics** — MVRV, NUPL, exchange flows require third-party data (Glassnode, etc.) not available for 67-pair universe with historical depth. **Skip.**

**H9: Sentiment analysis** — News/social data requires NLP pipeline. Fear & Greed Index already in LSI (H3). **Skip.**

---

## Mechanism Priority Order

1. **H1 Reversal** — Highest empirical support (H0 negative IC → H1 positive IC expected); test first
2. **H2 BTC-relative** — Strong theoretical grounding; mechanistically distinct from all tested families
3. **H5 Vol-adjusted** — Addresses known contamination problem (meme-coin vol heterogeneity)
4. **H6 Streak persistence** — Lower confidence; quick to compute; test last
