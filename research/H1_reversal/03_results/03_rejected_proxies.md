# H6_streak_persistence — Candle Persistence / Streak (H6 Family — Expected to Fail)

**Proxy universe:** pre-committed before IC data observed (frozen)  
**Test period:** Oct 2024–Jan 2025 (trending, BTC +61% bull run)  
**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  
**Promotion gate:** IC > 0.03 AND t > 1.5  

Star `*` = |t| > 1.0. All ICs are Spearman rank correlation.

## IC Decay Profile

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |
|--------|----|----|----|----|----|-----|------|------|
| `H6_up_pct_6h` | -0.019* | -0.022* | -0.022* | -0.021* | -0.017* | -0.013* | 24h | fail |
| `H6_streak_ts` | -0.020* | -0.024* | -0.023* | -0.021* | -0.017* | -0.014* | 24h | fail |
| `H6_body_mean_6h` | -0.001  | -0.006* | -0.006* | -0.008* | -0.007* | -0.004* | 1h | fail |

## Decision Gate Summary

**No signals pass the IC gate** (IC>0 AND t>1.0) at any forward horizon.  

## Sample Sizes

| Signal | Obs (4h horizon) | Obs (6h horizon) |
|--------|-----------------|-----------------|
| `H6_up_pct_6h` | 2924 | 2922 |
| `H6_streak_ts` | 2924 | 2922 |
| `H6_body_mean_6h` | 2924 | 2922 |
