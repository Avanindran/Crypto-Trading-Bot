---
proxy_id: TS_BB_DIST
test_period: Oct 2024 – Jan 2025
decision: PROMOTED
ic_best: +0.0363 @ 1h (t=+9.44)
---

# TS_BB_DIST — IC Test Results

**Source:** `research/signal_search.py` (TS overshoot family)
**Period:** Oct 2024 – Jan 2025 (N=2900 obs @ 4h horizon; fewer obs due to 24h std requirement)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.036 | * |
| 2h | +0.030 | * |
| 4h | +0.024 | * |
| 6h | +0.020 | * |
| 12h | +0.011 | * |
| 24h | +0.014 | * |

Best IC: **+0.0363 @ 1h** (t=+9.44)

## Decision

**PROMOTE** — IC > 0.03 and t > 1.5 at best horizon.
Nearly identical decay profile to TS_ZSCORE_NEG_R2H. Both measure an asset's deviation below its recent norm via different parameterizations (z-score vs Bollinger distance). Confirms the TS overshoot mechanism is real and robust to operationalization choice.

## Notes

Bollinger band distance = (SMA_6h − price) / (2 × std_price_24h). A positive value means price is below the lower Bollinger band — extended below its own trend. This is a price-space measure whereas TS_ZSCORE_NEG_R2H is a return-space measure. The near-identical IC confirms they are measuring the same phenomenon.
