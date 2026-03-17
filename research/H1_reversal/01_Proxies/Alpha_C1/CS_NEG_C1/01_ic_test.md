---
proxy_id: CS_NEG_C1
test_period: Oct 2024 – Jan 2025
decision: PROMOTED (in live GP formula, 0.70 weight)
ic_best: +0.0431 @ 1h (t=+9.36)
---

# CS_NEG_C1 — IC Test Results

**Source:** `research/signal_search.py`
**Period:** Oct 2024 – Jan 2025 (N=2924 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.043 | * |
| 2h | +0.042 | * |
| 4h | +0.042 | * |
| 6h | +0.037 | * |
| 12h | +0.026 | * |
| 24h | +0.024 | * |

Best IC: **+0.0431 @ 1h** (t=+9.36)

## Decision

**PROMOTED — IN LIVE FORMULA (0.70 weight)**
Selected by `gp_search.py` as primary terminal in the GP combination:
`0.70 × CS_NEG_C1 + 0.30 × CS_NEG_VOL`
Train IC at 4h: +0.047 (IC-Sharpe: +0.190); Holdout IC at 4h: +0.066 (t=+10.59)

## Notes

CS_NEG_C1 is the multi-horizon composite C1 score negated. Its flat IC decay (1h–4h all near +0.042) indicates persistent predictive content across horizons — more robust than single-horizon proxies. This is why it wins the GP search: IC-Sharpe (stability-adjusted IC) is highest.
