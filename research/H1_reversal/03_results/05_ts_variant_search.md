# H1_TS_and_H2_new — TS Overshoot Variants (H1_TS) + Non-Collapsed H2 Proxies (H2c/H2d)

**Proxy universe:** pre-committed before IC data observed (frozen)  
**Test period:** Oct 2024–Jan 2025 (trending, BTC +61% bull run)  
**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  
**Promotion gate:** IC > 0.03 AND t > 1.5  

Star `*` = |t| > 1.0. All ICs are Spearman rank correlation.

## IC Decay Profile

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |
|--------|----|----|----|----|----|-----|------|------|
| `TS_zscore_neg_r6h` | +0.027* | +0.025* | +0.017* | +0.012* | +0.008* | +0.014* | 1h | **PASS** |
| `TS_zscore_neg_r2h` | +0.036* | +0.031* | +0.024* | +0.020* | +0.011* | +0.011* | 1h | **PASS** |
| `TS_bb_dist` | +0.036* | +0.030* | +0.024* | +0.020* | +0.011* | +0.014* | 1h | **PASS** |
| `CS_TS_blend_r6h` | +0.035* | +0.034* | +0.027* | +0.020* | +0.010* | +0.017* | 1h | **PASS** |
| `H2c_beta_adj_gap` | +0.042* | +0.036* | +0.029* | +0.027* | +0.016* | +0.011* | 1h | **PASS** |
| `H2d_btcgated_h1` | +0.019* | +0.016* | +0.012* | +0.006* | +0.001  | -0.004  | 1h | **PASS** |

## Decision Gate Summary

**Passes gate (IC>0, t>1.0):** `TS_zscore_neg_r6h`, `TS_zscore_neg_r2h`, `TS_bb_dist`, `CS_TS_blend_r6h`, `H2c_beta_adj_gap`, `H2d_btcgated_h1`
**Promotion-quality (IC>0.03, t>1.5):** `TS_zscore_neg_r2h`, `TS_bb_dist`, `CS_TS_blend_r6h`, `H2c_beta_adj_gap`

## Sample Sizes

| Signal | Obs (4h horizon) | Obs (6h horizon) |
|--------|-----------------|-----------------|
| `TS_zscore_neg_r6h` | 2918 | 2916 |
| `TS_zscore_neg_r2h` | 2918 | 2916 |
| `TS_bb_dist` | 2900 | 2898 |
| `CS_TS_blend_r6h` | 2918 | 2916 |
| `H2c_beta_adj_gap` | 2914 | 2912 |
| `H2d_btcgated_h1` | 2924 | 2922 |
