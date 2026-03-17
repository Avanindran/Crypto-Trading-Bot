---
proxy_id: H2C_BETA_ADJ_GAP
family: Alpha_C1
mechanism: H2 BTC-Diffusion (non-collapsed)
formula: CS_z(β_i × r_BTC,2h − r_i,2h) where β_i = rolling 48h OLS slope
status: PROMOTED
ic_best: +0.0422 @ 1h, t=+9.85
---

# H2C_BETA_ADJ_GAP — Mechanism

## Formula

```
H2C_BETA_ADJ_GAP = CS_z(β_i × r_BTC,2h − r_i,2h)

where β_i = rolling OLS regression slope from last 48 hourly observation pairs:
  β_i = Cov(r_i,1h, r_BTC,1h) / Var(r_BTC,1h)
```

## Economic Rationale

The H2 mechanism holds that BTC diffusion creates a "owed adjustment" in altcoins
that lag their theoretical beta-adjusted return. The gap `β_i × r_BTC,2h − r_i,2h`
measures how much each altcoin has underperformed relative to what its BTC sensitivity
predicts. A positive gap means the altcoin is "owed" upside it has not yet realized.

**Why H2a collapsed and H2c survives:**
The original H2a proxy `CS_z(r_BTC − r_i)` collapses to `CS_z(−r_i)` because r_BTC
is a cross-sectional constant removed by the z-normalization. H2c survives because
β_i × r_BTC varies per asset: assets with higher BTC sensitivity (higher β) receive
a larger expected return target, so the gap `β_i × r_BTC − r_i` discriminates
between assets in a way that survives CS normalization.

**Orthogonality to H1:**
H1 selects laggards by CS rank of raw return. H2c selects by the gap between
beta-predicted return and actual return — these can diverge: an asset can be a
CS laggard (low r_i relative to peers) while having a small H2c gap (if its β is
also low, BTC-driven return was not expected to be high). The overlap increases
when β_i is approximately uniform across the universe.

## Signal Family

H2: Expectation Diffusion via BTC — non-collapsed beta-adjusted variant

## IC Results (from signal_search.py)

| Horizon | IC | t-stat | Gate |
|---------|-----|--------|------|
| 1h | +0.0422 | +9.85 | PROMOTE |
| 2h | see results file | — | — |
| 4h | see results file | — | — |

## Decision

**Status: PROMOTED** — IC=+0.0422 at 1h (t=+9.85) exceeds promotion threshold
(IC > 0.03, t > 1.5). Non-collapsed H2 proxy confirmed as distinct from H1.
Eligible for inclusion in expanded GP search terminal set.

See [../../03_results/01_ic_results.md](../../03_results/01_ic_results.md) for
full IC table across all horizons.
