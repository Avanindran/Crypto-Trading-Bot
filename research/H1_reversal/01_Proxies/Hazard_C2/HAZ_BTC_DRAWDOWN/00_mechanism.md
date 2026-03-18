---
proxy_id: HAZ_BTC_DRAWDOWN
family: Hazard_C2
formula: BTC drawdown from 24h rolling high > 2% → block entries
status: REJECTED
ic_best: N/A
---

# HAZ_BTC_DRAWDOWN — Mechanism

## Formula

BTC percentage drawdown from its 24-hour rolling high price > 2% → block new entries

```
btc_high_24h = max(btc_prices[-1440:])   # 24h rolling high (minute resolution)
btc_drawdown = (btc_price − btc_high_24h) / btc_high_24h
block_entry if btc_drawdown < −0.02
```

## Economic Rationale

A BTC drawdown of more than 2% from its intraday high suggests that buying pressure
has been exhausted and a distribution phase may be underway. For secondary crypto assets,
this often precedes a correlated sell-off as market participants de-risk. In theory,
blocking entries during BTC drawdown avoids catching falling knives. In practice,
the 2% threshold is too sensitive: BTC frequently retraces 2–3% intraday within normal
trending conditions, and these drawdowns are often followed by continuation or rapid
recovery. The proxy fires too frequently (in benign conditions) and not specifically
enough (missing the larger drawdowns that actually damage NAV).

## Signal Family

C2 Hazard — BTC trend continuation / drawdown gate

## Decision

**Status:** REJECTED — MaxDD change −6.4%; drawdown threshold is too low and fires
during normal intraday noise, blocking profitable reversal entries in healthy regimes
without adequately protecting against the deeper drawdowns that matter for Calmar.
