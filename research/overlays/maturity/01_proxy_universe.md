# Maturity Overlay — Component Proxy Specs

**Status:** PARTIALLY DEPLOYED (pct_rank proxy rejected; composite retained)
**Written:** 2026-03-17
**Mechanism reference:** [00_mechanism.md](00_mechanism.md)

---

## M_t Components

### SMA Extension (weight: 0.40)

```
sma_12h_i           = mean(close_i, last 12 hourly bars)
extension_i         = (close_i − sma_12h_i) / (sma_12h_i + ε)
M_sma_i             = clip(extension_i / EXTENSION_MAX, 0, 1)
```

**Rationale:** If price has already extended significantly above its 12h moving average, the mean-reversion that H1 predicts may already be partially complete. A laggard that has recovered 5% above its 12h SMA is less likely to recover another 5% than a laggard still trading at its SMA.

**Weight rationale:** 0.40 — the single most informative component. Price extension is a direct observable measure of where the asset stands in its recovery trajectory.

### RSI Proxy (weight: 0.15)

```
# RSI-like overbought proxy using recent return momentum
up_periods   = sum of positive hourly returns in last 14 periods
down_periods = sum of negative hourly returns in last 14 periods (absolute)
RS           = up_periods / (down_periods + ε)
RSI_proxy_i  = RS / (1 + RS)    # maps to [0, 1]
M_rsi_i      = clip(RSI_proxy_i, 0, 1)
```

**Rationale:** The RSI proxy identifies sustained buying pressure over the last 14 hours. High RSI-proxy signals that recent buyers have been consistently present — suggesting the correction is mature and fewer new buyers remain.

**Weight rationale:** 0.15 — secondary signal. RSI works best in range-bound markets; in trending conditions it may remain high for extended periods without predicting exhaustion.

### Percentile Rank (weight: 0.25)

```
r_6h_history_i      = rolling list of r_6h values for asset i, last 48 periods
pct_rank_i          = percentile of current r_6h in r_6h_history_i
M_pctrank_i         = clip(pct_rank_i, 0, 1)    # 0 = low return (early recovery), 1 = high return (mature)
```

**Rationale:** If the current 6h return is in the top percentile of recent history, the asset has already experienced a large positive move relative to its own norms — suggesting diminishing mean-reversion potential.

**Validation status:** **REJECTED as standalone proxy.**
- IC(fresh, pct_rank < 30%) = +0.018 < IC(unconditional) = +0.048
- In the trending period, pct_rank mislabels momentum continuation as "mature recovery"
- Retained in composite at 0.25 weight (reduced from a higher standalone consideration) as it may provide signal in non-trending regimes not tested in the research period

### Funding Rate (weight: 0.20)

```
funding_rate_i      = Binance perpetual funding rate for symbol_i (refreshed every 10 loops)
M_funding_i         = clip((funding_rate_i − FUNDING_NEUTRAL) / FUNDING_SCALE, 0, 1)
    where FUNDING_NEUTRAL = 0.0001  (0.01%/8h, approximate equilibrium)
          FUNDING_SCALE   = 0.0008  (1.0 at 0.09%/8h, high positive funding)
```

**Source:** Binance fapi `/v1/premiumIndex` (free, no auth).

**Rationale:** Positive funding rate means long perpetual holders pay shorts. High positive funding indicates crowded long positioning — the market has already accumulated the position that H1's recovery would create. Entering at high funding means competing with existing longs for the same upside.

**Weight rationale:** 0.20 — the most novel and externally sourced component. Funding rate is a real-time market signal that captures positioning information not available from price history alone.

---

## M_t Composite

```
M_t_i = 0.40 × M_sma_i + 0.15 × M_rsi_i + 0.25 × M_pctrank_i + 0.20 × M_funding_i
```

**Entry gate:**
```
if M_t_i > MAX_MATURITY_FOR_ENTRY (0.72):
    asset i excluded from entry candidates
```

---

## Configuration Reference

```python
MT_WEIGHT_EXTENSION   = 0.40
MT_WEIGHT_RSI_PROXY   = 0.15
MT_WEIGHT_PCT_RANK    = 0.25
MT_WEIGHT_FUNDING     = 0.20
FUNDING_RATE_NEUTRAL  = 0.0001
FUNDING_RATE_SCALE    = 0.0008
FUNDING_RATE_REFRESH_LOOPS = 10
MT_LOOKBACK_PERIODS   = 48
MAX_MATURITY_FOR_ENTRY = 0.72
```
