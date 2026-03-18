---
proxy_id: MAT2_TIME_DECAY
family: Maturity_C3
mechanism: H2 BTC-Diffusion — time since BTC's peak move (diffusion window freshness)
formula: (t − t_peak_BTC) / 6h where t_peak = argmax |r_BTC,1h| in last 6h lookback
status: PENDING
ic_best: N/A (maturity scaler — IC uplift metric)
---

# MAT2_TIME_DECAY — Mechanism

## Formula

```
# Find the timestamp of BTC's largest 1h return in the past 6h
t_peak_BTC = argmax_{t-6h ≤ t' ≤ t}  |r_BTC,1h(t')|

# Time elapsed since BTC's most significant directional move (normalized to [0, 1])
time_decay = (t − t_peak_BTC) / (6h)    # hours since peak, divided by 6

# Clipped to [0, 1]; None if fewer than 6h of BTC history available

MAT2_FRESH = time_decay < 0.40  (BTC's peak move was < 2.4h ago)
MAT2_STALE = time_decay > 0.75  (BTC's peak move was > 4.5h ago)
```

## Economic Rationale

H2's diffusion window has a natural lifetime. Research on crypto intraday dynamics
suggests price information diffuses from BTC to altcoins within 1-6h, after which
the adjustment is largely complete. The H2C signal is most valid immediately after
BTC makes a large directional move, while the diffusion has not yet propagated.

MAT2_TIME_DECAY captures the "age" of the BTC directional impulse that is driving
the current H2C signal:

- **Low time_decay (< 0.40 = BTC moved < 2.4h ago):** Diffusion window is fresh.
  The BTC impulse is recent; altcoins are still adjusting. H2C has maximum
  remaining predictive value.

- **High time_decay (> 0.75 = BTC moved > 4.5h ago):** The triggering BTC move
  occurred long ago. Most diffusion has likely already propagated, even if the
  raw H2C gap formula still shows a non-zero gap (possibly due to noise, other
  idiosyncratic factors, or beta estimation error). Entering H2C positions now
  captures much less of the diffusion alpha.

**Complementarity with MAT2_GAP_REMAINING:**
- MAT2_GAP_REMAINING measures diffusion progress via price (has the alt moved?)
- MAT2_TIME_DECAY measures diffusion progress via time (has enough time passed?)
- The two proxies can agree (large gap + recent BTC move = definitely fresh) or
  disagree (small gap but recent BTC move = alt moved fast, or large gap but old
  BTC move = alt stubbornly lagged — the latter is lower quality H2 signal)

## Data Requirements

Requires BTC 1h return history for the past 6h (6 observations). This is a subset
of the data already loaded for H2C computation.

## IC Test

For each timestamp t in training period (Oct–Nov 2024):
1. Compute H2C signal scores
2. Compute time_decay for the BTC key at timestamp t
3. Split into fresh bucket (time_decay < 0.40) and stale bucket (time_decay > 0.75)
4. Compute IC(H2C, 4h fwd return) within each bucket
5. Compare to unconditional IC

**Approval criterion:** IC(fresh) > IC(unconditional, full period)

See `02_modifier_screen.md` for results after running `h2_modifier_screen.py`.

## Decision

**Status: PENDING** — awaiting IC screen from `h2_modifier_screen.py`.
