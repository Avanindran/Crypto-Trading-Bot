---
proxy_id: MAT_FUNDING_RATE
family: Maturity_C3
formula: (price − mean_price_48h) / std_price_48h > 1.0 → block entry (proxy for positive funding)
status: APPROVED
ic_best: N/A
---

# MAT_FUNDING_RATE — Mechanism

## Formula

TS z-score of price vs 48h history > 1.0 → block new entry (used as proxy for positive
perpetual funding rate when direct funding data is unavailable)

```
price_zscore = (price − mean_price_48h) / std_price_48h
block_entry if price_zscore > 1.0
```

In production, direct Binance perp funding rate data is available:
```
normalized_funding = clip((rate − 0.0001) / 0.0008, 0, 1)
block_entry if normalized_funding > threshold
```

## Economic Rationale

Positive perpetual funding rates indicate that long traders are paying short traders,
meaning the market is leaning heavily long. High positive funding is a maturity signal:
it reflects overcrowded positioning and market participants who are already fully
allocated to the upside. Entering a long position when funding is highly positive means
buying into a crowded trade — funding rate spikes are historically followed by sharp
drawdowns as the crowd unwinds. The price z-score formulation serves as a funding proxy
because high funding typically coincides with price well above its recent equilibrium.
This is the only C3 proxy to pass with positive IC uplift at a meaningful level.

## Signal Family

C3 Maturity — perpetual funding rate / crowded-long gate

## Decision

**Status:** APPROVED — IC uplift +0.0101; fresh IC 0.0578 vs unconditional 0.0477;
the funding rate signal correctly identifies overextended long positioning; deployed
with MT_WEIGHT_FUNDING = 0.20 in the maturity composite.
