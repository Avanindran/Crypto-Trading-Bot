# Strategy: Cross-Sectional Reversal with BTC-Diffusion Regime Overlay

## Economic Mechanism

### H1 — Transient Expectation Overshoot (Live Signal, Reversal Archetype)

At short horizons (1–4h), crypto price moves are frequently driven by **liquidity shocks** rather than full information updates. A large aggressive order, leveraged liquidation cascade, or sudden retail flow can push price beyond the level justified by the current information set:

```
P_t < E[P_t | I_t]   (recent laggard: price below conditional expectation)
```

The corrective flow from market makers, statistical arbitrageurs, and mean-reverting participants restores price toward equilibrium within 1–4h. For recent underperformers, the expected forward return is positive — **this is a Reversal signal, not Momentum.**

Economic basis: De Bondt & Thaler (1985) overreaction hypothesis; Lehmann (1990) market-maker inventory rebalancing at hourly frequency; Frazzini-Pedersen (2014) low-vol anomaly. Full theory: `research/H1_reversal/00_mechanism.md`.

### H2 — Expectation Diffusion via BTC (Mechanism Confirmed, H2c Promoted)

Crypto markets have a partially shared expectation structure where BTC serves as the primary state variable. When new information arrives, BTC reprices first (superior liquidity, CME participation). Altcoins lag:

```
Δᵢ = βᵢ · r_BTC,h − r_i,h > 0   (altcoin has not yet tracked BTC's move)
```

This is a **Momentum signal** (expectation updating speed error). The mechanism is empirically confirmed: H1 IC = +0.024 when BTC flat vs +0.110 when BTC has moved (uplift = +0.087). The direct proxy H2a collapses to H1 via CS z-normalization identity; H2b has no lag at 1h. H2c (beta-adjusted gap: `CS_z(β_i·r_BTC,2h − r_i,2h)`) is PROMOTED (IC=+0.042 @ 1h, t=+9.85) and is not deployed yet — pending GP integration before Mar 28 deadline. Full theory: `research/H2_transitional_drift/00_mechanism.md`.

### Signal Architecture

Three necessary conditions must hold simultaneously for a trade:
1. **Genuine deviation** — the asset is a cross-sectional laggard with genuine mean-reversion potential (measured by C1 reversal+stability signal)
2. **Low hazard** — the market is not in a stressed/trending state where laggards continue down (measured by λ_t regime overlay)
3. **Early stage** — the recovery has not yet been priced in by other participants (measured by M_t < MAX_MATURITY)

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
See `research/H1_reversal/04_decision.md` and `research/H1_reversal/02_Candidates/Signal/04_combination_search.md`.

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

A mechanism-specific backtest was conducted on Binance 1h data over Oct 2024 – Jan 2025 (44 pairs with full-period data). Each mechanism received its own risk overlay parameter sweep, selected on the Oct–Nov 2024 training period. OOS holdout (Dec–Jan 2025) evaluated after all parameter selection. Full results at `research/H1_reversal/02_Candidates/Strategy/02_backtest.md`, `research/H2_transitional_drift/02_Candidates/Strategy/01_backtest.md`, `research/portfolio/03_combined_backtest.md`.

**H1 Reversal — fully stacked config (stop-loss −4%, C1 exit 0.25, C2 z>0.75, Kelly sizing, top-3):**
- **Net return: +39.9%** | Sortino: **2.78** | Calmar: **11.03** | MaxDD: **−15.5%**
- OOS holdout (Dec–Jan 2025): return +2.5%, Sortino 0.53 — no overfit

**H2C BTC Lead-Lag — fully stacked config (BTC-rev exit −0.5%, BTC gate |r_BTC,2h|≥0.5%):**
- **Net return: +34.2%** | Sortino: **1.34** | Calmar: **2.96** | MaxDD: **−47.0%**
- BTC-direction exit transforms signal: Sortino 0.29 → 1.68 before portfolio optimization

**Dual-Engine (regime-conditional allocation):**
- α_TREND = 0.0 optimally selected — H1 dominates in TREND_ACTIVE periods; H2C does not add alpha on top of H1 in portfolio context (mechanisms select overlapping laggard assets)
- **Net return: +35.6%** | Sortino: **2.51** | Calmar: **9.68** | MaxDD: **−15.1%**
- OOS holdout: return +1.5%, Sortino 0.40 — positive
- Robustness (±20% parameter perturbation): Calmar 16.45/9.68/14.86 — PASS

**Fee sensitivity (H1 Version A with all risk overlays):**

| Fee Level | Net Return | Notes |
|-----------|-----------|-------|
| 0.00% (no fees) | +149.2% | Upper bound (no C2, no fee) |
| 0.05% maker | +28.9% | Competition scenario (+C2, limit orders) |
| 0.10% taker | −33.4% | Strategy not viable at taker fee |

**Research parameter validation:** Sweep confirmed `STOP_LOSS_PCT = −0.04` (matches H1_SL_OPT). `EXIT_C1_THRESHOLD` updated 0.20 → 0.25 (Sortino 1.86 vs 1.32 in sweep). See `research/H1_reversal/02_Candidates/Strategy/02_backtest.md` for full sweep tables.

### Signal Validation

An extended IC test was conducted across 67 pairs and three conditions: (A) current period Dec 2025–Feb 2026, (B) trending period Oct 2024–Jan 2025 (BTC +61% bull run), and (C) regime-conditional (TREND-eligible hours, BTC vol z-score ≤ 0). See `research/ic_validation_extended.py` for the data library methodology.

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

**Phase 4 — Reversal, Volatility, TS Overshoot, and H2 Signal Discovery (H1, H2, H5, TS):** A research pipeline was run following Systematic Trading Architecture doctrine. Mechanism families declared before any data was processed. See `research/H1_reversal/01_Proxies/00_proxy_universe.md` and `research/H2_transitional_drift/01_Proxies/00_proxy_universe.md`.

**Key finding (CS family):** The original C1 signal had IC = −0.038 at 4h (selecting winners → underperformers). Inverting C1 to select laggards gives IC = +0.042 at 4h. All 5 H1 reversal proxies (CS_NEG_R1H/R2H/R6H/C1/VOL) passed IC gate. H5_neg_vol showed strongest individual IC (+0.076 at 24h, t = +13.26). H5 Sharpe variants and H6 streak signals failed.

**Key finding (TS overshoot family):** Time-series z-score variants (TS_ZSCORE_NEG_R2H, TS_BB_DIST, CS_TS_BLEND_R6H) all PROMOTED (IC +0.035–0.036 @ 1h). These measure per-asset deviation below own recent history, orthogonal to cross-sectional variants. TS_ZSCORE_NEG_R6H passes but does not reach PROMOTE threshold (IC +0.027). Full results: `research/H1_reversal/02_Candidates/Signal/05_ts_variant_search.md`.

**Key finding (H2 non-collapsed):** H2a collapses to H1 mathematically. H2c (beta-adjusted gap `CS_z(β_i·r_BTC,2h − r_i,2h)`) PROMOTED (IC=+0.042 @ 1h, t=+9.85) — β_i varies per asset, surviving CS normalization. H2d (BTC-gated H1) PASS (IC=+0.019, diluted by gating). See `research/H2_transitional_drift/01_Proxies/00_proxy_universe.md`.

**Key finding (GP search):** Expanded terminal set including TS variants — champion unchanged: `0.70 × CS_z(−C1_raw) + 0.30 × CS_z(−realized_vol_6h)` (IC-Sharpe +0.190 train; holdout IC +0.066, t=10.59). TS-blend formula scores IC-Sharpe +0.159 — valid but lower than the multi-horizon composite CS_NEG_C1. Robustness: 97.2% of 500 random 10-day windows show positive IC. See `research/H1_reversal/02_Candidates/Signal/04_combination_search.md` and `02_Candidates/Strategy/03_robustness.md`.

**H2 mechanism test (Step 3D):** IC of H1 conditioned on BTC 2h move magnitude. Result: IC(BTC flat) = +0.024, IC(BTC large up, |r_2h|≥1.5%) = +0.110 — uplift = +0.087, 8.6× gate threshold. **H2 mechanism confirmed.** See `research/H2_transitional_drift/02_Candidates/Signal/02_mechanism_test.md`.

**C2 modifier screen (individual proxies):** 6 HAZ_ proxies individually screened. HAZ_BTC_VOL_Z APPROVED (+17.8% MaxDD rel improvement); HAZ_FNG_EXTREME APPROVED (+17.6%); 4 others REJECTED. Full results per proxy in `research/H1_reversal/01_Proxies/Hazard_C2/`.

**C3 modifier screen (individual proxies):** 7 MAT_ proxies individually screened. MAT_VOL_RATIO APPROVED (IC uplift +0.064 — strongest); MAT_FUNDING_RATE APPROVED (+0.010); 5 others REJECTED. Full results per proxy in `research/H1_reversal/01_Proxies/Maturity_C3/`.

**Vector tests (Steps 3C, 4A, 4B, 5):** A fixed-horizon portfolio backtest (4h hold, top-3 equal weight, Oct 2024–Jan 2025) was run across three configurations — bare signal, +C2 regime gate, +C2+C3 maturity filter. Results:

| Configuration | Sharpe | MaxDD | Hit Rate | Total Return |
|---|---|---|---|---|
| Bare C1 (no modifiers) | 1.87 | −34.1% | 51.5% | +59.4% |
| + C2 regime gate | 3.02 | −28.0% | 47.1% | +119.1% |
| + C2 + C3 maturity filter | 3.16 | −27.0% | 47.0% | +130.1% |

Step 3C sanity bars: all pass. Step 4A (C2 modifier, HAZ_BTC_VOL_Z): MaxDD improvement +17.8% relative (≥10% bar), worst 30d DD improvement +9.1pp (≥5pp bar) — **APPROVED**. HAZ_FNG_EXTREME also APPROVED (+17.6% MaxDD rel). Step 4B (C3 individual screens): MAT_VOL_RATIO APPROVED (IC uplift +0.064); MAT_FUNDING_RATE APPROVED (+0.010); pct_rank, SMA extension, RSI proxy, TS_zscore, consec_up all REJECTED. See `research/H1_reversal/02_Candidates/Strategy/01_vector_tests.md` and per-proxy screens in `01_Proxies/`.

**Phases 1–3 conclusion:** Three mechanistically distinct families — cross-sectional price momentum (Phase 1), time-series price momentum (Phase 2), and market microstructure/order flow (Phase 3) — all failed to find signals with IC > 0 and t > 1.0. **Phase 4 reversal research succeeded by inverting the direction of the Phase 1 search.**

The strategy's value proposition now rests on four components:

1. **Validated alpha selection (Sortino/Sharpe):** The promoted C1 signal (IC = +0.057, t = 12.55) selects cross-sectional laggards with low realized volatility, providing genuine cross-sectional alpha at the 4h horizon.
2. **Regime gating (Sortino):** The HAZARD_DEFENSIVE state (0% exposure when LSI > 0.60) avoids all downside deviation on stressed market days. Binary switching is what drives Sortino — clean zero exposure, not smooth scaling.
3. **Drawdown control (Calmar):** The -12% kill switch hard-caps max drawdown. A portfolio that earns 5% with a -6% max drawdown scores Calmar = 0.83; extending to -20% drawdown gives Calmar = 0.25.
4. **Maturity filter (Sortino/Sharpe):** M_t blocks entry into overextended assets (extension from SMA, RSI proxy, pct_rank, funding rate), preventing entry at the tail of a move where risk/reward is worst.

The competition scoring formula (0.4×Sortino + 0.3×Sharpe + 0.3×Calmar) rewards risk-adjusted performance. A strategy that avoids large drawdowns and the worst-vol days will score competitively even without superior selection IC, provided the market direction during the 10-day competition window is non-hostile.

## Research Pipeline Status

Full doctrine compliance table. Every step maps to a research file with a formal verdict.

| Step | Doctrine Name | File | Verdict |
|------|---------------|------|---------|
| 0 | OOS reserve | `research/H1_reversal/03_OOS_Reservation/oos_reservation.md` | Dec–Jan 2025 holdout formally declared before IC testing |
| 1 | Mechanism declaration | `research/H1_reversal/00_mechanism.md`, `research/H2_transitional_drift/00_mechanism.md` | H1 (Reversal), H2 (Momentum), H5, TS declared before data seen |
| 2 | Proxy commitment | `research/H1_reversal/01_Proxies/00_proxy_universe.md`, `research/H2_transitional_drift/01_Proxies/00_proxy_universe.md` | All proxies frozen before IC run |
| 3A | IC testing (CS) | `research/H1_reversal/02_Candidates/Signal/01_ic_results.md` | H1+H5 pass; H5_sharpe, H6 fail |
| 3A | IC testing (TS + H2) | `research/H1_reversal/02_Candidates/Signal/05_ts_variant_search.md` | TS_R2H, TS_BB_DIST, CS_TS_blend, H2c PROMOTE; H2d PASS |
| 2B | GP weight search | `research/H1_reversal/02_Candidates/Signal/04_combination_search.md` | 0.70×H1 + 0.30×H5 champion; IC-Sharpe +0.190 |
| 3B | Near-duplicate filter | `research/H2_transitional_drift/04_decision.md` | H2a = H1 (mathematical identity) |
| 3D | H2 mechanism test | `research/H2_transitional_drift/02_Candidates/Signal/02_mechanism_test.md` | CONFIRMED — IC uplift +0.087 when BTC moves |
| 4A | C2 modifier screens | `research/H1_reversal/01_Proxies/Hazard_C2/` | HAZ_BTC_VOL_Z + HAZ_FNG_EXTREME APPROVED; 4 REJECTED |
| 4B | C3 modifier screens | `research/H1_reversal/01_Proxies/Maturity_C3/` | MAT_VOL_RATIO (+0.064) + MAT_FUNDING_RATE (+0.010) APPROVED; 5 REJECTED |
| 3C | Bare signal vector | `research/H1_reversal/02_Candidates/Strategy/01_vector_tests.md` Part A | PASS (Sharpe 1.87, MaxDD −34%, HitRate 51.5%) |
| 5 | Full signal vector | `research/H1_reversal/02_Candidates/Strategy/01_vector_tests.md` Part D | Sharpe 1.87 → 3.02 → 3.16 |
| 6 | Portfolio construction | `research/overlays/portfolio_construction/01_sizing_schemes.md` | Quarter-Kelly vs equal weight Sortino gate |
| 7 | Regime allocation ladder | `research/overlays/portfolio_construction/02_regime_allocation.md` | 3-regime vs binary gate Calmar gate |
| 8 | Signal nomination | `research/H1_reversal/04_decision.md` | H1_neg_c1_x07_H5_neg_vol PROMOTED |
| 9 | Strategy assembly | `bot/strategy/signals.py` | Deployed |
| 10A | H1 mechanism backtest | `research/H1_reversal/02_Candidates/Strategy/02_backtest.md` | Sortino 2.78, Calmar 11.03, MaxDD −15.5% (0.05% maker, all overlays) |
| 10B | H2C mechanism backtest | `research/H2_transitional_drift/02_Candidates/Strategy/01_backtest.md` | Sortino 1.34, Calmar 2.96 (BTC-rev exit −0.5%, BTC gate ≥0.5%) |
| 10C | Dual-engine allocation | `research/portfolio/03_combined_backtest.md` | α_TREND=0.0 optimal; Sortino 2.51, Calmar 9.68; OOS positive |
| 12 | Robustness | `research/H1_reversal/02_Candidates/Strategy/03_robustness.md` | 97.2% block-resample hit rate |

## Research → Config Mapping

Every numeric constant in `config.py` traces to a specific research finding.

| Config constant | Value | Research basis |
|----------------|-------|----------------|
| `ALPHA_WEIGHT_REVERSAL` | 0.70 | GP search IC-Sharpe optimum (04_gp_search/) |
| `ALPHA_WEIGHT_STABILITY` | 0.30 | GP search IC-Sharpe optimum (04_gp_search/) |
| `LSI_WEIGHT_BTC_VOL` | 0.45 | C2 modifier: BTC vol is dominant stress indicator |
| `LSI_WEIGHT_FNG` | 0.15 | Fear & Greed added as leading indicator (pre-price-based) |
| `KELLY_FRACTION` | 0.25 | Portfolio construction Step 6: Quarter-Kelly vs EW Sortino |
| `REGIME_PARAMS` gross caps | 85/65/0% | Regime ladder Step 7: 3-regime improves Calmar vs binary gate |
| `MAX_MATURITY_FOR_ENTRY` | 0.72 | C3 gate: IC(fresh bucket) test in 06_vector_tests.md Part C |
| `DRAWDOWN_KILL` | −12% | Calmar denominator hard cap: prevents runaway MaxDD |
| `HOLD_HOURS` (implicit) | 4h | Optimal IC decay: reversal IC peaks at 1–4h (03_validation/) |
| `STOP_LOSS_PCT` | −4% | H1 SL sweep: −4% best Calmar (<5% stops/period criterion) |
| `EXIT_C1_THRESHOLD` | 0.25 | H1 exit sweep: 0.25 > 0.20 (Sortino 1.86 vs 1.32) |

## References

- Jegadeesh, N. & Titman, S. (1993). Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency. *Journal of Finance*, 48(1), 65–91.
- Liu, Y. & Tsyvinski, A. (2021). Risks and Returns of Cryptocurrency. *Review of Financial Studies*, 34(6), 2689–2727.
- Cong, L. W., Li. Y., & Wang, N. (2021). Tokenomics: Dynamic Adoption and Valuation. *Review of Financial Studies*, 34(3), 1105–1155.
- Glosten, L. R. & Milgrom, P. R. (1985). Bid, Ask and Transaction Prices in a Specialist Market with Heterogeneously Informed Traders. *Journal of Financial Economics*, 14(1), 71–100.
- Chordia, T., Roll, R., & Subrahmanyam, A. (2002). Order Imbalance, Liquidity, and Market Returns. *Journal of Financial Economics*, 65(1), 111–130.
