---
proxy_id: H2D_BTCGATED_H1
family: Alpha_C1
mechanism: H2 BTC-Diffusion (operationalised via BTC gate on H1)
formula: CS_z(−r_2h) × I(|r_BTC,2h| > 0.5%)
status: PASS
ic_best: +0.0190 @ 1h, t=+5.32
---

# H2D_BTCGATED_H1 — Mechanism

## Formula

```
H2D_BTCGATED_H1 = CS_z(−r_2h)   if |r_BTC,2h| > 0.005
                = 0               otherwise
```

The H1 reversal signal is active only when BTC has moved more than 0.5% in the
last 2 hours. When BTC is flat (|r_BTC,2h| ≤ 0.005), the signal is zeroed out.

## Economic Rationale

The H2 mechanism test (research/H2_transitional_drift/03_results/02_mechanism_test.md)
found that H1 reversal IC is strongly conditioned on BTC movement:

- IC when BTC flat (|r_BTC| < 0.5%): +0.024
- IC when BTC moves (|r_BTC| > 0.5%): +0.110
- IC uplift: +0.087

H2D directly operationalises this finding: it turns off the reversal signal when
the BTC diffusion mechanism is inactive (flat BTC = no laggard-catch-up dynamic).
This reduces the noise in the signal and concentrates positions in the regime
where the mechanism is confirmed to be active.

**Relationship to H2C:**
H2D is a "softer" test of the BTC diffusion mechanism: it gates on whether BTC
moved at all (binary), rather than computing the full beta-adjusted gap (continuous).
It is simpler and more directly derived from the mechanism test finding.

## Signal Family

H2: Expectation Diffusion via BTC — BTC-gated H1 operationalisation

## IC Results (from signal_search.py)

| Horizon | IC | t-stat | Gate |
|---------|-----|--------|------|
| 1h | +0.0190 | +5.32 | PASS (not PROMOTE) |

Note: IC passes the minimum gate (IC > 0, t > 1.0) but does not reach PROMOTE
threshold (IC > 0.03). The unconditional IC is diluted by the ~40-50% of periods
when BTC is flat and the signal is zeroed out.

## Decision

**Status: PASS** — IC=+0.0190 at 1h (t=+5.32) passes the gate but does not
reach PROMOTE. The mechanism is valid (confirmed by mechanism test); the signal
is implementation-specific and will improve if the BTC threshold is tuned.

Consider as a C2 modifier (regime gate: only trade when BTC active) rather than
a standalone C1 alpha signal. See H2 decision record for full analysis.
