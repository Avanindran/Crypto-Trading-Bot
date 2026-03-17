---
proxy_id: MAT_VOL_RATIO
family: Maturity_C3
formula: mean(vol_6h) / median(vol_48h) > 2.0 → block entry (climax volume)
status: APPROVED
ic_best: N/A
---

# MAT_VOL_RATIO — Mechanism

## Formula

Ratio of current 6h average volume to 48h median volume > 2.0 → block new entry

```
vol_ratio = mean(volume_6h) / median(volume_48h)
block_entry if vol_ratio > 2.0
```

## Economic Rationale

Climax volume — a volume spike to more than twice the recent baseline — is one of the
most reliable technical signals that a move is exhausted. High-volume price spikes attract
maximum participation from momentum traders, fast money, and retail FOMO, often marking
the exact point where the marginal buyer is depleted. After a volume climax, price
typically either consolidates or reverses sharply. In the C3 maturity framework, this
represents the terminal phase of the diffusion event: the information has fully propagated
to all market participants (evidenced by the volume surge), leaving no further catch-up
potential. Blocking entries after climax volume prevents entering at the worst possible
time in the diffusion cycle.

## Signal Family

C3 Maturity — volume climax gate (diffusion exhaustion)

## Decision

**Status:** APPROVED — IC uplift +0.0640; fresh IC 0.1117 vs unconditional 0.0477 —
the strongest C3 modifier by a very wide margin; climax volume is the single most
effective maturity indicator in the universe; strongly recommended for deployment in
the maturity composite.
