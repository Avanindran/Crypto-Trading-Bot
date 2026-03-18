---
proxy_id: H2D_BTCGATED_H1
test_period: Oct 2024 – Jan 2025
decision: PASS (IC > 0 but unconditional IC diluted by gating)
ic_best: +0.0190 @ 1h (t=+5.32)
---

# H2D_BTCGATED_H1 — IC Test Results

**Source:** `research/signal_search.py` (H2 non-collapsed family)
**Period:** Oct 2024 – Jan 2025 (N=2924 obs @ 4h horizon)

## IC Decay Profile

| Horizon | IC | Star (t>1.0) |
|---------|----|-------------|
| 1h | +0.019 | * |
| 2h | +0.016 | * |
| 4h | +0.012 | * |
| 6h | +0.006 | * |
| 12h | +0.001 | |
| 24h | −0.004 | |

Best IC: **+0.0190 @ 1h** (t=+5.32)

## Decision

**PASS** — IC > 0 and t > 1.0, but IC < 0.03 so does not reach PROMOTE.

**Why IC is diluted:** When BTC is flat (~40–50% of all periods), the signal is forced to zero — these zero-signal periods contribute negative IC noise (rank correlation of 0 signal vs non-zero forward return). The unconditional IC of +0.019 understates the signal's value when it IS active.

## Conditional IC (from mechanism test)

From `02_Candidates/Signal/02_mechanism_test.md`:
- IC when BTC active (|r_BTC,2h| > 0.5%): +0.110
- IC when BTC flat (|r_BTC,2h| < 0.5%): +0.024

H2D's unconditional IC of +0.019 is the blended average across both regimes, heavily diluted by zero-signal periods.

## Alternative Use: C2 Modifier

As noted in `00_mechanism.md`: consider H2D as a C2 modifier (regime gate: only trade when BTC active) rather than a standalone C1 alpha. This preserves the +0.087 IC uplift finding without the dilution problem.
