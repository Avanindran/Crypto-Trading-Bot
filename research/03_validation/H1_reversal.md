# H1_reversal — Short-Term Cross-Sectional Reversal

**Proxy universe:** `research/02_proxy_universe.md` (pre-committed, FROZEN)  
**Test period:** Oct 2024–Jan 2025 (trending period, BTC +61% bull run)  
**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  
**Promotion gate:** IC > 0.03 AND t > 1.5  

**Economic Basis:** De Bondt & Thaler (1985, JF) overreaction hypothesis — investors overreact to recent news, creating short-term reversal as corrective flow restores price equilibrium. In crypto, thin liquidity amplifies price overshooting; market-maker inventory rebalancing (Lehmann 1990) produces corrective flow within 1–4h. Full theory: `01_mechanism_universe.md` → H1 section.

Star `*` = |t| > 1.0. All ICs are Spearman rank correlation.

## IC Decay Profile

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Best | Gate |
|--------|----|----|----|----|----|-----|------|------|
| `H1_neg_r1h` | +0.049* | +0.041* | +0.032* | +0.026* | +0.018* | +0.012* | 1h | **PASS** |
| `H1_neg_r2h` | +0.047* | +0.043* | +0.036* | +0.032* | +0.018* | +0.014* | 1h | **PASS** |
| `H1_neg_r6h` | +0.039* | +0.040* | +0.034* | +0.027* | +0.010* | +0.018* | 2h | **PASS** |
| `H1_neg_r24h` | +0.027* | +0.027* | +0.031* | +0.032* | +0.032* | +0.024* | 12h | **PASS** |
| `H1_neg_c1` | +0.043* | +0.042* | +0.042* | +0.037* | +0.026* | +0.024* | 1h | **PASS** |

## Decision Gate Summary

**Passes gate (IC>0, t>1.0):** `H1_neg_r1h`, `H1_neg_r2h`, `H1_neg_r6h`, `H1_neg_r24h`, `H1_neg_c1`
**Promotion-quality (IC>0.03, t>1.5):** `H1_neg_r1h`, `H1_neg_r2h`, `H1_neg_r6h`, `H1_neg_r24h`, `H1_neg_c1`

## Sample Sizes

| Signal | Obs (6h horizon) |
|--------|-----------------|
| `H1_neg_r1h` | 2922 |
| `H1_neg_r2h` | 2922 |
| `H1_neg_r6h` | 2922 |
| `H1_neg_r24h` | 2922 |
| `H1_neg_c1` | 2922 |

*IC time-series chart: see `research/charts/03_validation/ic_timeseries.png`*
*Multi-horizon IC comparison: see `research/charts/03_validation/ic_multi_horizon.png`*
