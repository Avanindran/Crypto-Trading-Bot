---
proxy_id: HAZ_SPREAD_Z
family: Hazard_C2
formula: (high − low) / close z-score (48h window) > 1.50 → block entries
status: REJECTED
ic_best: N/A
---

# HAZ_SPREAD_Z — Mechanism

## Formula

Per-asset high-low range normalized by close, z-scored vs 48h history, averaged across
universe > 1.50 → block new entries

```
hl_spread = (high − low) / close
spread_z = (hl_spread − mean_spread_48h) / std_spread_48h
block_entry if mean(spread_z[all_assets]) > 1.50
```

## Economic Rationale

Wide intrabar high-low spreads indicate elevated intraday volatility and potential
liquidity stress. In theory, elevated spreads should foreshadow adverse execution
conditions and signal instability that would degrade reversal alpha. However, in the
empirical test, the spread proxy fires frequently during periods that are actually
favorable for reversal: high-spread bars often correspond to sharp moves that create
exactly the overshooting conditions that reversal strategies exploit. Blocking during
these periods destroys alpha rather than protecting against loss.

## Signal Family

C2 Hazard — intraday volatility / liquidity stress gate

## Decision

**Status:** REJECTED — MaxDD change −16.1%; worst single C2 proxy; blocking on wide
spreads is deeply counter-productive as spread expansion often coincides with the
onset of mean-reversion opportunities, not their destruction.
