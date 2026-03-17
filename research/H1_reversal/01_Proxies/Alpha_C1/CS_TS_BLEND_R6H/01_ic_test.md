---
proxy_id: CS_TS_BLEND_R6H
test_period: Oct 2024 – Jan 2025
decision: PROMOTED
ic_best: +0.0347 @ 1h (t=+8.37)
---

# CS_TS_BLEND_R6H — IC Test Results

**Source:** `research/signal_search.py` (TS overshoot family)
**Period:** Oct 2024 – Jan 2025 (N=2918 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.035 | * |
| 2h | +0.034 | * |
| 4h | +0.027 | * |
| 6h | +0.020 | * |
| 12h | +0.010 | * |
| 24h | +0.017 | * |

Best IC: **+0.0347 @ 1h** (t=+8.37)

## Decision

**PROMOTE** — IC > 0.03 and t > 1.5 at best horizon.
The 50/50 blend of CS and TS z-scores dampens each component's noise. IC decay is notably flatter than individual CS or TS signals — 1h to 2h ratio is 0.035/0.034 ≈ 1.03 vs 0.049/0.041 ≈ 1.20 for CS_NEG_R1H. This suggests diversification benefit.

## GP Search Performance

From `gp_search.py` expanded terminal set results:
`0.70×CS_TS_BLEND_R6H + 0.30×H5_neg_vol` — Train IC-Sharpe: +0.159, Holdout IC: +0.049
vs champion: `0.70×CS_NEG_C1 + 0.30×CS_NEG_VOL` — Train IC-Sharpe: +0.190, Holdout IC: +0.066
Blend formula does not outperform champion. CS_NEG_C1 (multi-horizon composite) captures the CS-TS diversification more efficiently than a single-horizon blend.
