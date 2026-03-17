---
proxy_id: TS_ZSCORE_NEG_R2H
test_period: Oct 2024 – Jan 2025
decision: PROMOTED
ic_best: +0.0358 @ 1h (t=+9.46)
---

# TS_ZSCORE_NEG_R2H — IC Test Results

**Source:** `research/signal_search.py` (TS overshoot family)
**Period:** Oct 2024 – Jan 2025 (N=2918 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.036 | * |
| 2h | +0.031 | * |
| 4h | +0.024 | * |
| 6h | +0.020 | * |
| 12h | +0.011 | * |
| 24h | +0.011 | * |

Best IC: **+0.0358 @ 1h** (t=+9.46)

## Decision

**PROMOTE** — IC > 0.03 and t > 1.5 at best horizon.
Stronger than TS_ZSCORE_NEG_R6H at all horizons. The 2h TS normalization captures short-term overreactions against each asset's own recent distribution — faster-decaying but higher peak IC.

## Notes

Eligible as GP terminal. Not included in current GP search terminal set (which tested TS_ZSCORE_NEG_R6H instead). This is a candidate for the next GP expansion run. The signal is orthogonal to CS_NEG_R2H: an asset can be a CS laggard (low r_2h vs peers) while having a normal TS z-score (r_2h normal vs own history), and vice versa.
