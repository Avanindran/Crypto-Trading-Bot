# H1 — Transient Expectation Overshoot (Reversal Archetype)

**Archetype:** Reversal — see `Systematic Trading Architecture/01_strategy_archetypes.md`
**Status:** PROMOTED — live in `bot/strategy/signals.py`
**Last updated:** 2026-03-17

---

## Mechanism Statement

At short horizons (1–4h), crypto price moves are frequently driven by **liquidity shocks** rather than full information updates. A large aggressive order, a leveraged liquidation cascade, or sudden retail flow can push price beyond the level justified by the current information set:

```
P_t > E[P_t | I_t]    (recent outperformer: price above conditional expectation)
P_t < E[P_t | I_t]    (recent underperformer: price below conditional expectation)
```

Because price temporarily deviates from expectation, the expected forward return is:

```
E[r_{t → t+h} | P_t < E[P_t | I_t]] > 0    (laggards: positive expected return)
E[r_{t → t+h} | P_t > E[P_t | I_t]] < 0    (leaders: negative expected return)
```

Corrective flow from market makers, statistical arbitrageurs, and mean-reverting participants restores price toward equilibrium within 1–4h. This corrective flow is the return engine.

**This is not a momentum signal.** The direction of alpha is correction toward conditional expectation, not continuation of recent direction. The archetype is **Reversal**, not Momentum (De Bondt & Thaler 1985, Lehmann 1990, Jegadeesh 1990).

---

## What Is Mispriced

The mispriced quantity is the **deviation of observed price from conditional expectation**:

```
ε_i,t = P_i,t − E[P_i,t | I_t]
```

For recent underperformers, ε < 0 → price will recover.
For recent outperformers, ε > 0 → price will correct.

We cannot observe ε directly. The signal proxy approximates it using the cross-sectional rank of recent returns — recent laggards are likely in negative deviation state.

---

## Return Engine

The return driver is the **mean-reversion of liquidity-induced price deviations**:

1. Liquidity shock pushes price away from expectation
2. Overshoot persists briefly (duration ~30min–2h, longer in thin crypto markets)
3. Market makers observe mispricing and submit corrective orders
4. Cross-asset arbitrageurs who hold correlated positions rebalance
5. Price returns to near-expectation level within 1–4h

**Why crypto specifically:**
- Thin order books (2–5× wider bid-ask than equities in comparable size)
- Fragmented liquidity across hundreds of pairs competing for the same pool of arbitrageurs
- High retail participation → more aggressive order flow → larger overshoots
- Lower institutional presence → slower correction → longer window to exploit

---

## State Dependence and Admissibility

**H1 is only admissible when recent moves are driven by noise/liquidity, not genuine information.**

In a strong directional trend (confirmed by BTC momentum + low LSI), recent laggards may be laggards because they are genuinely weaker assets — not because of a transient liquidity shock. In this state:

- The overshoot mechanism still exists but is overwhelmed by genuine directional drift
- Entering laggards in a downtrend produces negative expected return
- H1 must be **GATED by the regime overlay** (λ_t from LSI/MPI cascade)

Admissible states:
- `LSI < 0.40` AND `MPI > 0.30` (non-hazardous, some upward momentum)
- Specifically: TREND_SUPPORTIVE and NEUTRAL_MIXED regimes

Not admissible:
- `LSI > 0.60` (HAZARD_DEFENSIVE) — liquidity-driven moves in stressed markets are persistent, not corrective
- Strong downtrend (`MPI < 0.30`) — laggards continue down

The regime overlay (`exp(-λ_t)`) enforces this admissibility constraint mathematically. At λ = 4.0, position scores collapse to 1.8% of face value — effectively zero exposure.

---

## Economic Theory

**De Bondt & Thaler (1985, Journal of Finance) — Overreaction hypothesis:**
Investors systematically overreact to short-term price information. The correction produces negative serial autocorrelation at horizons matching the overreaction window. In crypto, the overreaction window is compressed to 1–4h due to high retail participation and low institutional stabilizing flow.

**Lehmann (1990, Review of Financial Studies) — Weekly reversal:**
Documents weekly reversal in equity markets attributed to bid-ask bounce and market-maker inventory rebalancing. The crypto analogue operates at hourly frequency. Market makers who absorbed the aggressive flow rebalance their inventory over the subsequent 1–4h, creating the corrective return stream.

**Jegadeesh (1990, Journal of Finance) — Monthly reversal:**
Documents 1-month autocorrelation reversals in equities. The same inventory-rebalancing and overreaction dynamics apply at the hourly crypto frequency, compressed by higher retail participation and thinner books.

**Frazzini & Pedersen (2014, Journal of Financial Economics) — Betting Against Beta:**
Leverage-constrained investors overallocate to high-volatility assets, pushing them above fundamental value. High-vol meme coins are structurally overpriced; their apparent laggard status during a correction is noise (they simply fell back to equilibrium), not a genuine reversal opportunity. The **H5 stability filter** removes these from the candidate set, leaving only laggards with genuine mean-reversion potential.

---

## Necessary Conditions

1. Price moves at short horizons (1–6h) are driven by liquidity shocks more than information updates
2. Corrective flow from market makers and arbitrageurs arrives within the 4h holding window
3. The cross-sectional rank of recent returns is a reasonable proxy for the deviation from expectation
4. High-vol meme-coin moves are predominantly noise (H5 filter handles this)
5. The regime state is non-hazardous (admissibility condition above)

---

## Failure Modes

1. **Strong directional trend:** In a confirmed bull market, the positive IC is lower (see H2 mechanism test — IC = +0.024 when BTC flat vs +0.110 when BTC large-move). The signal degrades but does not reverse. The regime gate is the primary defense.

2. **Mean reversion at sub-1h frequency:** If the corrective flow arrives within the same 1h kline (not visible in our data), IC at 1h is zero. Empirically, IC is highest at 1h (not zero), so this condition is not binding.

3. **Systematic one-sided flow (liquidation cascade):** A cascade that continues across multiple hours can make laggards continue lower. The stop-loss (−4%) in the live bot handles this at the position level.

4. **H5 filter underfit:** If the stability screen (CS_z(-vol)) is too aggressive, it excludes too many laggards. The 0.30 blend weight limits this risk.

---

## Relationship to H2

H1 and H2 (Transitional Drift) are **mechanistically distinct but empirically linked**:

- H2 predicts WHEN H1 has highest IC (when BTC has moved → altcoin laggards are more likely in genuine deviation state, not random noise)
- When BTC makes a large move, H1 IC jumps from +0.024 to +0.110 (H2 mechanism test, +0.087 uplift)
- Interpretation: BTC-driven moves create the clearest expectation deviations in altcoins
- The H2 regime conditioning informs the H1 signal strength (more BTC movement → stronger H1 alpha)

In the current live bot, this linkage is captured through the regime overlay (BTC vol z-score in LSI). In a future dual-engine architecture, H2 would explicitly condition H1's allocation.

See `H2_transitional_drift/00_mechanism.md` for the H2 mechanism statement.
See `portfolio/01_signal_aggregation.md` for the combined allocation framework.

---

## Signal Construction

```
# H1 component: select cross-sectional laggards
C1_raw_i  = 0.10×r_30m + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r2h)
neg_c1_z  = CS_z(−C1_raw_i)       # negate: laggards get high scores

# H5 stability component: select low-vol assets
neg_vol_z = CS_z(−realized_vol_6h_i)  # negate: low vol gets high score

# Promoted blend (GP-selected weights)
C1_i = 0.70 × neg_c1_z + 0.30 × neg_vol_z
```

**Expected predictive horizon:** 1h–4h (decay after 4h as corrective flow completes)
**Optimal rebalance cadence:** 4h (as in live bot)

---

## Navigation

| Next step | File |
|-----------|------|
| Proxy universe (all candidate signals) | [01_Proxies/00_proxy_universe.md](01_Proxies/00_proxy_universe.md) |
| IC results (CS family) | [02_Candidates/Signal/01_ic_results.md](02_Candidates/Signal/01_ic_results.md) |
| IC results (TS + H2 family) | [02_Candidates/Signal/05_ts_variant_search.md](02_Candidates/Signal/05_ts_variant_search.md) |
| Combination search results | [02_Candidates/Signal/04_combination_search.md](02_Candidates/Signal/04_combination_search.md) |
| Vector backtest results | [02_Candidates/Strategy/01_vector_tests.md](02_Candidates/Strategy/01_vector_tests.md) |
| Promotion decision | [04_decision.md](04_decision.md) |
| H2 mechanism (why H1 IC varies with BTC) | [../H2_transitional_drift/00_mechanism.md](../H2_transitional_drift/00_mechanism.md) |
| Regime overlay | [../overlays/regime/00_mechanism.md](../overlays/regime/00_mechanism.md) |
