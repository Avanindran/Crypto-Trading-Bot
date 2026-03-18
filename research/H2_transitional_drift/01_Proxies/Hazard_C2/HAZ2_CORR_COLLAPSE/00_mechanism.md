---
proxy_id: HAZ2_CORR_COLLAPSE
family: Hazard_C2
mechanism: H2 BTC-Diffusion — BTC-altcoin correlation collapse gate
formula: rolling 48h median Spearman ρ(r_BTC,1h, r_i,1h) across active pairs < 0.40 → block H2 entries
status: PENDING
ic_best: N/A (hazard gate — MaxDD metric)
---

# HAZ2_CORR_COLLAPSE — Mechanism

## Formula

```
For each active pair i (excluding BTC):
  ρ_i = Spearman_rank_correlation(r_BTC,1h[t-48:t], r_i,1h[t-48:t])

median_corr = median(ρ_i  for all active pairs)
block_h2_entry if median_corr < threshold  (default 0.40; sweep: 0.30, 0.40, 0.50)
```

## Economic Rationale

H2's core mechanism is that altcoins are "connected" to BTC via a shared state
variable: all altcoins respond to BTC moves, with a diffusion lag that H2C
measures and exploits. This entire thesis depends on a high BTC-altcoin correlation:
if the crypto market is in an "alt-season" regime, altcoin returns are primarily
driven by alt-specific narratives (project launches, sector rotations, social
media catalysts) rather than BTC spillover.

**When correlation collapses:**
- β_i estimates become unreliable: an OLS slope estimated from 48h of data
  where ρ ≈ 0 is mostly noise; the "expected BTC-linked return" β_i × r_BTC is
  meaningless
- The gap `β_i × r_BTC − r_i` does not measure diffusion lag — it measures
  coincidental deviation driven by alt-specific factors
- H2C IC drops toward zero in low-correlation regimes (H2C mechanism is
  invalidated, not just weakened)

**This gate is H2-unique:** H1's reversal signal (CS_z of negative returns) does
not rely on BTC-altcoin correlation. CS dispersion and relative-strength signals
remain valid in alt-season because they compare altcoins against each other rather
than against BTC. HAZ2_CORR_COLLAPSE has no H1 analogue.

## Historical Context

Alt-season episodes (Oct–Nov 2023, early 2024) showed 48h median BTC-alt
correlation dropping to 0.10–0.25 as altcoins individually outperformed BTC.
During these periods, H2C-like signals would produce near-zero IC because the
β_i × r_BTC prediction bears no relationship to actual alt moves.

## Threshold Sweep

Three thresholds tested: {0.30, 0.40, 0.50}

| Threshold | Expected behavior |
|-----------|------------------|
| 0.30 | Blocks only severe alt-season (ρ < 0.30) — rarely triggers |
| 0.40 | Default — moderate correlation requirement |
| 0.50 | Strict — blocks mild decorrelation episodes |

Selection criterion: threshold that maximizes MaxDD improvement while minimizing
the fraction of timestamps blocked (avoid over-filtering normal market periods).

## Signal Family

C2 Hazard (H2-specific) — alt-season / correlation breakdown gate

## Approval Criterion

MaxDD relative improvement ≥10% AND worst 30-day drawdown improvement ≥5pp
vs ungated H2C baseline.

See `02_modifier_screen.md` for results after running `h2_modifier_screen.py`.

## Decision

**Status: PENDING** — awaiting screen from `h2_modifier_screen.py`.
