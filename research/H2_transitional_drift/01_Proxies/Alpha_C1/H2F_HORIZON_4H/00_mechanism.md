---
proxy_id: H2F_HORIZON_4H
family: Alpha_C1
mechanism: H2 BTC-Diffusion (4h horizon variant)
formula: CS_z(β_i × r_BTC,4h − r_i,4h) where β_i = rolling 48h OLS slope
status: PENDING
ic_best: TBD
---

# H2F_HORIZON_4H — Mechanism

## Formula

```
H2F_HORIZON_4H = CS_z(β_i × r_BTC,4h − r_i,4h)

where β_i = rolling OLS regression slope from last 48 hourly observation pairs:
  β_i = Cov(r_i,1h, r_BTC,1h) / Var(r_BTC,1h)
```

## Economic Rationale

Extends the BTC return measurement window from H2C's 2h to 4h. The hypothesis is
that the 4h window captures sustained directional moves by BTC, which produce
larger and more significant owed adjustments in lagging altcoins. Some diffusion
episodes may span longer than 2h — particularly when BTC's move is driven by a
major macro event (e.g., ETF news, regulatory announcement) that takes several
hours for full price discovery to cascade to altcoins.

**When H2F outperforms H2C:** If the dominant diffusion dynamic occurs over
3-4h cycles (consistent with H1's reversal holding period), then H2F captures the
full extent of the BTC directional impulse, producing a higher IC. The 4h window
also smooths out noise in the BTC return (less susceptible to single-candle spikes).

**Potential failure modes:**
- Over a 4h window, more altcoins will have had time to partially catch up already,
  reducing the remaining gap and the IC of H2F relative to H2C
- H2F effectively measures a "stale" gap — the adjustment opportunity may have
  partially closed by the time the signal is observed
- At the 4h measurement horizon, H2F gap increasingly overlaps with H1's CS
  reversal signal (both capture 4h relative-return rank), reducing orthogonality

## Comparison to H2C

| | H2C (2h) | H2F (4h) |
|---|---|---|
| BTC window | r_BTC,2h | r_BTC,4h |
| β window | 48h 1h-returns | 48h 1h-returns (same) |
| Signal freshness | Medium | Lowest |
| Signal magnitude | Medium | Highest |
| Expected IC | +0.042 (confirmed) | TBD — hypothesis: similar or lower (stale gap) |
| H1 orthogonality | Medium | Lower (increasing overlap) |

## Signal Family

H2: Expectation Diffusion via BTC — 4h horizon variant

## IC Test

Promotion threshold: IC > 0.03, t-stat > 1.5 at 1h forward horizon.

See `01_ic_test.md` for results after running `signal_search.py`.

## Decision

**Status: PENDING** — awaiting IC test from `signal_search.py`.
