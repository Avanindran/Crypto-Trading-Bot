---
proxy_id: H2A_CS_RELATIVE
family: Alpha_C1
mechanism: H2 BTC-Diffusion (collapsed identity)
formula: CS_z(r_i,h − r_BTC,h) = CS_z(r_i,h) mathematically
status: COLLAPSED
ic_best: N/A — mathematical identity with H1
---

# H2A_CS_RELATIVE — Mechanism

## Formula

```
H2A_CS_RELATIVE = CS_z(r_i,h − r_BTC,h)
```

## Economic Rationale (Intended)

The H2 mechanism holds that BTC information diffuses to altcoins with a lag. The proxy was intended to measure each altcoin's return relative to BTC, capturing the "owed" BTC-implied return not yet realized.

## Why It Collapses

`r_BTC,h` at any timestamp t is a **cross-sectional constant** — the same scalar for all N assets in the universe. CS z-normalization removes any constant added to all inputs:

```
CS_z(r_i − c) = CS_z(r_i)   for any scalar c
```

Therefore `CS_z(r_i − r_BTC) = CS_z(r_i)`, which is identical to the H1 proxy negated.

**This is a mathematical identity, not an empirical finding.** H2A provides zero independent information beyond H1 in any cross-sectional framework.

## IC Validation

Confirmed in `02_Candidates/Signal/01_ic_results.md`: H2A IC at all horizons equals H1 IC within numerical precision (diff < 0.001).

## Decision

**COLLAPSED** — zero independent signal. Not eligible for GP terminal set.
