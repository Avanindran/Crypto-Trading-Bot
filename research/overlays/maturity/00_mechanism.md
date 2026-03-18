# Maturity Overlay — M_t Remaining Drift Capacity

> **Scope:** H1 Reversal engine only — C3 mean-reversion maturity layer.
> This is NOT a cross-mechanism overlay. M_t measures how far along the mean-reversion
> trade is for H1; it does not apply to H2's diffusion mechanism.
> H2's C3 (diffusion exhaustion) lives at `H2_transitional_drift/01_Proxies/Maturity_C3/`.
> The sole cross-mechanism overlay is `overlays/regime/` (λ_t hazard rate).

**Archetype:** Entry Timing Filter (reduces entry into overextended positions)
**Status:** PARTIALLY VALIDATED — pct_rank proxy REJECTED; composite retained with caveat
**Last updated:** 2026-03-17

---

## Mechanism Statement

After a laggard asset is identified by H1 (cross-sectional reversal signal), a secondary question arises:

> **Has the recovery already been partially captured by other participants, or is there remaining drift capacity?**

Even if an asset is a genuine reversal candidate, entering near the end of the correction period — when the mean-reversion is nearly complete — reduces expected forward return. The M_t overlay measures the **remaining drift capacity**: how much of the expected 4h correction has not yet been captured.

```
M_t_i ∈ [0, 1]    where 0 = early stage (full drift potential), 1 = late stage (drift nearly exhausted)

Effective position score modifier: (1 − M_t_i)
  M_t = 0.0 → modifier = 1.0  (full weight: early entry)
  M_t = 0.5 → modifier = 0.5  (half weight: mid-recovery)
  M_t = 1.0 → modifier = 0.0  (zero weight: recovery complete)
```

Combined position score:
```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
```

---

## What Is Measured

M_t captures "overextension" — the degree to which the asset has already moved in the reversal direction (recovering from its laggard position). Four proxy components contribute:

1. **SMA extension** (weight 0.40): How far has price extended above its 12h SMA? Large positive extension → price has already recovered → less remaining upside.

2. **RSI proxy** (weight 0.15): An overbought indicator. High RSI-proxy → buying pressure has been sustained for long enough that new buyers are scarce.

3. **Percentile rank** (weight 0.25): Where does r_6h fall in the asset's own 48h history? High pct_rank → current return is already in the high end of the recent distribution → suggests drift may be mature.

4. **Funding rate** (weight 0.20): Binance perpetual funding rate. High positive funding → crowded long positioning → reduced upside as new longs are less likely.

---

## Why M_t Has Lower Confidence than C1

The H1 reversal mechanism operates on a 1–4h timescale. The M_t overlay attempts to measure timing within that window — a harder estimation problem than the signal itself.

**Key empirical finding:** The pct_rank proxy alone FAILS the validation gate:
- IC(fresh bucket, pct_rank < 30%) = +0.018
- IC(unconditional) = +0.048
- IC(fresh) < IC(unconditional) → pct_rank proxy REJECTED

In a trending market, assets with "fresh" pct_rank (recently entered recovery from laggard position) have lower IC than the unconditional expectation. This is because in a trend, assets that have just started recovering may be in the early phase of a momentum move, but the pct_rank filter misidentifies "not yet extended" assets as better candidates when statistically they are not.

**Why the composite is retained:** The four-component composite includes SMA extension and funding rate, which capture overextension through different channels than pct_rank alone. These components are not covered by the pct_rank validation and retain economic justification:
- Funding rate is a direct market signal of crowded positioning (not captured by pct_rank)
- SMA extension captures price-level overextension (not covered by return percentile)

The composite is retained in the live bot with the caveat that only the pct_rank component was formally tested.

---

## Admissibility Condition

```
M_t_i > MAX_MATURITY_FOR_ENTRY (0.72) → do not enter new position in asset i
```

This is a hard gate, not a soft scaling. Assets with M_t > 0.72 are excluded from entry consideration regardless of C1 score.

The threshold 0.72 corresponds to approximately the top 28% of the maturity distribution — the most overextended assets.

---

## Economic Theory

**Jegadeesh & Titman (1993, Journal of Finance) — Momentum returns and overreaction:**
The reversal at 1–4h operates similarly to the 1-month reversal documented by Jegadeesh (1990). In both cases, the correction has a finite duration — once the inventory rebalancing is complete, the asset enters a new steady state. M_t attempts to capture proximity to this completion point.

**Shleifer & Vishny (1997, Journal of Finance) — Limits of arbitrage:**
Arbitrageurs face capital constraints and noise trader risk. They enter corrective positions early (when the asset is most mispriced) and exit before the full correction completes (to avoid noise trader reversals). High M_t suggests the smart money has already entered — remaining upside is limited by limits-of-arbitrage dynamics.

---

## Navigation

| File | Content |
|------|---------|
| [01_proxy_universe.md](01_proxy_universe.md) | M_t component specs |
| [03_decision.md](03_decision.md) | pct_rank REJECTED; composite retained |
| [../regime/00_mechanism.md](../regime/00_mechanism.md) | Regime overlay (λ_t) |
| [../../H1_reversal/00_mechanism.md](../../H1_reversal/00_mechanism.md) | H1 signal (what M_t modifies) |
