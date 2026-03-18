---
proxy_id: HAZ_BTC_VOL_Z
family: Hazard_C2
formula: BTC 6h realized-vol z-score (48h window) > 1.50 → block entries
status: APPROVED
ic_best: N/A
---

# HAZ_BTC_VOL_Z — Mechanism

## Formula

BTC 6h realized volatility z-score vs 48h rolling history > 1.50 → block new entries

```
vol_z = (realized_vol_6h_BTC − mean_vol_48h_BTC) / std_vol_48h_BTC
block_entry if vol_z > 1.50
```

## Economic Rationale

BTC realized volatility is the single most reliable real-time indicator of systemic
stress in the crypto market. A z-score above 1.50 means BTC's short-term volatility
is in the top ~7% of its recent distribution — a regime where reversal signals become
unreliable because price discovery is dominated by forced liquidations and panic
rather than information diffusion. During these episodes, the expectation-diffusion
lag that drives C1 alpha disappears: secondary assets reprice instantly (downward)
in lock-step with BTC rather than exhibiting orderly catch-up dynamics. Blocking entries
under elevated BTC vol avoids the most dangerous adverse selection in the universe
selection.

## Signal Family

C2 Hazard — market-wide stress gate (BTC volatility regime)

## Decision

**Status:** APPROVED — MaxDD improvement +17.8% relative, worst 30-day drawdown
improvement +9.1pp; the strongest single C2 modifier in the screen; deployed as the
primary LSI component (weight 0.45).
