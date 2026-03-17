---
proxy_id: TS_ZSCORE_NEG_R6H
test_period: Oct 2024 – Jan 2025
decision: PASS (IC > 0 but < 0.03 promotion threshold)
ic_best: +0.0266 @ 1h (t=+6.91)
---

# TS_ZSCORE_NEG_R6H — IC Test Results

**Source:** `research/signal_search.py` (TS overshoot family)
**Period:** Oct 2024 – Jan 2025 (N=2918 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.027 | * |
| 2h | +0.025 | * |
| 4h | +0.017 | * |
| 6h | +0.012 | * |
| 12h | +0.008 | * |
| 24h | +0.014 | * |

Best IC: **+0.0266 @ 1h** (t=+6.91)

## Decision

**PASS** — IC > 0 and t > 1.0, but IC < 0.03 so does not meet PROMOTE threshold.
Signal is valid but weaker than TS_ZSCORE_NEG_R2H. The 6h TS normalization window captures longer-duration overreactions but these are noisier on a per-asset basis than the cross-sectional ranking.

## Notes

Included in GP search terminal set (gp_search.py). GP results: standalone IC at 4h was +0.014 on train, placing it below promotion quality. Not selected in final formula. Blended form (CS_TS_BLEND_R6H) performs better by combining CS and TS views.
