# Regime Overlay — Component Proxy Specs

**Status:** DEPLOYED
**Written:** 2026-03-17
**Mechanism reference:** [00_mechanism.md](00_mechanism.md)

---

## LSI Components

### BTC_vol_z (weight: 0.45)

```
realized_vol_6h_BTC = std(r_BTC, last 6 hourly returns)
baseline_vol_48h    = mean(realized_vol_6h_BTC, last 48h window)
std_vol_48h         = std(realized_vol_6h_BTC, last 48h window)
BTC_vol_z           = (realized_vol_6h_BTC − baseline_vol_48h) / (std_vol_48h + ε)
LSI_btc_vol         = clip(BTC_vol_z / 3.0, 0, 1)    # normalize z-score to [0,1]
```

**Rationale:** BTC volatility is the primary leading indicator of crypto market stress. BTC is the most liquid asset; its volatility spikes are the first signal of liquidity pressure propagating to altcoin pairs. Weight = 0.45 (dominant).

### spread_z (weight: 0.25)

```
spread_i,t          = (ask_i,t − bid_i,t) / mid_i,t    (relative spread)
mean_spread_t       = mean over all pairs i of spread_i,t
baseline_spread     = mean(mean_spread_t, last 48 snapshots)
std_spread          = std(mean_spread_t, last 48 snapshots)
spread_z_raw        = (mean_spread_t − baseline_spread) / (std_spread + ε)
LSI_spread          = clip(spread_z_raw / 3.0, 0, 1)
```

**Rationale:** Spread widening is a direct measure of market-maker withdrawal. When spreads widen, market makers are either reducing inventory (less willing to provide liquidity) or facing elevated adverse selection risk. Both states reduce the corrective flow that H1 depends on.

### dispersion_z (weight: 0.15)

```
cs_disp_t           = std(r_i,1h, over all pairs) at time t
baseline_disp       = mean(cs_disp_t, last 48 periods)
std_disp            = std(cs_disp_t, last 48 periods)
disp_z_raw          = (cs_disp_t − baseline_disp) / (std_disp + ε)
LSI_dispersion      = clip(disp_z_raw / 3.0, 0, 1)
```

**Rationale:** Cross-sectional dispersion spikes during sector rotations and regime transitions, when correlated assets suddenly move at different speeds. High dispersion can indicate that the cross-sectional z-normalization is picking up regime noise rather than genuine mean-reversion candidates. Weight = 0.15 (secondary signal, not a crisis indicator by itself).

### FNG_component (weight: 0.15)

```
FNG_value           = Alternative.me Fear & Greed Index (0–100)
FNG_component       = 0 if FNG_value < 25   (Fear → no greed stress)
                    = 1 if FNG_value > 75   (Extreme Greed → crowded longs)
                    = linear interpolation in (25, 75)
```

**Source:** Alternative.me `/fng/?limit=1` (free, no auth). Refreshed once per 24h.

**Rationale:** Extreme greed signals crowded long positioning. When the market is in extreme greed, everyone is already long — the corrective flow for H1 (buying laggards) faces a headwind because all participants are already positioned in the direction H1 would predict. A sudden reversal in extreme-greed conditions produces violent drawdowns. Weight = 0.15 (leading indicator, not contemporaneous like vol/spread).

---

## MPI — Momentum Persistence Index

```
btc_hourly_returns  = r_BTC at each hourly timestamp, last 48 periods
MPI                 = fraction of btc_hourly_returns > 0

MPI > 0.50 → BTC trending up (positive momentum)
MPI < 0.30 → BTC in chop or mild downtrend
```

**Rationale:** MPI answers "is BTC in a genuine uptrend?" A reversal signal requires non-trending conditions to work cleanly. If BTC is drifting downward (MPI < 0.30), the upward correction H1 expects from laggards is more likely to be a brief consolidation before continuing lower.

---

## FEI — Forward Expectation Index

FEI is a composite that estimates whether the forward 4h period is likely to be favorable for H1:

```
FEI_components:
  - MPI contribution: min(MPI / 0.5, 1)     # normalized momentum score
  - LSI_inverse: 1 − LSI                     # stress-adjusted opportunity
  - BTC_vol_normalized: ...                  # moderate vol is good (trending)

FEI = weighted composite (internal computation in regime.py)
```

FEI > 0.55 is the minimum threshold for TREND_SUPPORTIVE classification.

---

## Regime Gross Allocation Caps

| Regime | λ_t | exp(−λ) | Gross Cap | Max Positions |
|--------|-----|---------|-----------|--------------|
| TREND_SUPPORTIVE | 0.3 | 0.74 | 85% NAV | 5 positions |
| NEUTRAL_MIXED | 0.8 | 0.45 | 65% NAV | 3 positions |
| HAZARD_DEFENSIVE | 4.0 | 0.018 | 0% NAV (no new entries) | 0 new |
| EMERGENCY | 10.0 | ≈0 | 0% NAV (exit all) | Emergency exit |

---

## Configuration Reference

All parameters live in `config.py`:

```python
LSI_WEIGHT_BTC_VOL = 0.45
LSI_WEIGHT_SPREAD  = 0.25
LSI_WEIGHT_DISP    = 0.15
LSI_WEIGHT_FNG     = 0.15

LSI_THRESHOLD_EMERGENCY  = 0.80
LSI_THRESHOLD_DEFENSIVE  = 0.60
LSI_THRESHOLD_CAUTION    = 0.40
MPI_THRESHOLD_CHOP       = 0.30
FEI_THRESHOLD_HIGH       = 0.55
FNG_REFRESH_HOURS        = 24.0
```
