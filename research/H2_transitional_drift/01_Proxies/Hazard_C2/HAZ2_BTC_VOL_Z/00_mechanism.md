---
proxy_id: HAZ2_BTC_VOL_Z
family: Hazard_C2
mechanism: H2 BTC-Diffusion — BTC volatility spike gate
formula: BTC 6h realized-vol z-score (48h window) > 1.50 → block H2 entries
status: PENDING
ic_best: N/A (hazard gate — MaxDD metric)
---

# HAZ2_BTC_VOL_Z — Mechanism

## Formula

```
vol_z = (realized_vol_6h_BTC − mean_vol_48h_BTC) / std_vol_48h_BTC
block_h2_entry if vol_z > 1.50
```

Same signal computation as H1's approved HAZ_BTC_VOL_Z. The formula and
threshold are identical; the economic justification is H2-specific.

## Economic Rationale

H2C relies on BTC sustaining its directional move long enough for altcoins to
diffuse. The diffusion window is 1-6h: altcoins are expected to close their
beta-adjusted gap within this period. Elevated BTC volatility (vol z > 1.5) breaks
this assumption in two ways:

1. **BTC reversal risk:** A high-vol BTC environment has frequent and large intraday
   reversals. If BTC reverses within the 1-6h diffusion window, the gap formula
   `β_i × r_BTC,2h − r_i,2h` is misdirected — the alts should now move opposite to
   the original BTC signal. The backtest sweep confirmed that a BTC-reversal exit
   at −0.5% is the dominant H2 risk control (Sortino 0.29 → 1.68), and elevated
   BTC vol is the leading indicator of exactly this reversal risk.

2. **Gap reliability breakdown:** Under high BTC vol, β_i estimates become unreliable
   (the OLS slope from 48h of 1h-returns becomes noisy when individual 1h returns
   are extreme). The gap formula `β_i × r_BTC − r_i` therefore produces
   erratic scores that do not correspond to genuine diffusion lags.

**Distinction from H1 rationale:**
For H1 (mean-reversal), HAZ_BTC_VOL_Z blocks entries because high vol signals
cascade risk — the asset being bought may continue falling rather than reverting.
For H2, the same proxy blocks entries because high BTC vol signals that BTC's
directional move is unstable and likely to reverse before diffusion completes.
Same indicator, different causal mechanism.

## Cross-Validation from Backtest

The BTC-reversal exit sweep in `backtest_simulation.py` found that exiting H2C
positions when BTC reverses by 0.5% since entry reduced MaxDD from −32.2% to
−11.4% and improved Sortino from 0.29 to 1.68. This confirms that BTC reversal
(the event HAZ2_BTC_VOL_Z is designed to predict) is the dominant H2 failure mode.

The vol z-score is the pre-entry leading indicator of reversal risk; the BTC-rev
exit is the intra-position safety net. Together they form a two-layer defense.

## Signal Family

C2 Hazard (H2-specific) — BTC volatility spike gate for diffusion-engine protection

## Approval Criterion

MaxDD relative improvement ≥10% AND worst 30-day drawdown improvement ≥5pp
vs ungated H2C baseline.

See `02_modifier_screen.md` for results after running `h2_modifier_screen.py`.

## Decision

**Status: PENDING** — awaiting screen from `h2_modifier_screen.py`.
