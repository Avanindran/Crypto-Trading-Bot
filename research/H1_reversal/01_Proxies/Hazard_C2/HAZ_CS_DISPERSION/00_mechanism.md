---
proxy_id: HAZ_CS_DISPERSION
family: Hazard_C2
formula: std(r_1h across assets) < 0.005 → block entries (panic correlation)
status: REJECTED
ic_best: N/A
---

# HAZ_CS_DISPERSION — Mechanism

## Formula

Cross-sectional standard deviation of 1h returns across all assets < 0.005 → block new entries

```
dispersion = std(r_1h[all_assets])
block_entry if dispersion < 0.005
```

## Economic Rationale

Cross-sectional dispersion collapse — all assets moving in near-identical lockstep —
indicates a systemic panic or capitulation event where individual asset characteristics
become irrelevant. In theory, very low dispersion should signal that reversal signals
will not work because there is no meaningful cross-sectional spread to exploit. However,
the empirical result contradicts this intuition: low dispersion events are actually
associated with quiet consolidation periods where reversal alpha is still present,
and the threshold is triggered too infrequently to provide meaningful protection during
actual stress (where dispersion increases from forced directional liquidations).

## Signal Family

C2 Hazard — cross-sectional correlation regime gate

## Decision

**Status:** REJECTED — MaxDD change −3.1%; blocking entries during low-dispersion regimes
removes profitable periods more than it avoids losses; the proxy misfires on the wrong
side of the volatility cycle.
