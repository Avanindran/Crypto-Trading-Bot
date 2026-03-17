# Research Objective and Admissibility Constraints

**Written:** 2026-03-17 | **Status:** FROZEN (do not modify after signal_search.py first run)

---

## Competition Objective Function

The hackathon scoring formula is:

```
Score = 0.4 × Sortino + 0.3 × Sharpe + 0.3 × Calmar
```

Over a 10-day live trading window (Mar 21–31, $1M paper portfolio, Roostoo mock exchange).

Implications for signal selection:
- **Sortino (0.4 weight — highest):** Reward mean_return / downside_deviation. Binary regime switching (fully in cash during stress) eliminates downside deviation on those days without any signal needed. A selection signal that adds downside deviation without proportional mean return HURTS Sortino.
- **Calmar (0.3 weight):** Reward mean_return / max_drawdown. The -12% kill switch hard-caps the denominator. A selection signal that causes avoidable drawdowns HURTS Calmar.
- **Sharpe (0.3 weight):** Reward mean_return / total_deviation. A signal with rough, high-variance returns hurts Sharpe even if mean return is positive.

**Implication:** A signal is valuable ONLY if it improves the selection of long candidates in TREND regimes without adding significant volatility or drawdown. The bar is not "any positive IC" but "positive IC that survives fees and adds net risk-adjusted value."

---

## Signal Admissibility Criteria

A signal is admissible for promotion to the live bot only if ALL of the following are satisfied:

| # | Criterion | Threshold | Rationale |
|---|-----------|-----------|-----------|
| 1 | **Long-only compatible** | Signal ranks assets for LONG entry; no short-selling required | Spot-only exchange, no leverage |
| 2 | **Operationally feasible** | Signal inputs available from Roostoo ticker + Binance public APIs within 30 API calls/min budget | Hard rate limit |
| 3 | **Low turnover** | Estimated daily turnover < 5% of NAV at signal-driven rebalance frequency | Fee at 0.10%/trade; 5%/day = 0.10% fee drag (tolerable vs 2% 10-day budget) |
| 4 | **Statistically meaningful IC** | IC > 0, t > 1.0 at primary horizon in trending period (Oct 2024–Jan 2025) | Doctrine gate; IC > 0.03, t > 1.5 for promotion with confidence |
| 5 | **Explainable mechanism** | Mechanism statable in ≤ 2 sentences with clear causal chain | Screen 4 judge evaluation (30% of final score) |
| 6 | **Stable across subperiods** | IC positive in both halves of trending period | Avoids lucky-slice overfitting |
| 7 | **Robust to parameter perturbation** | IC Sharpe degrades < 50% under ±20% parameter change | Avoids threshold-specific overfitting |
| 8 | **10-day window viability** | Block-resample hit rate ≥ 55% on 10-day windows from trending period | Directly models competition window duration |

---

## What Does Not Need a Signal

The following are CONFIRMED value drivers that do NOT require selection alpha:

1. **Regime gating (H3):** HAZARD_DEFENSIVE → 0% exposure when LSI > 0.60. Eliminates downside deviation on stressed days. Sortino impact confirmed in backtest.
2. **Kill switch (H4 adjunct):** -12% portfolio drawdown → emergency exit. Hard-caps Calmar denominator.
3. **M_t maturity filter:** Blocks entries when drift already spent (extension, RSI proxy, pct_rank, funding rate). Reduces late-entry overpayment.

These three do NOT depend on IC from selection signal. Even with zero selection IC, the strategy has a positive expected Sortino contribution from regime timing.

---

## Research Objective (Precise)

Find a selection signal f(market_data_t) → ranked_altcoin_list such that:

```
E[r_{i,t+τ} | rank_i = top_k] > E[r_{i,t+τ} | rank_i = random]
```

...where τ is the optimal holding horizon, conditional on the market being in TREND_SUPPORTIVE regime, with sufficient statistical confidence (t > 1.0 in trending period) and robustness (stable across subperiods and parameter perturbations).

The null hypothesis is **equal-weight random selection** within the eligible universe in TREND regime. A signal must beat this null to justify the operational cost of computing and maintaining it.

---

## Failure Documentation Policy

If a mechanism family fails the IC gate, document:
1. What was tested (formula + data source)
2. What the IC result was (direction, magnitude, significance)
3. **Why it likely failed** (theoretical explanation, not post-hoc rationalization)
4. What limitation this reveals (proxy quality, data frequency, universe characteristics)

This documentation appears in `08_limitations_and_rejections.md` and is explicitly referenced in STRATEGY.md. Failure documentation is a research asset, not a liability.
