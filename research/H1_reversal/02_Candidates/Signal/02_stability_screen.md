# H5_voladj_momentum — Volatility-Adjusted Stability Filter (H5 Family)

**Proxy universe:** pre-committed before IC data observed (frozen)  
**Test period:** Oct 2024–Jan 2025 (trending, BTC +61% bull run)  
**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  
**Promotion gate:** IC > 0.03 AND t > 1.5  

Star `*` = |t| > 1.0. All ICs are Spearman rank correlation.

## IC Decay Profile

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |
|--------|----|----|----|----|----|-----|------|------|
| `H5_sharpe_6h` | -0.030* | -0.027* | -0.023* | -0.018* | -0.008* | -0.009* | 12h | fail |
| `H5_sharpe_24h` | -0.021* | -0.018* | -0.017* | -0.017* | -0.016* | -0.007* | 24h | fail |
| `H5_sortino_6h` | -0.026* | -0.023* | -0.020* | -0.016* | -0.007* | -0.009* | 12h | fail |
| `H5_neg_vol` | +0.035* | +0.043* | +0.049* | +0.057* | +0.070* | +0.076* | 24h | **PASS** |

## Decision Gate Summary

**Passes gate (IC>0, t>1.0):** `H5_neg_vol`
**Promotion-quality (IC>0.03, t>1.5):** `H5_neg_vol`

## Sample Sizes

| Signal | Obs (4h horizon) | Obs (6h horizon) |
|--------|-----------------|-----------------|
| `H5_sharpe_6h` | 2924 | 2922 |
| `H5_sharpe_24h` | 2924 | 2922 |
| `H5_sortino_6h` | 2924 | 2922 |
| `H5_neg_vol` | 2924 | 2922 |
