---
proxy_id: CS_NEG_R2H
test_period: Oct 2024 – Jan 2025
decision: PROMOTED
ic_best: +0.0472 @ 1h (t=+10.33)
---

# CS_NEG_R2H — IC Test Results

**Source:** `research/signal_search.py`
**Period:** Oct 2024 – Jan 2025 (N=2924 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.047 | * |
| 2h | +0.043 | * |
| 4h | +0.036 | * |
| 6h | +0.032 | * |
| 12h | +0.018 | * |
| 24h | +0.014 | * |

Best IC: **+0.0472 @ 1h** (t=+10.33)

## Decision

**PROMOTE** — IC > 0.03 and t > 1.5 at best horizon.
Slightly lower IC than CS_NEG_R1H at 1h, but stronger at 4–6h. Used as r_2h component inside CS_NEG_C1 composite.

## Notes

CS_NEG_R2H is the base reversal proxy operationalised as H2D_BTCGATED_H1 (BTC-gated variant). Also an H2c input horizon.
