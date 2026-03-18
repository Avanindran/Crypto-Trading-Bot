---
proxy_id: H2C_BETA_ADJ_GAP
test_period: Oct 2024 – Jan 2025
decision: PROMOTED
ic_best: +0.0422 @ 1h (t=+9.85)
---

# H2C_BETA_ADJ_GAP — IC Test Results

**Source:** `research/signal_search.py` (H2 non-collapsed family)
**Period:** Oct 2024 – Jan 2025 (N=2914 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.042 | * |
| 2h | +0.036 | * |
| 4h | +0.029 | * |
| 6h | +0.027 | * |
| 12h | +0.016 | * |
| 24h | +0.011 | * |

Best IC: **+0.0422 @ 1h** (t=+9.85)

## Decision

**PROMOTE** — IC > 0.03 and t > 1.5 at best horizon. Non-collapsed H2 proxy confirmed as distinct from H1.

The beta-adjusted gap `β_i × r_BTC − r_i` survives CS normalization because β_i varies per asset. An altcoin with β_i = 1.2 facing r_BTC = +1% has an expected return of +1.2%; if its actual return was +0.5%, the gap is +0.7%. An altcoin with β_i = 0.6 facing the same BTC move has gap = +0.6% − 0.5% = +0.1%. The cross-section discriminates.

## Relationship to H1

H2C and H1 (CS_NEG_C1) can diverge: an asset that is a CS laggard (low r vs peers) may have a small H2C gap if its β is also low. Correlation between H2C and H1 signals is less than 1.0 — confirmed by separate IC measurements.

## Notes

Eligible as GP terminal. Not yet tested in gp_search.py terminal set (which used H1/H5 family only). Candidate for next GP expansion run.
