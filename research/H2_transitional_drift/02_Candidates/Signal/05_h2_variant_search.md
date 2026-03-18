# H2_C1_variants — H2C BTC-Diffusion C1 Variants (H2E: 1h horizon, H2F: 4h horizon, H2G: direction-conditional)

**Proxy universe:** pre-committed before IC data observed (frozen)  
**Test period:** Oct 2024–Jan 2025 (trending, BTC +61% bull run)  
**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  
**Promotion gate:** IC > 0.03 AND t > 1.5  

Star `*` = |t| > 1.0. All ICs are Spearman rank correlation.

## IC Decay Profile

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |
|--------|----|----|----|----|----|-----|------|------|
| `H2e_horizon_1h` | +0.041* | +0.037* | +0.025* | +0.022* | +0.014* | +0.008* | 1h | **PASS** |
| `H2f_horizon_4h` | +0.034* | +0.029* | +0.025* | +0.024* | +0.010* | +0.011* | 1h | **PASS** |
| `H2g_direction_cond` | +0.020* | +0.016* | +0.012* | +0.011* | +0.001  | -0.001  | 1h | **PASS** |

## Decision Gate Summary

**Passes gate (IC>0, t>1.0):** `H2e_horizon_1h`, `H2f_horizon_4h`, `H2g_direction_cond`
**Promotion-quality (IC>0.03, t>1.5):** `H2e_horizon_1h`, `H2f_horizon_4h`

## Sample Sizes

| Signal | Obs (4h horizon) | Obs (6h horizon) |
|--------|-----------------|-----------------|
| `H2e_horizon_1h` | 2914 | 2912 |
| `H2f_horizon_4h` | 2914 | 2912 |
| `H2g_direction_cond` | 2914 | 2912 |
