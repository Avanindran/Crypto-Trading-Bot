---
proxy_id: HAZ_FNG_EXTREME
family: Hazard_C2
formula: Crypto Fear & Greed Index > 75 (extreme greed) → block entries
status: APPROVED
ic_best: N/A
---

# HAZ_FNG_EXTREME — Mechanism

## Formula

Crypto Fear & Greed Index (Alternative.me) > 75 → block new entries

```
fng_value = get_fear_greed_index()   # 0–100
block_entry if fng_value > 75
```

## Economic Rationale

The Fear & Greed Index is a leading macro-sentiment indicator for the crypto market.
Extreme greed readings (>75) historically precede sharp market corrections: retail
positioning becomes overcrowded, funding rates spike, and the market is vulnerable to
sudden reversal of the prevailing trend. In this environment, the expectation-diffusion
mechanism inverts: the "secondary laggards" that C1 targets are no longer lagging due
to information diffusion delay — they are lagging because they are genuinely weaker
assets being held up by euphoric sentiment. Entering positions in this regime risks
catching the unwind of stretched longs rather than harvesting a catch-up move.
The index is a low-frequency signal (daily resolution), making it suitable as a
regime gate rather than a high-frequency filter.

## Signal Family

C2 Hazard — macro sentiment regime gate (leading indicator)

## Decision

**Status:** APPROVED — MaxDD improvement +17.6% relative, worst 30-day improvement
+5.3pp; second-strongest C2 modifier; deployed as the FNG component in LSI with
weight 0.15 and as standalone gate in the regime engine.
