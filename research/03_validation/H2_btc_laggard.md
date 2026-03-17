# H2_btc_laggard — BTC Leader-Laggard Catch-Up

**Proxy universe:** `research/02_proxy_universe.md` (pre-committed, FROZEN)  
**Test period:** Oct 2024–Jan 2025 (trending period, BTC +61% bull run)  
**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  
**Promotion gate:** IC > 0.03 AND t > 1.5  

**Economic Basis:** Kyle (1985, Econometrica) sequential information arrival — BTC, as the most liquid crypto asset, reprices market-wide information first; altcoins adjust with a 1–4h lag due to rational inattention (Grossman-Stiglitz 1980) and finite cross-pair arbitrage bandwidth. Analogue: Hou (2007) large-cap equity leadership in US markets. Full theory: `01_mechanism_universe.md` → H2 section.

Star `*` = |t| > 1.0. All ICs are Spearman rank correlation.

## IC Decay Profile

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |
|--------|----|----|----|----|----|-----|------|------|
| `H2a_neg_rel_btc_r1h` | +0.049* | +0.041* | +0.032* | +0.026* | +0.018* | +0.012* | 1h | **PASS** |
| `H2a_neg_rel_btc_r2h` | +0.047* | +0.043* | +0.036* | +0.032* | +0.018* | +0.014* | 1h | **PASS** |
| `H2a_neg_rel_btc_r6h` | +0.039* | +0.040* | +0.034* | +0.027* | +0.010* | +0.018* | 2h | **PASS** |

## H2b: Lagged BTC Predictor — Pearson Correlation

These are market-level signals (same value for all pairs at each timestamp).  
Cannot use cross-sectional Spearman IC. Tested as time-series Pearson r:  
does btc_lag_ret correlate with mean cross-sectional altcoin forward return?  
Gate: Pearson r > 0.05 AND t > 1.0.

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |
|--------|----|----|----|----|----|-----|------|------|
| `H2b_btc_lag1h` | -0.003  | -0.008  | -0.023* | -0.026* | -0.020* | -0.029* | 1h | fail |
| `H2b_btc_lag2h` | -0.029* | -0.038* | -0.035* | -0.024* | -0.015  | -0.033* | 12h | fail |

## Decision Gate Summary

**Passes gate (IC>0, t>1.0):** `H2a_neg_rel_btc_r1h`, `H2a_neg_rel_btc_r2h`, `H2a_neg_rel_btc_r6h`
**Promotion-quality (IC>0.03, t>1.5):** `H2a_neg_rel_btc_r1h`, `H2a_neg_rel_btc_r2h`, `H2a_neg_rel_btc_r6h`

## Sample Sizes

| Signal | Obs (6h horizon) |
|--------|-----------------|
| `H2a_neg_rel_btc_r1h` | 2922 |
| `H2a_neg_rel_btc_r2h` | 2922 |
| `H2a_neg_rel_btc_r6h` | 2922 |
