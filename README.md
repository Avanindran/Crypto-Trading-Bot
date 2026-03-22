# Crypto Momentum Bot — Team178-Hamburglers (NUS)

**SG vs HK Quant Trading Hackathon 2026**

---

## Strategy

**Thesis:** Exploit incomplete cross-asset expectation diffusion in crypto spot markets. Two economic mechanisms are deployed in parallel, combined via continuous regime-adaptive allocation:

| Engine | Archetype | Mechanism |
|--------|-----------|-----------|
| **H1 Reversal** | Mean-reversion | Laggard assets recover within 1–4h as liquidity restores; buy cross-sectional underperformers with low realized vol |
| **H2C BTC-Diffusion** | Momentum | BTC reprices first on macro information; altcoins lag due to rational inattention; buy assets that haven't yet tracked BTC's move |

**Scoring formula:**

```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
```

| Component | Role | Description | Module |
|-----------|------|-------------|--------|
| `C1_i` | Alpha signal | 0.70 × CS_z(−momentum) + 0.30 × CS_z(−vol): laggards with low realized vol | `bot/strategy/signals.py` |
| `λ_t` | Market hazard rate | LSI/MPI/FEI regime engine; high λ collapses all scores exponentially | `bot/strategy/regime.py` |
| `1 − M_t_i` | Drift capacity (C3) | Fraction of expected move still unrealized; blocks entry if move is spent | `bot/strategy/maturity.py` |

**H2C continuous allocation** (failure-mode-derived formula):

```
f_t = f_max × min(1, |r_BTC,2h| / 0.003) × max(0, 1 − vol_z / 2.0)
```

- `btc_activity = 0` when BTC is flat → H2C signal undefined; ramps to 1 at 0.3% move
- `stress_decay = 0` when `vol_z ≥ 2σ` → correlations spike, lag-signal degrades
- `f_max = 0.50`, mean active fraction ≈ 36.8%

---

## Key Terms

| Term | Definition |
|------|-----------|
| **C1** | Alpha signal — cross-sectional reversal (70%) + low-vol filter (30%); higher C1 = bigger laggard with lower realized vol |
| **M_t (C3)** | Drift maturity — fraction of expected recovery already realized; entry blocked when M_t > 0.72 |
| **λ_t** | Hazard rate — regime engine output; all position scores scale as exp(−λ_t), so λ=4 → 2% effective allocation |
| **CS_z(x)** | Cross-sectional z-score: `(x_i − mean) / std` across all pairs at each timestamp (not asset's own history) |
| **LSI** | Liquidity Stress Index — BTC realized vol + bid-ask spread + cross-section dispersion collapse + Fear & Greed; 0=calm, 1=panic |
| **MPI** | Market Posture Index — BTC trend strength (directional move / typical vol); 0=choppy, 1=strong trend |
| **FEI** | Flow Elasticity Index — top-quartile minus bottom-quartile 6h return spread; 0=homogeneous moves, 1=clear leaders |
| **IC** | Information Coefficient — Pearson correlation between predicted rank and actual 4h forward returns; IC > 0.03 with t > 1.5 is the promotion gate |
| **OOS** | Out-of-sample — Dec 2024–Jan 2025 holdout period; all parameters frozen before this window was examined |
| **Sortino** | Return / downside volatility (only negative returns penalized) — primary competition metric |
| **Calmar** | Annualized return / max drawdown — measures capital efficiency |
| **IC-Sharpe** | `mean(IC) / std(IC) × √n` — measures signal consistency across time (high mean IC + low variance) |

---

## Validated Performance

Backtest period: Oct 2024 – Nov 2024 (train) | Dec 2024 – Jan 2025 (OOS holdout)
Data: Binance 1h OHLCV, 44 pairs, 0.05% maker fee

| Engine | Sortino | Calmar | MaxDD | OOS Return | OOS Sortino |
|--------|---------|--------|-------|------------|-------------|
| H1 only | 2.69 | 11.73 | −13.6% | +8.2% | 1.33 |
| H2C only | 1.99 | 20.25 | −20.6% | +0.1% | 0.25 |
| **Combined (f_max=0.50)** | **3.30** | **19.22** | **−13.7%** | **+9.3%** | **1.40** |

Signal IC @ 4h: +0.047 (t=7.2) train · +0.066 (t=10.6) OOS holdout
Block-resample: 97.2% of 500 random 10-day windows show positive IC

Full research pipeline: [`research/README.md`](research/README.md)
Combined backtest details: [`research/portfolio/05_dual_portfolio_backtest.md`](research/portfolio/05_dual_portfolio_backtest.md)

---

## Architecture

```
main.py              # 60-second event loop — ticker → features → regime → signals → execution
config.py            # All parameters (60+ constants, each traced to a research finding)
state.py             # JSON state persistence (crash recovery across restarts)

bot/
  data/
    roostoo_client.py      # HMAC-SHA256 signed client (7 endpoints, 3-retry backoff)
    market_cache.py        # Rolling 300-snapshot price history per asset
    feature_builder.py     # Computes r_30m, r_2h, r_6h, r_24h, realized vol, spread, M_t inputs
    funding_rate_client.py # Binance perp funding rates — crowding proxy for M_t (free, no auth)
    fear_greed_client.py   # Crypto Fear & Greed Index — LSI leading indicator (free, no auth)

  strategy/
    regime.py              # RegimeEngine: LSI/MPI/FEI → (RegimeState, λ_t)
    signals.py             # C1 signal: 0.70×laggard z-score + 0.30×low-vol z-score
    maturity.py            # M_t composite: extension/RSI_proxy/pct_rank/funding_rate
    ranking.py             # PositionScore = C1×exp(−λ)×C3; entry/exit filter gates
    h2_signals.py          # H2C engine: BTC-adjusted gap signal, rolling OLS beta
    engine_aggregator.py   # Blends H1 and H2C weights: w = (1−f)×H1_w + f×H2C_w

  portfolio/
    allocator.py           # Score-proportional weights, regime gross caps, drawdown overrides

  execution/
    order_manager.py       # Limit orders at bid+20%×spread; timeout cancellation
    reconcile.py           # Startup: cancel stale orders, verify balance, pre-flight checks

  risk/
    drawdown.py            # NAV tracking, 3-tier drawdown response (−5% / −8% / −12%)
    kill_switch.py         # Emergency exit, BTC direct gates (−3% / −6%), per-position stops
    constraints.py         # Min hold 4h, re-entry lockout 2h, max hold 72h

  infra/
    logger.py              # Structured logs: trades.csv (Screen 1 audit), state.jsonl, errors.log
    retry.py               # @with_retry decorator: 3 attempts, exponential backoff

tests/
  test_features.py          # 19 tests — feature computation (returns, vol, RSI proxy, pct_rank)
  test_precision.py         # 10 tests — order precision, minimum notional compliance
  test_scoring.py           # 22 tests — C1/M_t/PositionScore formula + regime cascade
  test_h2_signals.py        # 13 tests — H2C beta history, score computation
  test_engine_aggregator.py #  6 tests — H1+H2C blending logic
  test_risk.py              # 13 tests — drawdown tracker levels, kill switch (hard stop, trailing stop)

docs/
  STRATEGY.md               # Full strategy writeup: mechanisms, formulas, IC validation, risk
  ARCHITECTURE.md           # Module dependency diagram, data-flow, API rate budget

research/
  README.md                 # Judge's guide to the research pipeline
  10_pipeline_index.md      # Master index: every doctrine step → file → verdict
  (see research/README.md for full structure)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full module dependency diagram and per-loop data flow.

---

## Risk Management

| Layer | Trigger | Action |
|-------|---------|--------|
| LSI (Liquidity Stress Index) > 0.80 | BTC vol spike + spread + panic | λ=10.0, ~0% exposure |
| LSI > 0.60 (defensive) | Elevated stress | λ=4.0 → exp(−4)≈2% effective allocation |
| LSI > 0.40 or MPI (Market Posture Index) < 0.30 | Caution / chop | λ=1.5 |
| Portfolio DD −12% | Kill switch | Emergency exit all, block until −8% recovery |
| Portfolio DD −8% | Defensive | Max 30% gross cap, recovery gate active |
| Portfolio DD −5% | Caution | 50% gross cap override |
| BTC −6% (2h return) | BTC gate | Emergency exit all positions |
| BTC −3% (2h return) | BTC gate | Block all new entries |
| Position −3% from entry | Hard stop | Market order exit |
| Position +3%, then −2.5% | Trailing stop | Market order exit |
| H2C position held 6h | H2C hold cap | Market order exit — diffusion window expired |
| H2C + BTC −1% (2h) | H2C BTC reversal | Market order exit — diffusion direction invalidated |

---

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env: set ROOSTOO_API_KEY and ROOSTOO_API_SECRET

# Run locally
python main.py
```

**AWS EC2 (production deployment):**

```bash
# Start in persistent background session
tmux new-session -d -s bot 'python main.py'

# Attach / detach
tmux attach -t bot      # attach
# Ctrl-B D              # detach (bot keeps running)

# Monitor
tail -f logs/state.jsonl   # strategy state per loop
tail -f logs/trades.csv    # order audit trail
tail -f logs/errors.log    # warnings and errors
```

---

## Tests

Run before every restart during live trading:

```bash
python -X utf8 tests/test_features.py
python -X utf8 tests/test_precision.py
python -X utf8 tests/test_scoring.py
python -X utf8 tests/test_h2_signals.py
python -X utf8 tests/test_engine_aggregator.py
python -X utf8 tests/test_risk.py
```

All 83 tests pass. Tests cover: signal formulas, order precision, regime cascade, H2C engine, and portfolio aggregation logic.

---

## Research

Strategy development follows a pre-committed doctrine: mechanisms are declared before data is seen, proxies are tested independently with IC validation, and every decision has an explicit pass/fail record.

**Start here for judges:** [`research/README.md`](research/README.md)

Key decision documents:

| Document | Content |
|----------|---------|
| [`research/10_pipeline_index.md`](research/10_pipeline_index.md) | Master index: every doctrine step → file → verdict |
| [`research/H1_reversal/04_decision.md`](research/H1_reversal/04_decision.md) | H1 promotion record (IC=+0.057, t=12.7) |
| [`research/H2_transitional_drift/04_decision.md`](research/H2_transitional_drift/04_decision.md) | H2C promotion record (IC=+0.042, t=9.85) |
| [`research/portfolio/05_dual_portfolio_backtest.md`](research/portfolio/05_dual_portfolio_backtest.md) | Section [G]: combined backtest — all gates passed |
| [`docs/STRATEGY.md`](docs/STRATEGY.md) | Full strategy writeup (mechanisms, formulas, risk rationale) |

---

## Logs (Screen 1 Compliance)

| File | Content |
|------|---------|
| `logs/trades.csv` | Every order: timestamp, pair, side, qty, price, fill, fee |
| `logs/state.jsonl` | Per-loop snapshot: regime, λ_t, C1 scores, positions, drawdown, h2c_capital_fraction |
| `logs/errors.log` | Warnings, API errors, retry events |

---

## Competition Notes

- **Round 1:** Mar 21 8pm HKT → Mar 31 (bot runs autonomously, no manual intervention)
- **Every parameter change** during live trading is committed to git before the bot restarts
- **State persists** across restarts — bot resumes where it left off within a 2h window
- **Screen 1 compliance:** `logs/trades.csv` provides complete autonomous trade record
