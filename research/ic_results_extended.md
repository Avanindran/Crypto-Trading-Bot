# Extended IC Validation — Multi-Signal, Multi-Period, Regime-Conditional

**Universe:** 67 pairs  |  **Generated:** 2026-03-17 02:21 UTC

## Test Conditions

- **A.** Current period (unconditional): Dec 2025–Feb 2026
- **B.** Trending period (unconditional): Oct 2024–Jan 2025 — BTC +61% bull run
- **C.** Current period, TREND-eligible only: BTC vol z-score ≤ 0 (51% of timestamps)

Forward return target: forward 6h return.  Significance: `*` IC>0 · `**` IC>0.03+t>1.0 · `***` IC>0.05+t>1.5

## Part 1: Cross-Sectional Signal IC (baseline)

| Signal | Test A (current) | Test B (trending) | Test C (TREND-cond.) |
|--------|-----------------|-------------------|----------------------|
| 1h ret(30m~) | IC=-0.0333 t=-1.54 hit=43% n=2129 | IC=-0.0106 t=-0.18 hit=47% n=297 | IC=-0.0244 t=-0.81 hit=44% n=1093 |
| 2h return | IC=-0.0381 t=-1.76 hit=42% n=2129 | IC=-0.0193 t=-0.33 hit=48% n=297 | IC=-0.0230 t=-0.76 hit=45% n=1093 |
| 6h return | IC=-0.0388 t=-1.79 hit=42% n=2129 | IC=-0.0301 t=-0.52 hit=47% n=297 | IC=-0.0124 t=-0.41 hit=49% n=1093 |
| 24h return | IC=-0.0589 t=-2.72 hit=38% n=2129 | IC=-0.0178 t=-0.31 hit=51% n=297 | IC=-0.0300 t=-0.99 hit=42% n=1093 |
| C1 composite | IC=-0.0657 t=-3.04 hit=36% n=2129 | IC=-0.0380 t=-0.65 hit=46% n=297 | IC=-0.0340 t=-1.12 hit=42% n=1093 |

## Part 2: Time-Series (TS) Signal IC — Candidate Formulas F1–F7

Mechanism: per-asset TS z-score removes cross-section heterogeneity.  
Final cross-sectional normalization applied as allocation step (doctrine).  
F1–F3: pure TS momentum · F4: MA deviation anchor · F5: volume flow proxy · F6: volume-confirmed TS momentum · F7: multi-horizon composite.

| Signal | Test A (current) | Test B (trending) | Test C (TREND-cond.) |
|--------|-----------------|-------------------|----------------------|
| F1: TS z_6h | IC=-0.0336 t=-1.55 hit=41% n=2129 | IC=-0.0222 t=-0.38 hit=46% n=297 | IC=-0.0261 t=-0.86 hit=44% n=1093 |
| F2: TS z_2h | IC=-0.0327 t=-1.51 hit=42% n=2129 | IC=-0.0429 t=-0.74 hit=41% n=297 | IC=-0.0265 t=-0.87 hit=43% n=1093 |
| F3: TS z_24h | IC=-0.0466 t=-2.15 hit=39% n=2129 | IC=-0.0000 t=-0.00 hit=52% n=297 | IC=-0.0235 t=-0.78 hit=44% n=1093 |
| F4: TS MA-dev | IC=-0.0484 t=-2.23 hit=38% n=2117 | IC=-0.0036 t=-0.06 hit=51% n=285 | IC=-0.0116 t=-0.38 hit=46% n=1081 |
| F5: vol ratio | IC=-0.0180 t=-0.83 hit=45% n=2119 | IC=+0.0177 t=+0.30 hit=53% n=287 * | IC=-0.0128 t=-0.42 hit=47% n=1083 |
| F6: z6h×vol | IC=-0.0346 t=-1.59 hit=41% n=2119 | IC=-0.0189 t=-0.32 hit=48% n=287 | IC=-0.0282 t=-0.93 hit=44% n=1083 |
| F7: TS compos. | IC=-0.0478 t=-2.20 hit=38% n=2117 | IC=-0.0146 t=-0.25 hit=49% n=285 | IC=-0.0337 t=-1.11 hit=43% n=1081 |

## TS Formula Selection — Decision Gate

Gate: **IC > 0 in Test B** (trending period) **AND t > 1.0**.  
Tiebreak: highest IC Sharpe (mean_IC / std_IC across period ICs).

| Formula | IC (Test B) | t-stat | IC Sharpe | Gate |
|---------|------------|--------|-----------|------|
| F1: TS z_6h | -0.0222 | -0.38 | -0.12 | FAIL |
| F2: TS z_2h | -0.0429 | -0.74 | -0.22 | FAIL |
| F3: TS z_24h | -0.0000 | -0.00 | -0.00 | FAIL |
| F4: TS MA-dev | -0.0036 | -0.06 | -0.02 | FAIL |
| F5: vol ratio | +0.0177 | +0.30 | +0.09 | FAIL |
| F6: z6h×vol | -0.0189 | -0.32 | -0.10 | FAIL |
| F7: TS compos. | -0.0146 | -0.25 | -0.07 | FAIL |

**NO TS FORMULA passes the decision gate.**  
Strategy value rests on regime-gated drawdown control (Sortino/Calmar),  
not on selection alpha. Cross-sectional approach retained as-is.

## Interpretation

**C1 composite (cross-sectional)** — Trending period: IC=-0.0380, t=-0.65

**Verdict:** Neither cross-sectional nor time-series momentum signals show statistically meaningful IC in the trending period.  
Strategy value is entirely in regime gating (Sortino) and kill switch (Calmar).  
**Recommendation:** No signal change warranted. Maintain current approach.

## Notes

- `r_30m` proxy: Binance Vision provides 1h bars; 1h return used as 30m proxy.
- F5/F6 require volume data (Binance klines col 5).
- TS signals use 48-period rolling baseline; first 3 periods return z=0 (warmup).
- Two-step construction: (1) per-asset TS z-score → (2) cross-sectional normalize.

Reference: `ic_results.md` for baseline unconditional IC, `backtest_results.md` for simulation results.
