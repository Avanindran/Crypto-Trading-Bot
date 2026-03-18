# H2 Engine Integration Spec — Bot Architecture

**Written:** 2026-03-18
**Status:** Research complete; bot integration pending
**Depends on:** `backtest_simulation.py` H2 final sweep results

---

## Overview

This document specifies how the H2C signal (BTC-diffusion expectation gap) integrates into the
live bot without violating the trade aggregation constraint.

The key constraint: **H2 must blend at signal level, not run as an independent strategy.**
Both engines share the same asset universe and produce one combined target portfolio per period.

---

## Architecture: Where H2 Lives in the Bot

```
main.py (60s loop)
  │
  ├── market_cache.py          — price history (unchanged)
  ├── feature_builder.py       — per-asset features (unchanged)
  ├── funding_rate_client.py   — funding rates (unchanged)
  │
  ├── signals.py               ← H2C INTEGRATED HERE
  │   Step 1: compute H1 score vector (existing)
  │   Step 2: if BTC regime = TREND_ACTIVE:
  │     a. compute H2C score vector (needs beta_hist state)
  │     b. apply MAT2_TIME_DECAY gate
  │     c. blend: score_i = α × H2C_z_i + (1−α) × H1_z_i, re-z-score
  │   Step 3: if TREND_FLAT or H2C unavailable: use H1 only
  │
  ├── regime.py                — LSI/MPI/FEI → (RegimeState, λ_t) (unchanged)
  ├── ranking.py               — PositionScore formula (unchanged)
  ├── allocator.py             — target weights (unchanged)
  └── order_manager.py         — one set of trades (unchanged, no H2-specific logic needed)
```

The key insight: **everything downstream of `signals.py` receives a single blended score vector**.
`ranking.py`, `allocator.py`, and `order_manager.py` require no changes.

---

## State Management

H2C requires a stateful rolling beta history that persists across bot restarts.

### `beta_hist` structure

```python
beta_hist: Dict[str, Tuple[List[float], List[float]]]
# pair → (r_i_hourly_last48, r_btc_hourly_last48)
```

### Persistence

Save to `state.json` alongside existing state:

```json
{
  "positions": {...},
  "last_exit_times": {...},
  "beta_hist": {
    "ETHUSDT": {"r_i": [0.001, -0.002, ...], "r_btc": [0.003, -0.001, ...]},
    ...
  }
}
```

On startup: load `beta_hist` from `state.json`. If missing (first run or corruption): initialize
empty — H2C will be inactive for the first 24h while beta_hist accumulates (this is safe; H1
continues to operate normally during the burn-in period).

### Update cadence

Beta histories are updated every loop iteration (same cadence as price history):

```python
# In signals.py, every loop:
r_btc_1h = compute_return(btc_prices, ts, 1.0)
if r_btc_1h is not None:
    for pair in active_pairs:
        r_1h = compute_return(prices[pair], ts, 1.0)
        if r_1h is not None:
            beta_hist[pair]["r_i"].append(r_1h)
            beta_hist[pair]["r_btc"].append(r_btc_1h)
            # Keep last 48h
            beta_hist[pair]["r_i"] = beta_hist[pair]["r_i"][-48:]
            beta_hist[pair]["r_btc"] = beta_hist[pair]["r_btc"][-48:]
```

---

## H2C Signal Computation

### H2C score (per-asset gap)

```python
def compute_h2c_scores(prices, btc_prices, beta_hist, ts) -> Optional[Dict[str, float]]:
    """CS_z(β_i × r_BTC,2h − r_i,2h).

    Returns None if < 4 assets have sufficient beta history (< 24h).
    Returns None if MAT2_TIME_DECAY gate is stale (time_decay ≥ MAT2_THRESH).
    """
    r_btc_2h = compute_return(btc_prices, ts, 2.0)
    if r_btc_2h is None:
        return None

    # MAT2_TIME_DECAY gate
    time_decay = compute_btc_time_decay(btc_prices, ts)
    if time_decay is None or time_decay >= MAT2_TIME_THRESH:
        return None  # diffusion window stale or BTC quiescent

    gaps = {}
    for pair in active_pairs:
        hist = beta_hist.get(pair, {"r_i": [], "r_btc": []})
        if len(hist["r_i"]) < 24:
            continue  # need 24h burn-in
        r_2h = compute_return(prices[pair], ts, 2.0)
        if r_2h is None:
            continue
        beta = ols_beta(hist["r_i"], hist["r_btc"])
        gaps[pair] = beta * r_btc_2h - r_2h

    if len(gaps) < 4:
        return None
    return cross_sectional_z(gaps)
```

### MAT2_TIME_DECAY helper

```python
def compute_btc_time_decay(btc_prices, ts) -> Optional[float]:
    """(t − t_peak_BTC) / 6h. Returns None if BTC quiescent (|r_peak| < 0.1%)."""
    best_abs_r, best_lag = 0.0, 0
    for lag in range(7):
        r = compute_return(btc_prices, ts - lag * MS_PER_H, 1.0)
        if r is not None and abs(r) > best_abs_r:
            best_abs_r, best_lag = abs(r), lag
    return None if best_abs_r < 0.001 else best_lag / 6.0
```

---

## Regime-Conditional Blending

```python
def compute_blended_signal(h1_scores, h2_scores, r_btc_2h, alpha) -> Dict[str, float]:
    """Blend H1 and H2C at signal level. Returns one unified z-score vector."""
    btc_active = abs(r_btc_2h) >= BTC_ACTIVE_THRESHOLD  # 0.5%

    if not btc_active or h2_scores is None:
        return h1_scores  # TREND_FLAT: H1 only

    # TREND_ACTIVE: blend at signal level
    blended = {}
    for pair in h1_scores:
        h1_z = h1_scores.get(pair, 0.0)
        h2_z = h2_scores.get(pair, 0.0)
        blended[pair] = alpha * h2_z + (1 - alpha) * h1_z

    return cross_sectional_z(blended)  # re-normalize after blend
```

The `alpha` value comes from the backtest dual-engine sweep (`alpha_TREND_OPT`).

---

## Parameters to add to `config.py`

From `backtest_simulation.py` H2 final (run 2026-03-18):

```python
# ── H2C BTC-Diffusion Engine ──────────────────────────────────────────────────
H2C_ALPHA_TREND       = 0.0     # alpha_TREND_OPT=0.0: H1 alone outperforms blends in training
                                  # Note: H2C is better as standalone engine (Sortino=1.99,
                                  # Calmar=20.25) than as H1 portfolio complement (reduces Sortino)
H2C_BTC_ACTIVE_THRESH = 0.003   # |r_BTC,2h| >= 0.3% to activate H2C (H2_GATE_OPT from sweep E)
H2C_BTC_REV_EXIT      = -0.01   # Exit if BTC fell -1.0% since entry (H2_BTCREV_OPT sweep C)
H2C_HOLD_CAP_HOURS    = 6       # Force-exit after 6h (H2_HOLDCAP_OPT sweep D)
H2C_VOL_Z_THRESH      = 0.75    # HAZ2_BTC_VOL_Z gate (H2_Z_OPT; no discriminatory power in training)
H2C_MAT2_TIME_THRESH  = None    # MAT2_TIME_DECAY: not applied (filter hurts full-strategy metrics)
H2C_BETA_WINDOW       = 48      # OLS window in hours
H2C_BETA_MIN_OBS      = 24      # Min observations before beta is usable
```

**Key finding:** `alpha_TREND_OPT = 0.0` means H2C does not improve the combined portfolio in the training period. However, H2C standalone (all modifiers applied) achieves ret=+74.0%, Sortino=1.99, Calmar=20.25, MaxDD=−20.6% — substantially better than stale baseline (Sortino=1.34, Calmar=2.96). H2C is validated for standalone operation but adds no marginal benefit when blended with H1 in training.

---

## HAZ2_BTC_VOL_Z Gate

The BTC volatility z-score gate for H2 is already partially captured by the existing LSI
(which has `LSI_WEIGHT_BTC_VOL = 0.45`). When BTC vol is high, LSI rises → λ_t increases → all
positions suppressed via `exp(−λ_t)`.

However, the H2-specific vol gate (`H2_Z_OPT` from the B sweep) may differ from the H1 gate:
- H1: high vol = stressed market = reverse reversal signal → gate tighter
- H2: high vol = large BTC moves = potentially MORE diffusion opportunities

If `H2_Z_OPT` from the backtest is substantially higher than `LSI_THRESHOLD_DEFENSIVE`, a
separate H2-specific vol check should be added to `compute_h2c_scores()`:

```python
btc_vol_z = compute_btc_vol_zscore(btc_prices, ts, window=6)  # 6h realized vol
if btc_vol_z is not None and btc_vol_z > H2C_VOL_Z_THRESH:   # from H2_Z_OPT
    return None  # H2 channel invalidated
```

---

## Rollout Plan

1. **After backtest results** — fill in `H2C_ALPHA_TREND`, `H2C_MAT2_TIME_THRESH`, `H2C_VOL_Z_THRESH`
2. **Add `beta_hist` to `state.json`** — update `state.py` `save_state()` and `load_state()`
3. **Update `signals.py`** — add `compute_h2c_scores()`, `compute_btc_time_decay()`, `compute_blended_signal()`
4. **Update `config.py`** — add H2C parameters from Step 1
5. **Test** — run `tests/test_scoring.py`; add H2C-specific test case
6. **Deploy** — commit before restart; monitor for 30+ minutes

---

## Scope Boundaries

- `ranking.py`, `allocator.py`, `order_manager.py` — no changes needed
- `regime.py` — no changes needed (LSI already captures BTC vol)
- OOS window (Dec–Jan) — never touched during integration
- No new API calls — H2C uses existing `MarketCache` BTC price history
