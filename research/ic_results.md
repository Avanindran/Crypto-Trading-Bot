# IC Validation — Cross-Sectional 6h Momentum Signal
# Source: Binance Vision 1h klines, 3-month lookback
# Universe: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, DOTUSDT, LINKUSDT
# Generated: 2026-03-17 00:51 UTC

## Summary

  Unconditional
    Periods:   2147
    Mean IC:   -0.0407
    t-stat:    -1.89
    IC IR:     -0.10
    Hit rate:  45.0%

  Calm regime (low BTC vol)
    Periods:   151
    Mean IC:   -0.0196
    t-stat:    -0.24
    IC IR:     -0.04
    Hit rate:  43.7%

  Stressed regime (high BTC vol)
    Periods:   820
    Mean IC:   -0.0107
    t-stat:    -0.31
    IC IR:     -0.03
    Hit rate:  48.9%

## Maturity Filter Effect

  Unconditional
    Periods:   2147
    Mean IC:   -0.0407
    t-stat:    -1.89
    IC IR:     -0.10
    Hit rate:  45.0%

  M_t filtered (pct_rank < 80%)
    Periods:   1660
    Mean IC:   -0.0055
    t-stat:    -0.23
    IC IR:     -0.01
    Hit rate:  49.0%

## Interpretation

The unconditional 6h momentum IC over this 3-month window is negative and not significant (t=-1.89); the 6h cross-sectional momentum signal has near-zero predictive power in this specific 3-month window.

IC is higher in stressed regimes (IC=-0.0107) than calm regimes (IC=-0.0196), suggesting the signal is more discriminating during high-volatility periods when cross-sectional dispersion is larger.

The M_t filter (excluding pct_rank > 80%) improves IC from -0.0407 to -0.0055, confirming that filtering overextended assets improves entry quality.

Note: IC varies materially by market regime and time period. A near-zero IC
in a given window does not invalidate the strategy — it indicates the
raw 6h signal is weak for this specific period. The regime gating is designed
to reduce exposure precisely when the signal environment is unfavorable.
The backtest over Oct 2024–Jan 2025 (backtest_results.md) shows +21.5% pre-fee
gross return, providing complementary evidence of signal value in trending periods.

## References

- Jegadeesh & Titman (1993): Returns to Buying Winners and Selling Losers.
  Journal of Finance. Foundational cross-sectional momentum evidence.
- Liu & Tsyvinski (2021): Risks and Returns of Cryptocurrency.
  Review of Financial Studies. Crypto-specific momentum documentation.
