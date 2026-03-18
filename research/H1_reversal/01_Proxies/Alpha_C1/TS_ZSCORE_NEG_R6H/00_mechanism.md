---
proxy_id: TS_ZSCORE_NEG_R6H
family: Alpha_C1
formula: CS_z(−TS_z(r_6h)) where TS_z(r_6h) = (r_6h − mean_r6h_48h) / std_r6h_48h
status: PASS
ic_best: +0.0266 @ 1h (t=+6.91)
---

# TS_ZSCORE_NEG_R6H — Mechanism

## Formula

`CS_z(−TS_z(r_6h))` where:

```
TS_z(r_6h) = (r_6h − mean_r6h_48h) / std_r6h_48h
```

## Economic Rationale

Time-series normalization compares an asset's current 6h return against its own recent
history (48h window), rather than against the cross-section. A negative TS z-score
means the asset is underperforming relative to its own typical returns — a self-referential
laggard. This captures a different dimension from CS-based proxies: an asset can score
highly on TS_ZSCORE_NEG_R6H while performing in line with peers (neutral CS score) if
its own absolute momentum has turned unusually weak. The subsequent CS normalization of
the TS z-score layers cross-sectional ranking on top, creating a two-stage filter.

## Signal Family

H1 TS — time-series self-comparison reversal at 6h horizon

## Decision

**Status:** PASS — IC +0.0266, t-stat +6.91; passes the |t|>5 threshold but is the
weakest individual reversal signal; included in the CS_TS_BLEND combination but not
deployed standalone due to lower information content vs pure CS proxies.
