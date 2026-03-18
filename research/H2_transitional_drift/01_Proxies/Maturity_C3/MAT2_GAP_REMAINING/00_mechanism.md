---
proxy_id: MAT2_GAP_REMAINING
family: Maturity_C3
mechanism: H2 BTC-Diffusion — gap closure fraction (diffusion exhaustion)
formula: |r_i,2h| / |β_i × r_BTC,2h| — fraction of expected BTC-linked catch-up already realized
status: PENDING
ic_best: N/A (maturity scaler — IC uplift metric)
---

# MAT2_GAP_REMAINING — Mechanism

## Formula

```
gap_expected = β_i × r_BTC,2h          # BTC-linked return the altcoin "owes"
gap_realized = r_i,2h                   # what the altcoin has actually done
gap_closure  = |r_i,2h| / |β_i × r_BTC,2h|  # fraction of owed adjustment completed

# Clipped to [0, 1]; undefined (None) when |gap_expected| < 0.001 (BTC barely moved)

MAT2_FRESH  = gap_closure < 0.30  (>70% of expected catch-up still outstanding)
MAT2_STALE  = gap_closure > 0.80  (>80% of expected catch-up already realized)
```

## Economic Rationale

H2C's thesis is that altcoins will close their beta-adjusted gap to BTC within
1-6h. The signal is most predictive at entry when the gap is large — meaning the
altcoin has yet to adjust. As the gap closes, the remaining alpha decays: an
altcoin that has already realized 80% of its BTC-linked owed return has very
little remaining diffusion alpha to harvest.

MAT2_GAP_REMAINING directly measures where in the diffusion lifecycle the asset
sits at the moment of signal evaluation:

- **Low gap_closure (< 0.30):** Altcoin has barely moved relative to BTC expectation.
  High remaining alpha. H2C signal is "fresh." IC(H2C | fresh) should be
  significantly above unconditional IC.

- **High gap_closure (> 0.80):** Altcoin has already caught up. Diffusion is
  essentially complete. Entering a long here captures noise, not signal.
  IC(H2C | stale) should be near zero or negative.

**Why this proxy is unique to H2:**
H1 maturity proxies measure reversal lifecycle (how extended is the asset from mean).
MAT2_GAP_REMAINING measures diffusion lifecycle (how much of the BTC-driven
adjustment has already propagated). The two quantities are computed differently
and capture different phenomena.

**Why no H1 equivalent:** H1 does not rely on a BTC-linked "expected return" target.
There is no natural "gap_expected" for H1's mean-reversion signal.

## Data Requirements

Reuses existing H2C computation: β_i and r_BTC,2h are already computed as part
of the H2C signal. No additional data downloads required.

Gap_closure computation is O(n_pairs) per timestamp.

## IC Test

For each timestamp t in training period (Oct–Nov 2024):
1. Compute H2C signal scores
2. Compute gap_closure_i for each active pair
3. Split into fresh bucket (gap_closure < 0.30) and stale bucket (gap_closure > 0.80)
4. Compute IC(H2C, 4h fwd return) within each bucket
5. Compare to unconditional IC

**Approval criterion:** IC(fresh) > IC(unconditional, full period)

See `02_modifier_screen.md` for results after running `h2_modifier_screen.py`.

## Decision

**Status: PENDING** — awaiting IC screen from `h2_modifier_screen.py`.
