---
proxy_id: CS_NEG_VOL
test_period: Oct 2024 – Jan 2025
decision: PROMOTED (in live GP formula, 0.30 weight; H5 stability)
ic_best: +0.0759 @ 24h (t=+13.26)
---

# CS_NEG_VOL — IC Test Results (H5 Stability)

**Source:** `research/signal_search.py` (H5 stability family section)
**Period:** Oct 2024 – Jan 2025 (N=2924 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.035 | * |
| 2h | +0.043 | * |
| 4h | +0.049 | * |
| 6h | +0.057 | * |
| 12h | +0.070 | * |
| 24h | +0.076 | * |

Best IC: **+0.0759 @ 24h** (t=+13.26)

## Stability Screen Context

From `02_stability_screen.md`: H5 family tested `H5_sharpe_6h`, `H5_sharpe_24h`, `H5_sortino_6h`, `H5_neg_vol`.
Only `H5_neg_vol` passed — the risk-adjusted variants showed **negative** IC (they anti-select).

## Decision

**PROMOTED — IN LIVE FORMULA (0.30 weight; H5 stability filter)**
Selected by `gp_search.py` as secondary terminal:
`0.70 × CS_NEG_C1 + 0.30 × CS_NEG_VOL`
GP selection rationale: CS_NEG_VOL has a long IC tail (peaks at 24h, stays positive); it diversifies CS_NEG_C1 which peaks at 1h.

## Notes

CS_NEG_VOL (low realized volatility = low vol = more stable mover) selects calm, steady-trending assets over noisy ones. This is orthogonal to the short-term reversal mechanism in CS_NEG_C1 — it filters out assets whose recent moves are explained by volatility expansion rather than diffusion lag.
