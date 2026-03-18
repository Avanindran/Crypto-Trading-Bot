---
proxy_id: MAT_PCT_RANK
family: Maturity_C3
formula: pct_rank(r_6h, 48h rolling) > 0.72 → block entry
status: REJECTED
ic_best: N/A
---

# MAT_PCT_RANK — Mechanism

## Formula

Percentile rank of current r_6h return within its own 48h rolling distribution > 0.72
→ block new entry

```
pct_rank = percentileofscore(r6h_history_48h, r6h_current) / 100
block_entry if pct_rank > 0.72
```

## Economic Rationale

A high percentile rank means the asset's current 6h return is near the top of its recent
history — it has been running strongly on a relative basis. In the C3 maturity framework,
this signals that the diffusion move is in its late stage: most of the catch-up has
already occurred, leaving little remaining upside from the expectation-diffusion mechanism.
Blocking entries when r_6h is above the 72nd percentile of its own history is intended
to avoid entering positions that are already overextended in time-series terms. Empirically,
however, the IC uplift is negative: assets with high pct_rank generate worse forward
returns when we apply this filter, suggesting the proxy is blocking entries at exactly
the wrong time — possibly because high pct_rank also coincides with genuine momentum.

## Signal Family

C3 Maturity — time-series return percentile rank (drift saturation)

## Decision

**Status:** REJECTED — IC uplift −0.0287; the pct_rank filter removes profitable entries
disproportionately; the 0.72 threshold appears to be in the momentum zone rather than
the overextension zone.
