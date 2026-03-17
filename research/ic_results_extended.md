# Extended IC Validation — Multi-Signal, Multi-Period, Regime-Conditional
# Universe: 67 pairs (1000CHEEMSUSDT, AAVEUSDT, ADAUSDT, APTUSDT, ARBUSDT, ASTERUSDT, ...)
# Generated: 2026-03-17 01:41 UTC

## Test Conditions

  A. Current period (unconditional): Dec 2025–Feb 2026
  B. Trending period (unconditional): Oct 2024–Jan 2025  [backtest period: +21.5% pre-fee]
  C. Current period, TREND-eligible only: BTC vol z-score <= 0  [51% of timestamps]

  Forward return target: forward 6-hour return
  Significance: * = IC>0, ** = IC>0.03+t>1.0, *** = IC>0.05+t>1.5

## IC Results Table

  Signal          | Test A (current)               | Test B (trending)              | Test C (TREND-cond.)          
  ----------------+--------------------------------+--------------------------------+-------------------------------
  1h ret(30m~)  |  IC=-0.0333  t=-1.54  hit=42.8%  n=2129 |  IC=-0.0106  t=-0.18  hit=47.1%  n=297 |  IC=-0.0244  t=-0.81  hit=44.4%  n=1093
  2h return     |  IC=-0.0381  t=-1.76  hit=42.3%  n=2129 |  IC=-0.0193  t=-0.33  hit=48.1%  n=297 |  IC=-0.0230  t=-0.76  hit=45.2%  n=1093
  6h return     |  IC=-0.0388  t=-1.79  hit=42.4%  n=2129 |  IC=-0.0301  t=-0.52  hit=46.8%  n=297 |  IC=-0.0124  t=-0.41  hit=49.2%  n=1093
  24h return    |  IC=-0.0589  t=-2.72  hit=37.8%  n=2129 |  IC=-0.0178  t=-0.31  hit=50.8%  n=297 |  IC=-0.0300  t=-0.99  hit=42.2%  n=1093
  C1 composite  |  IC=-0.0657  t=-3.04  hit=36.2%  n=2129 |  IC=-0.0380  t=-0.65  hit=45.8%  n=297 |  IC=-0.0340  t=-1.12  hit=41.8%  n=1093

## Signal Quality Assessment

  1h ret(30m~) : NEGATIVE (mean-reversion)  (B IC=-0.0106, C IC=-0.0244)
  2h return    : NEGATIVE (mean-reversion)  (B IC=-0.0193, C IC=-0.0230)
  6h return    : NEGATIVE (mean-reversion)  (B IC=-0.0301, C IC=-0.0124)
  24h return   : NEGATIVE (mean-reversion)  (B IC=-0.0178, C IC=-0.0300)
  C1 composite : NEGATIVE (mean-reversion)  (B IC=-0.0380, C IC=-0.0340)

## Interpretation

  Best individual signal in trending period (Test B): 1h ret(30m~) IC=-0.0106

  C1 composite — Trending period (Test B): IC=-0.0380, t=-0.65
  C1 composite — TREND-conditional  (Test C): IC=-0.0340, t=-1.12

  VERDICT: No individual signal or composite shows meaningful IC (>0.02)
  in the trending period OR in TREND-conditional periods.
  Cross-sectional momentum does not have detectable predictive power
  in this universe across these test windows.
  RECOMMENDATION: Strategy value comes from regime-gated drawdown control
  (Sortino/Calmar), not from signal-based alpha. Narrative should focus on
  risk-adjusted return objectives, not return prediction.

## Notes

  r_30m proxy: Binance Vision provides 1h bars; 30-min return cannot be
  computed directly. 1-hour return is used as a proxy (labeled '1h ret(30m~)').
  The live bot uses 1-min snapshots and can compute r_30m precisely.

  Law of large numbers: a composite only amplifies predictive signal if
  individual components are positively correlated with the target. A composite
  of non-predictive signals remains non-predictive.

  Regime-conditionality: the strategy is designed to trade only in TREND
  regimes. IC measured unconditionally includes periods where the strategy
  would be in HAZARD_DEFENSIVE (in cash). Test C isolates the relevant subset.

  Reference: ic_results.md for baseline 3-month unconditional IC,
  backtest_results.md for simulation results.
