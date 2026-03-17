# H1+H5 GP Search Results

**Run:** 2026-03-17 10:43 UTC  
**Search space:** `04_gp_search/H1_H5_gp.md` (pre-committed FROZEN)  
**Inner train:** Oct–Nov 2024  |  **Holdout:** Dec 2024–Jan 2025  
**Optimizing:** IC Sharpe at 4h forward return  

Star `*` = |t| > 1.5.

## Individual Terminals — Train vs Holdout IC

| Signal | Train_4h | Holdout_4h | T1h | T2h | T6h | T12h | T24h |
|--------|---------|---------||------||------||------||------||------|
| `H1_neg_r1h` | +0.028* | +0.035* | +0.048* | +0.041* | +0.026* | +0.019* | +0.010  |
| `H1_neg_r2h` | +0.034* | +0.038* | +0.047* | +0.047* | +0.034* | +0.018* | +0.010  |
| `H1_neg_c1` | +0.039* | +0.046* | +0.040* | +0.040* | +0.037* | +0.024* | +0.029* |
| `H5_neg_vol` | +0.029* | +0.068* | +0.023* | +0.025* | +0.035* | +0.044* | +0.049* |
| `TS_ZSCORE_NEG_R6H` | +0.014* | +0.019* | +0.023* | +0.023* | +0.009* | +0.009* | +0.013* |
| `CS_TS_BLEND_R6H` | +0.027* | +0.027* | +0.034* | +0.036* | +0.020* | +0.010* | +0.017* |

## Top Combinations by IC Sharpe at {OPT_HORIZON}h (inner train)

| Formula | w | Train IC | Train IC-Sharpe | Holdout IC | Holdout t |
|---------|---|----------|----------------|-----------|---------|
| 0.7×H1_neg_c1 + 0.3×H5_neg_vol | 0.7 | +0.047* | +0.190 | +0.066 | +10.59 |
| 0.6×H1_neg_c1 + 0.4×H5_neg_vol | 0.6 | +0.048* | +0.187 | +0.073 | +11.57 |
| 0.8×H1_neg_c1 + 0.2×H5_neg_vol | 0.8 | +0.045* | +0.181 | +0.059 | +9.29 |
| 0.5×H1_neg_c1 + 0.5×H5_neg_vol | 0.5 | +0.047* | +0.173 | +0.077 | +11.95 |
| 0.9×H1_neg_c1 + 0.1×H5_neg_vol | 0.9 | +0.042* | +0.167 | +0.051 | +8.04 |
| 0.5×H1_neg_r2h + 0.5×H1_neg_c1 | 0.5 | +0.040* | +0.165 | +0.046 | +7.09 |
| 0.6×H1_neg_r2h + 0.4×H1_neg_c1 | 0.6 | +0.040* | +0.164 | +0.045 | +6.96 |
| 0.7×H1_neg_r2h + 0.3×H5_neg_vol | 0.7 | +0.041* | +0.162 | +0.058 | +9.16 |
| 0.4×H1_neg_r2h + 0.6×H1_neg_c1 | 0.4 | +0.040* | +0.162 | +0.047 | +7.26 |
| 0.6×H1_neg_r2h + 0.4×H5_neg_vol | 0.6 | +0.042* | +0.162 | +0.065 | +10.26 |
| 0.3×H1_neg_r2h + 0.7×H1_neg_c1 | 0.3 | +0.040* | +0.162 | +0.048 | +7.38 |
| 0.7×H1_neg_r2h + 0.3×H1_neg_c1 | 0.7 | +0.039* | +0.160 | +0.043 | +6.67 |
| 0.7×CS_TS_BLEND_R6H + 0.3×H5_neg_vol | 0.7 | +0.037* | +0.159 | +0.049 | +8.07 |
| 0.8×H1_neg_r2h + 0.2×H5_neg_vol | 0.8 | +0.039* | +0.159 | +0.051 | +7.99 |
| 0.2×H1_neg_r2h + 0.8×H1_neg_c1 | 0.2 | +0.040* | +0.159 | +0.048 | +7.39 |
| 0.6×CS_TS_BLEND_R6H + 0.4×H5_neg_vol | 0.6 | +0.039* | +0.159 | +0.059 | +9.31 |
| 0.2×H1_neg_r1h + 0.8×H1_neg_c1 | 0.2 | +0.040* | +0.159 | +0.048 | +7.51 |
| 0.3×H1_neg_r1h + 0.7×H1_neg_c1 | 0.3 | +0.039* | +0.158 | +0.049 | +7.67 |
| 0.5×H1_neg_r2h + 0.5×H5_neg_vol | 0.5 | +0.043* | +0.158 | +0.072 | +10.98 |
| 0.1×H1_neg_r1h + 0.9×H1_neg_c1 | 0.1 | +0.040* | +0.158 | +0.047 | +7.30 |

## Selected Formula

**Best by IC Sharpe on inner train (4h):** `H1_neg_c1_x07_H5_neg_vol`  
- Train IC at 4h: +0.0474 (IC-Sharpe: +0.190, t=+7.22)  
- Holdout IC at 4h: +0.0660 (t=+10.59)

**Holdout gate (IC>0, t>1.0):** PASS

## Promotion Decision

**PROMOTED:** `H1_neg_c1_x07_H5_neg_vol`  
Formula: `CS_z(0.7 × (H1_neg_c1) + 0.3 × (H5_neg_vol))`  
Economic description: 70% short-term reversal (H1_neg_c1) + 30% low-volatility stability (H5_neg_vol)  

See `09_robustness/` for block-resampling and parameter perturbation tests.
