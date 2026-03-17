# Regime Overlay — λ_t Hazard Rate

**Archetype:** Admissibility Gate (not a return-generating mechanism)
**Status:** APPROVED — live in `bot/strategy/regime.py`
**Last updated:** 2026-03-17

---

## Mechanism Statement

The regime overlay does not generate alpha. It answers a single question:

> **Is the current market state one in which H1's reversal mechanism is admissible?**

H1 is admissible only when recent price moves are driven by **noise/liquidity shocks** rather than genuine information. In a stressed or strongly trending market, recent laggards may continue falling (genuine information, not overshoot). Deploying H1 in these states generates negative expected return.

The regime overlay measures the **hazard rate** λ_t — the probability per unit time that the current market state invalidates H1's admissibility condition. It is applied multiplicatively to the position score:

```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
```

At λ = 0.3 (TREND_SUPPORTIVE): exp(−0.3) = 0.74 — 74% of face value deployed
At λ = 1.5 (NEUTRAL_MIXED):     exp(−1.5) = 0.22 — 22% of face value deployed
At λ = 4.0 (HAZARD_DEFENSIVE):  exp(−4.0) = 0.018 — 1.8% of face value deployed
At λ = 10.0 (EMERGENCY):        exp(−10)  ≈ 0 — positions collapse to zero

**Why exponential (not linear):** At λ=4, linear `(1−C2)` with C2=0.8 gives 20% — far too much exposure in stressed markets. Binary-ish suppression at near-zero (1.8%) is what maximizes Sortino by avoiding the worst outcomes.

---

## What Is Measured

### Liquidity Stress Index (LSI)

LSI aggregates four market stress indicators into a single score in [0, 1]:

```
LSI = 0.45 × BTC_vol_z + 0.25 × spread_z + 0.15 × dispersion_z + 0.15 × FNG_component
```

Where:
- **BTC_vol_z:** BTC realized volatility z-score vs 48h baseline (dominant component — BTC volatility is the primary crisis signal)
- **spread_z:** Bid-ask spread z-score vs 48h baseline (market microstructure stress)
- **dispersion_z:** Cross-sectional return dispersion vs 48h baseline (regime transition signal — dispersion spikes during sector rotations)
- **FNG_component:** Crypto Fear & Greed Index normalized to [0,1] (extreme greed → crowded long positioning)

### Momentum Persistence Index (MPI)

MPI = fraction of last 48 hourly BTC returns that are positive.

- MPI > 0.50 → BTC has been trending up more than 50% of recent hours → momentum is persistent
- MPI < 0.30 → BTC is in chop or mild downtrend → no directional support for H1 laggards

### Forward Expectation Index (FEI)

FEI aggregates components that predict whether H1 reversal candidates will recover:
- Strong BTC trend (positive MPI) → altcoin laggards have BTC-diffusion support
- Low stress (low LSI) → recovery flows are not crowded out by liquidation cascades

---

## Regime Cascade

```
LSI > 0.80 → EMERGENCY (λ = 10.0)
LSI > 0.60 → HAZARD_DEFENSIVE (λ = 4.0)
LSI > 0.40 OR MPI < 0.30 → NEUTRAL_MIXED (λ = 1.5)
FEI > 0.55 AND MPI > 0.50 → TREND_SUPPORTIVE (λ = 0.3)
else → NEUTRAL_MIXED (λ = 0.8)
```

**LSI dominates.** If LSI > 0.60, the regime is HAZARD_DEFENSIVE regardless of MPI or FEI.

**Why LSI dominates:** In a liquidity crisis, the corrective flow that H1 relies on (market makers rebalancing inventory, statistical arbitrageurs correcting overshoot) is the first to withdraw. A stressed market has fewer stabilizing participants → laggards continue falling rather than recovering. The strategy must be near-flat in this state.

---

## Economic Theory

**Brunnermeier & Pedersen (2009, Review of Financial Studies) — Market liquidity and funding liquidity:**
When funding constraints tighten, market makers reduce inventory and withdraw corrective flow. LSI > 0.60 corresponds to the regime where funding stress begins to dominate — H1's return engine (market maker rebalancing) becomes unavailable.

**Grossman & Miller (1988, Journal of Finance) — Liquidity and market equilibrium:**
In stressed markets, accommodation capacity is limited — there are fewer participants willing to take the other side of the corrective trade. High LSI signals low accommodation capacity → H1 is inadmissible.

**De Bondt & Thaler (1985, Journal of Finance) — Overreaction is state-dependent:**
The overreaction mechanism (and its correction) operates in normal market conditions. In strongly trending markets, price moves are genuine information updates, not overshoots. The MPI condition captures this state — when BTC momentum is weak (MPI < 0.30), laggards may not be experiencing overshoot at all.

---

## Failure Modes

1. **LSI misses liquidity crisis:** If the stress event arrives faster than the BTC vol z-score accumulates, LSI may lag. The BTC gate in `kill_switch.py` (emergency exit when BTC drops > 6% in 2h) provides faster response for sudden crashes.

2. **MPI false positive in bull market:** If BTC has been weakly positive for 48h (MPI = 0.52) but is about to reverse sharply, the regime scores TREND_SUPPORTIVE while actual conditions are deteriorating. The LSI path takes over if vol spikes occur.

3. **FNG stale data:** Fear & Greed is published once daily. The 24h refresh means the FNG component may be 12–24h stale during regime transitions.

---

## Navigation

| File | Content |
|------|---------|
| [01_proxy_universe.md](01_proxy_universe.md) | LSI/MPI/FEI component specs |
| [02_results.md](02_results.md) | Regime filter robustness (LSI threshold perturbation) |
| [03_decision.md](03_decision.md) | APPROVED — validation gates |
| [../maturity/00_mechanism.md](../maturity/00_mechanism.md) | M_t maturity overlay |
| [../../H1_reversal/00_mechanism.md](../../H1_reversal/00_mechanism.md) | H1 signal (what regime gates) |
| [../../portfolio/01_signal_aggregation.md](../../portfolio/01_signal_aggregation.md) | How regime interacts with signal aggregation |
