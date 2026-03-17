# Proxy Universe — Pre-Committed Inventory

**Written:** 2026-03-17 | **Status:** FROZEN before signal_search.py first run

No IC testing has been performed. All proxies declared from mechanism reasoning in `01_mechanism_universe.md`.

---

## H1: Short-Term Cross-Sectional Reversal — Proxy Family

All H1 proxies use cross-sectional z-normalization (CS z-score) as the final step. Each proxy selects assets that have UNDERPERFORMED the cross-section recently, on the hypothesis that they will outperform over the next 1–4h.

| Proxy ID | Formula | Input columns | Mechanism link |
|----------|---------|---------------|----------------|
| H1_neg_r1h | CS_z(-r_1h) | close col 4 | Reverse of 1h return rank; selects assets that fell most in last 1h |
| H1_neg_r2h | CS_z(-r_2h) | close col 4 | Reverse of 2h return rank |
| H1_neg_r6h | CS_z(-r_6h) | close col 4 | **Primary proxy** — exact reverse of C1's primary input; expected IC ≈ +|IC_C1| |
| H1_neg_r24h | CS_z(-r_24h) | close col 4 | Reverse of 24h return rank; tests longer-horizon reversal |
| H1_neg_c1 | CS_z(-C1_raw) | close col 4 | Exact negative of current C1 composite; if C1 IC = -0.038, this should IC ≈ +0.038 |

**Decision gate:** IC > 0 AND t > 1.0 at ANY of the 6 forward horizons (1h, 2h, 4h, 6h, 12h, 24h).

**GP search space (declared here, before any IC data):**
If H1 passes IC gate, GP search may combine H1 proxies:
- Terminals: {H1_neg_r1h, H1_neg_r2h, H1_neg_r6h, H1_neg_c1}
- Operators: weighted linear sum only (w1*P1 + w2*P2, w1+w2=1)
- Depth limit: 1 (linear combination)
- Objective: IC Sharpe at best passing horizon, inner 2-month training split
- Holdout: last 1 month of current period

---

## H2: BTC Leader-Laggard — Proxy Family

**H2a (catch-up sub-family):** Measure how much each altcoin has UNDERPERFORMED BTC recently. Negative values = lagged BTC = expected to catch up.

| Proxy ID | Formula | Input columns | Mechanism link |
|----------|---------|---------------|----------------|
| H2a_neg_rel_btc_r1h | CS_z(-(alt_r_1h - btc_r_1h)) = CS_z(btc_r_1h - alt_r_1h) | close col 4 | Altcoins that underperformed BTC in last 1h → catch up |
| H2a_neg_rel_btc_r2h | CS_z(-(alt_r_2h - btc_r_2h)) | close col 4 | **Primary proxy** — 2h BTC-relative underperformance |
| H2a_neg_rel_btc_r6h | CS_z(-(alt_r_6h - btc_r_6h)) | close col 4 | 6h BTC-relative underperformance; longer catch-up window |

**H2b (lagged BTC predictor sub-family):** Use BTC's past return as a predictor for all altcoins' future return. This is NOT a cross-sectional signal (same value for all alts) — tested as a market-timing signal using Pearson correlation between lagged BTC return and mean altcoin forward return.

| Proxy ID | Formula | Test method | Mechanism link |
|----------|---------|-------------|----------------|
| H2b_btc_lag1h | btc_r_1h at (t-1h) | Correlation with mean_altcoin_fwd_r | Does BTC 1h ago predict altcoin fwd return? |
| H2b_btc_lag2h | btc_r_2h at (t-2h) | Correlation with mean_altcoin_fwd_r | 2h lag BTC predictor |

**Decision gate:** H2a: same IC gate as H1. H2b: Pearson r > 0.05 and t > 1.0 between lagged BTC return and mean cross-sectional altcoin forward return.

---

## H5: Volatility-Adjusted Momentum — Proxy Family

All H5 proxies use 6h realized vol = std(hourly returns, last 6 bars) as the risk normalizer.

| Proxy ID | Formula | Input columns | Mechanism link |
|----------|---------|---------------|----------------|
| H5_sharpe_6h | CS_z(r_6h / max(realized_vol_6h, 1e-6)) | close col 4 | Risk-adjusted 6h momentum; normalizes for meme-coin vol |
| H5_sharpe_24h | CS_z(r_24h / max(realized_vol_24h, 1e-6)) | close col 4 | Risk-adjusted 24h momentum |
| H5_sortino_6h | CS_z(r_6h / max(downside_vol_6h, 1e-6)) | close col 4 | Downside-risk adjusted; aligns with Sortino objective |
| H5_neg_vol | CS_z(-realized_vol_6h) | close col 4 | Low-vol anomaly; selects least volatile (stable) coins |

**Note on look-ahead:** realized_vol_6h uses the current bar's data (close prices from t-6h to t-1h); it is NOT look-ahead. The 6h window excludes the current bar, which is computed from the PREVIOUS 6 hours' close prices.

**Decision gate:** Same as H1.

---

## H6: Candle Persistence — Proxy Family

All H6 proxies use OHLC data (cols 1–4), already downloaded in `load_klines_all_parallel()`.

| Proxy ID | Formula | Input columns | Mechanism link |
|----------|---------|---------------|----------------|
| H6_up_pct_6h | CS_z(count(close>open, last 6 bars) / 6) | cols 1,4 (open, close) | Fraction of last 6 bars that were up-candles |
| H6_streak_ts | CS_z(TS_z(up_pct_6h, 48h baseline)) | cols 1,4 | TS z-score of up_pct_6h vs own history, then CS normalize |
| H6_body_mean_6h | CS_z(mean(|close-open|/(high-low+ε), last 6 bars)) | cols 1,2,3,4 | Mean candle body ratio over 6h; consistent directional force |

**Decision gate:** Same as H1.

---

## Multi-Horizon Forward Returns

All proxies tested at the following forward return horizons (not just 6h as in previous tests):

| Horizon | Symbol | Rationale |
|---------|--------|-----------|
| 1h | fwd_1h | Shortest viable holding period (microstructure reversal window) |
| 2h | fwd_2h | Short-term reversal primary horizon |
| 4h | fwd_4h | Intermediate — transition between short-term and medium-term |
| 6h | fwd_6h | Current primary horizon (for comparison continuity) |
| 12h | fwd_12h | Medium-term — trend quality signals peak here |
| 24h | fwd_24h | 24h horizon — tests persistence beyond one trading session |

The IC decay profile (IC vs horizon curve) informs the optimal holding period and rebalance frequency for any promoted signal. If reversal signal peaks at 2h, `REBALANCE_HOURS` should be set to ~2h in the bot.

---

## Correlation Screening (within-family)

After IC testing, within-family duplicate filtering:
- **Within H1:** Correlations among neg_r1h, neg_r2h, neg_r6h, neg_r24h, neg_c1 — all highly correlated (same mechanism, different horizon). Keep only the horizon with best IC; others are near-duplicates.
- **Cross-family:** H1_neg_r6h and H2a_neg_rel_btc_r6h differ only by BTC subtraction. Correlation expected < 0.70 (BTC dominates some periods). Both may be tested independently.

**Correlation threshold (within-family):** ρ ≥ 0.80 on period-IC time series → eliminate lower IC Sharpe.
**Correlation threshold (cross-family):** ρ ≥ 0.90 on period-IC time series → eliminate; ρ ≥ 0.70 → flag for review.
