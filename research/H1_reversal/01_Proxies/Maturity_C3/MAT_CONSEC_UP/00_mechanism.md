---
proxy_id: MAT_CONSEC_UP
family: Maturity_C3
formula: fraction of last 6 bars with positive r_1h > 0.75 → block entry
status: REJECTED
ic_best: N/A
---

# MAT_CONSEC_UP — Mechanism

## Formula

Fraction of the last 6 one-hour bars with positive returns > 0.75 (i.e., 5 or more out
of 6 bars positive) → block new entry

```
consec_up = mean(r_1h[-6:] > 0)
block_entry if consec_up > 0.75
```

## Economic Rationale

Five or six consecutive up-bars in a row suggest persistent buying pressure over the
last 6 hours. In the C3 maturity framework, this is a short-horizon momentum saturation
signal: the asset has been rising consistently, indicating that the diffusion event may
have fully played out over the most recent bars. Entering after 5+ consecutive up-bars
means buying into a streak, which is statistically likely to break. However, in practice,
6-bar streaks are short enough that the base rate of such sequences occurring during
genuine momentum phases is high — the proxy fires frequently during sustained uptrends
and blocks profitable continuation entries along with the overextended ones.

## Signal Family

C3 Maturity — short-horizon consecutive-up bar gate

## Decision

**Status:** REJECTED — IC uplift −0.0197; the 6-bar window is too short to distinguish
genuine overextension from normal momentum; fires too frequently during healthy uptrends
and blocks profitable entries without adding meaningful protection against overextended
positions.
