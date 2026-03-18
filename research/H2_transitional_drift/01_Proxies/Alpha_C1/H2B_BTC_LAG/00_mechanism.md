---
proxy_id: H2B_BTC_LAG
family: Alpha_C1
mechanism: H2 BTC-Diffusion (lagged BTC return predictor)
formula: r_BTC,t−1h → predict mean altcoin forward return (market-level)
status: FAILED
ic_best: Pearson r = −0.003 @ 1h (not significant)
---

# H2B_BTC_LAG — Mechanism

## Formula

```
H2B_BTC_LAG = r_BTC,t−lag   (market-level predictor, not cross-sectional)
```

Tested as Pearson correlation between lagged BTC return and mean cross-sectional altcoin forward return.

## Economic Rationale (Intended)

If BTC moves cause altcoins to follow with a lag, then the past BTC return should predict the near-future mean altcoin return. This tests the market-timing version of the H2 diffusion mechanism.

## Failure Reason

Pearson r ≈ −0.003 at 1h (not significant). Tested at lags 1h and 2h — both fail.

**Economic explanation:** Any BTC-to-altcoin diffusion that exists at sub-1h timescales (minutes to tens of minutes) is fully arbitraged within the 1h kline aggregation window. The 1h kline resolution destroys the within-bar diffusion signal. The competition's 60-second polling loop does not provide meaningful sub-hour intraday resolution to exploit this lag.

## IC Results (from `02_Candidates/Signal/01_ic_results.md`)

| Signal | 1h | 2h | 4h | 6h | 12h | 24h | Gate |
|--------|----|----|----|----|----|-----|------|
| `H2b_btc_lag1h` | −0.003 | −0.008 | −0.023 | −0.026 | −0.020 | −0.029 | fail |
| `H2b_btc_lag2h` | −0.029 | −0.038 | −0.035 | −0.024 | −0.015 | −0.033 | fail |

## Decision

**FAILED** — no predictive lag at 1h resolution. Not eligible for GP terminal set.
