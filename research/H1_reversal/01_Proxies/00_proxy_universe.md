# H1 Reversal — Proxy Universe (Scope Inventory)

**Status:** FROZEN before IC testing (pre-committed 2026-03-17)
**Mechanism:** H1 Transient Expectation Overshoot — see [../00_mechanism.md](../00_mechanism.md)

All proxies categorised into three conditions: C1 (alpha direction), C2 (hazard gate), C3 (maturity scaler).

---

## C1 — Alpha Direction Proxies (9 total)

Cross-sectional rank reversal proxies: select assets that are laggards vs peers or vs own history.

| Proxy ID | Formula | Status | IC_best | Notes |
|----------|---------|--------|---------|-------|
| `CS_NEG_R1H` | `CS_z(−r_1h)` | PROMOTED | +0.049 @ 1h | Short-horizon reversal |
| `CS_NEG_R2H` | `CS_z(−r_2h)` | PROMOTED | +0.047 @ 1h | Medium-short reversal |
| `CS_NEG_R6H` | `CS_z(−r_6h)` | PROMOTED | +0.040 @ 2h | PRIMARY horizon proxy |
| `CS_NEG_C1` | `CS_z(−C1_raw)` | **PROMOTED (live, 0.70 wt)** | +0.043 @ 1h | Multi-horizon composite |
| `CS_NEG_VOL` | `CS_z(−σ_6h)` | **PROMOTED (live, 0.30 wt)** | +0.076 @ 24h | H5 stability; long IC tail |
| `TS_ZSCORE_NEG_R6H` | `CS_z(−(r_6h − μ_48h)/σ_48h)` | PASS | +0.027 @ 1h | TS self-comparison; IC < 0.03 |
| `TS_ZSCORE_NEG_R2H` | `CS_z(−(r_2h − μ_48h)/σ_48h)` | PROMOTED | +0.036 @ 1h | 2h TS overshoot |
| `TS_BB_DIST` | `CS_z((SMA_6h − price)/(2σ_24h))` | PROMOTED | +0.036 @ 1h | Bollinger distance (price space) |
| `CS_TS_BLEND_R6H` | `0.5×CS_z(−r_6h) + 0.5×TS_z(−r_6h)` | PROMOTED | +0.035 @ 1h | CS+TS blend; flatter decay |

**Live formula:** `0.70 × CS_NEG_C1 + 0.30 × CS_NEG_VOL`
Selected by `gp_search.py` (IC-Sharpe: +0.190 train; +0.066 holdout at 4h).

---

## C2 — Hazard Gate Proxies (6 total)

Modifier screens: applied as binary gates suppressing new entries when market regime is stressed.
Gate criterion: MaxDD relative improvement ≥ 10% AND worst-30d DD improvement ≥ 5pp.

| Proxy ID | Formula | Status | MaxDD Improv | Notes |
|----------|---------|--------|-------------|-------|
| `HAZ_BTC_VOL_Z` | `σ_BTC_6h z-score (48h) > 1.50` | **APPROVED** | +17.84% | BTC vol spike = stress |
| `HAZ_FNG_EXTREME` | `Fear & Greed > 75` | **APPROVED** | +17.6% | Extreme greed precedes corrections |
| `HAZ_CS_DISPERSION` | `CS return dispersion < threshold` | REJECTED | — | Panic correlation gate |
| `HAZ_SPREAD_Z` | `Bid-ask spread z-score > threshold` | REJECTED | — | Liquidity stress proxy |
| `HAZ_MPI_CHOP` | `MPI < 0.30` | REJECTED | — | Directional chop gate |
| `HAZ_BTC_DRAWDOWN` | `BTC drawdown from 24h high > 2%` | REJECTED | — | Active BTC selloff gate |

See individual `02_modifier_screen.md` files for full results.

---

## C3 — Maturity Scaler Proxies (7 total)

Modifier screens: restrict entry when an asset's move is already extended (drift capacity exhausted).
Gate criterion: IC(fresh, proxy < threshold) > IC(unconditional).

| Proxy ID | Formula | Status | IC uplift | Notes |
|----------|---------|--------|-----------|-------|
| `MAT_VOL_RATIO` | `vol_6h / median_vol_48h > 2×` | **APPROVED** | +0.064 | Strongest; volume exhaustion signal |
| `MAT_FUNDING_RATE` | `Binance perp funding rate > threshold` | **APPROVED** | +0.010 | Crowded longs → capped upside |
| `MAT_PCT_RANK` | `r_6h pct_rank vs 48h > 0.72` | REJECTED | — | No IC uplift standalone |
| `MAT_SMA_EXT` | `(price − SMA_12h) / SMA_12h > threshold` | REJECTED | — | Price extension from SMA |
| `MAT_RSI_PROXY` | `RSI(14) > 70` | REJECTED | — | Overbought filter |
| `MAT_TS_ZSCORE_R6H` | `(r_6h − μ_48h)/σ_48h > 1.5σ` | REJECTED | — | Parametric pct_rank analogue |
| `MAT_CONSEC_UP` | `frac of last 6 bars up > 0.75` | REJECTED | — | Streak persistence |

See individual `02_modifier_screen.md` files for full results.

---

## Full Formula Reference

```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)

where:
  C1_i    = 0.70 × CS_NEG_C1_i  + 0.30 × CS_NEG_VOL_i
  λ_t     = regime hazard rate (HAZ_BTC_VOL_Z ≥ 10.0 when triggered)
  M_t_i   = composite maturity (MAT_VOL_RATIO + MAT_FUNDING_RATE active)
  HAZ_FNG_EXTREME = LSI component (FNG > 75 → LSI elevated → λ_t increases)
```
