---
proxy_id: H2E_HORIZON_1H
family: Alpha_C1
mechanism: H2 BTC-Diffusion (1h horizon variant)
formula: CS_z(β_i × r_BTC,1h − r_i,1h) where β_i = rolling 48h OLS slope
status: PENDING
ic_best: TBD
---

# H2E_HORIZON_1H — Mechanism

## Formula

```
H2E_HORIZON_1H = CS_z(β_i × r_BTC,1h − r_i,1h)

where β_i = rolling OLS regression slope from last 48 hourly observation pairs:
  β_i = Cov(r_i,1h, r_BTC,1h) / Var(r_BTC,1h)
```

## Economic Rationale

Identical to H2C but uses a 1h BTC return window instead of 2h. The hypothesis
is that the freshest possible diffusion signal occurs immediately after BTC moves:
within the first hour of a BTC directional print, altcoins that have not yet
adjusted are at peak "owed adjustment." Using a 1h gap may capture entries closer
to the inflection point of diffusion onset.

**When H2E outperforms H2C:** If diffusion typically completes within 1-2h, then
a 1h gap measurement is more "current" — it reflects adjustment owed on the most
recent BTC move, with less partial catch-up already embedded. Noise is higher
because a single 1h BTC return is smaller in magnitude and noisier than a 2h
return, which weakens the IC.

**Potential failure modes:**
- 1h BTC return is too small to dominate noise in the gap formula
- The β estimate (48h of 1h returns) remains the same as H2C, so if BTC barely
  moved in the last 1h, the gap formula produces near-zero signal regardless of β

## Comparison to H2C

| | H2C (2h) | H2E (1h) |
|---|---|---|
| BTC window | r_BTC,2h | r_BTC,1h |
| β window | 48h 1h-returns | 48h 1h-returns (same) |
| Signal freshness | Medium | Highest |
| Signal magnitude | Medium | Lowest |
| Expected IC | +0.042 (confirmed) | TBD — hypothesis: lower due to noise |

## Signal Family

H2: Expectation Diffusion via BTC — 1h horizon variant

## IC Test

Promotion threshold: IC > 0.03, t-stat > 1.5 at 1h forward horizon.

See `01_ic_test.md` for results after running `signal_search.py`.

## Decision

**Status: PENDING** — awaiting IC test from `signal_search.py`.
