# H6_streak_persistence — Candle Persistence (Streak Consistency)

**Proxy universe:** `research/02_proxy_universe.md` (pre-committed, FROZEN)  
**Test period:** Oct 2024–Jan 2025 (trending period, BTC +61% bull run)  
**Decision gate:** IC > 0 AND t > 1.0 at any forward horizon  
**Promotion gate:** IC > 0.03 AND t > 1.5  

**Economic Basis (and redundancy):** H6 is designed to capture participation breadth distinct from cumulative return. However, for small per-bar returns, `H6_up_pct_6h ≈ sign(r_6h)` — cross-sectional z-normalization collapses H6 to the same ranking as H1's primary input. H6 discards per-bar magnitude, which is precisely the information reversal exploits. The near-zero IC confirms this structural redundancy; this is not a false negative. Full proof: `01_mechanism_universe.md` → H6 section.

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

| Signal | Obs (6h horizon) |
|--------|-----------------|
| `H6_up_pct_6h` | 2922 |
| `H6_streak_ts` | 2922 |
| `H6_body_mean_6h` | 2922 |
