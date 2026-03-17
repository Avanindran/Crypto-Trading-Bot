---
proxy_id: CS_NEG_R6H
test_period: Oct 2024 – Jan 2025
decision: PROMOTED
ic_best: +0.0398 @ 2h (t=+8.73)
---

# CS_NEG_R6H — IC Test Results

**Source:** `research/signal_search.py`
**Period:** Oct 2024 – Jan 2025 (N=2924 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.039 | * |
| 2h | +0.040 | * |
| 4h | +0.034 | * |
| 6h | +0.027 | * |
| 12h | +0.010 | * |
| 24h | +0.018 | * |

Best IC: **+0.0398 @ 2h** (t=+8.73)

## Decision

**PROMOTE** — IC > 0.03 and t > 1.5 at best horizon.
The 6h horizon captures a larger overshoot window, with IC peak at 2h. This implies the corrective flow completes within 2h of observation.

## Notes

PRIMARY horizon proxy in the H1 reversal thesis. 6h return is the primary C1 weight in the live bot (`C1_WEIGHT_R6H = 0.35`). Also used as TS_ZSCORE_NEG_R6H baseline and CS_TS_BLEND_R6H component.
