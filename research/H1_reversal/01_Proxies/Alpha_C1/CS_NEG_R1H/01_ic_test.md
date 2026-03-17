---
proxy_id: CS_NEG_R1H
test_period: Oct 2024 – Jan 2025
decision: PROMOTED
ic_best: +0.0492 @ 1h (t=+10.75)
---

# CS_NEG_R1H — IC Test Results

**Source:** `research/signal_search.py`
**Period:** Oct 2024 – Jan 2025 (N=2924 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.049 | * |
| 2h | +0.041 | * |
| 4h | +0.032 | * |
| 6h | +0.026 | * |
| 12h | +0.018 | * |
| 24h | +0.012 | * |

Best IC: **+0.0492 @ 1h** (t=+10.75)

## Decision

**PROMOTE** — IC > 0.03 and t > 1.5 at best horizon.
Eligible as standalone GP terminal. Shorter horizon than CS_NEG_R2H; decay profile typical of 1h noise-reversal.

## Notes

Promoted as GP terminal candidate. Not selected in final 0.70×CS_NEG_C1 + 0.30×CS_NEG_VOL formula (dominated by multi-horizon composite). Still validated as independent signal.
