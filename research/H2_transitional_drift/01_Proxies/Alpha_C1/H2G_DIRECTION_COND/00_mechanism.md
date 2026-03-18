---
proxy_id: H2G_DIRECTION_COND
family: Alpha_C1
mechanism: H2 BTC-Diffusion (direction-conditional variant)
formula: CS_z(β_i × r_BTC,2h − r_i,2h) × I(r_BTC,2h > 0) — only active when BTC moved up
status: PENDING
ic_best: TBD
---

# H2G_DIRECTION_COND — Mechanism

## Formula

```
H2G_DIRECTION_COND = CS_z(β_i × r_BTC,2h − r_i,2h) × I(r_BTC,2h > 0)

where β_i = rolling OLS regression slope from last 48 hourly observation pairs:
  β_i = Cov(r_i,1h, r_BTC,1h) / Var(r_BTC,1h)

I(r_BTC,2h > 0) = 1 if BTC moved up over past 2h, 0 otherwise
  (signal is zero when BTC fell — returns 0 scores for all pairs)
```

## Economic Rationale

H2C is symmetric: it identifies both "alts that should have gone up but didn't"
(positive BTC + positive gap = long opportunity) and "alts that should have gone
down but didn't" (negative BTC + negative gap = also scored positively by CS_z).
The direction-conditional variant restricts entries to the positive-BTC case only.

**Why positive-BTC gaps are cleaner:**

1. **Carry asymmetry (spot only):** In a spot-only portfolio, long-only entries
   make sense when BTC is rising. When BTC falls, the "diffusion owed" concept
   implies alts should fall further — but we cannot short. H2G avoids entering longs
   when the diffusion thesis predicts further downside.

2. **Beta sign ambiguity:** When BTC falls, high-β alts are expected to fall more.
   A positive gap (alt didn't fall enough) in a BTC-down environment is ambiguous —
   it could mean the alt has crypto-idiosyncratic support (not a diffusion lag) or
   it could mean the alt will catch up to the downside imminently.

3. **Expected IC improvement:** H2D (BTC-gated H1) showed IC uplift in BTC-up
   environments. H2G tests whether the BTC-direction gate similarly improves H2C IC.

**Potential failure modes:**
- Eliminates ~50% of signal-active timestamps, halving the IC sample size
- IC may be similar to H2C (gating doesn't improve per-observation IC, just reduces
  count) — this would make H2G a weaker PROMOTE candidate despite cleaner rationale
- Better operationalized as a C2 or C3 gate on H2C rather than a separate C1 proxy

## Comparison to H2C

| | H2C (symmetric) | H2G (direction-cond) |
|---|---|---|
| BTC direction | Both up/down | Up only |
| Active timestamps | ~100% | ~50% |
| IC per active ts | +0.042 (full period) | TBD |
| Rationale cleanness | Mixed | Cleaner |

## Signal Family

H2: Expectation Diffusion via BTC — direction-conditional (BTC-up only) variant

## IC Test

Promotion threshold: IC > 0.03, t-stat > 1.5 at 1h forward horizon.

Note: IC computed only over timestamps where r_BTC,2h > 0 (H2G is active).
The unconditional IC comparison must account for reduced sample size.

See `01_ic_test.md` for results after running `signal_search.py`.

## Decision

**Status: PENDING** — awaiting IC test from `signal_search.py`.
