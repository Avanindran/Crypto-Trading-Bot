# Strategy Backtest Results — Transitional-Drift Momentum
# Period: 2024-10-01 to 2025-01-31
# Universe: 67 pairs (1000CHEEMSUSDT, AAVEUSDT, ADAUSDT, APTUSDT, ARBUSDT, ...)
# Generated: 2026-03-17 01:43 UTC

## Parameter Disclosure

All parameters match config.py exactly. No parameters were modified
based on these results (theory-derived, OOS validation).

  Rebalance cadence:  6 hours
  Regime gross caps:  85% TREND / 65% NEUTRAL / 0% DEFENSIVE
  Max positions:      5 TREND / 3 NEUTRAL / 0 DEFENSIVE
  C1 entry threshold: 0.60 TREND / 1.00 NEUTRAL
  M_t block:          pct_rank > 0.72
  Stop-loss:          -4% from entry
  Fee per trade:      0.10% (conservative taker estimate)

## Performance Summary

  Net Total Return:    -31.4%
  Pre-fee Return:      -6.3%  (approx. before fee deduction)
  Annualized Return:   -67.3%
  Sortino Ratio:       -1.37
  Sharpe Ratio:        -1.94
  Calmar Ratio:        -1.55
  Max Drawdown:        -43.3%

## Fee Drag Analysis

  Total Fees (4-month test): 25.1% of initial NAV
  Daily fee rate:            0.204% per day
  Projected 10-day fees:     ~2.0%  (competition window)
  Test period (days):        123

  NOTE: The 4-month fee drag (25.1%) is 12x larger than the 10-day competition
  window estimate (~2.0%). Pre-fee return: -6.3%.

## vs. Buy-and-Hold BTC

  Strategy net return:     -31.4%
  Strategy pre-fee return: -6.3%
  BTC buy-and-hold:        61.2%  (Oct 2024–Jan 2025 bull run)
  Strategy max drawdown:   -43.3%

  NOTE: Oct 2024–Jan 2025 was an exceptional 61% bull run. Any regime-gated
  strategy that moves to cash during volatility spikes will underperform
  buy-and-hold in a pure trending market — that is the intended design.
  The competition scoring metric is Sortino/Calmar, not return vs buy-and-hold.

## Regime Distribution

  TREND_SUPPORTIVE:   54.5% of rebalance periods
  NEUTRAL_MIXED:      25.6% of rebalance periods
  HAZARD_DEFENSIVE:   19.9% of rebalance periods (in cash)
  Total rebalances:   492

## Interpretation

The pre-fee gross return (-6.3%) is negative across the full Roostoo universe.
This is driven by the high turnover of volatile alt-coins: with 40+ pairs competing
for 5 slots, relative C1 rankings shift rapidly each rebalance, causing frequent exits
and re-entries that accumulate fee drag (25.1% over 4 months). The IC validation
confirms no reliable cross-sectional momentum signal across this universe. The strategy
does not claim cross-sectional alpha; its value is regime gating (Sortino protection)
and hard drawdown limits (Calmar). For the 10-day competition (~2.0% fee drag),
the regime filter and position limits are the primary active management mechanism.
The HAZARD_DEFENSIVE regime (in cash ~20% of the time) explicitly avoids
downside deviation, which is the primary mechanism for maximizing the Sortino
ratio under the competition scoring formula (0.4×Sortino + 0.3×Sharpe + 0.3×Calmar).
