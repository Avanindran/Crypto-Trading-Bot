# Crypto Momentum Trading Bot — Team178-Hamburglers

**SG vs HK Quant Trading Hackathon 2026**

## 1. Project Overview

**Strategy:** Transitional-drift Momentum with Regime-Adaptive Hazard Gating

**Thesis:** Exploit incomplete cross-asset expectation diffusion in crypto spot markets. When a market-moving event occurs, leader assets reprice first. Secondary assets update more slowly — this lag creates a temporary continuation/drift window that can be harvested systematically.

**Key features:**
- Theory-grounded C1/M_t/PositionScore framework (transparent formula, no black-box ML)
- Crypto-adapted Regime State Vector (LSI/MPI/FEI) derived from ticker data only
- Exponential hazard gating targeting Sortino ratio maximization
- Quarter-Kelly position sizing with downside-volatility denominator
- Hard drawdown kill switch at -12% for Calmar protection
- Full state persistence and crash recovery

## 2. Architecture

```
main.py                     # Entry point + main event loop
config.py                   # All parameters, thresholds, weights
state.py                    # JSON state persistence (crash recovery)

bot/
  data/
    roostoo_client.py       # HMAC-signed API client (all 7 endpoints)
    market_cache.py         # Rolling ticker snapshot store (300 × all pairs)
    feature_builder.py      # r_30m, r_2h, r_6h, r_24h, vol, spread, M_t inputs

  strategy/
    regime.py               # Regime State Vector: LSI/MPI/FEI → (RegimeState, λ_t)
    signals.py              # C1: cross-sectional z-score of asset momentum
    maturity.py             # M_t: diffusion maturity [0,1] → C3 = 1 − M_t
    ranking.py              # PositionScore = C1 × exp(−λ_t) × C3

  portfolio/
    sizing.py               # Quarter-Kelly weights (Sortino-targeted)
    allocator.py            # Score-weighted + regime gross cap allocation

  execution/
    order_manager.py        # Limit orders, timeout cancellation, emergency exit
    reconcile.py            # Startup reconciliation + pre-flight checks

  risk/
    drawdown.py             # Portfolio NAV tracking, 3-level drawdown response
    kill_switch.py          # Portfolio kill switch + BTC direct gates + per-position stops
    constraints.py          # Min hold period, re-entry lockout, max hold time

  infra/
    logger.py               # Structured logs: trades.csv, state.jsonl, errors.log
    retry.py                # Exponential backoff retry decorator

tests/
  test_features.py          # Feature computation correctness
  test_precision.py         # Order precision and validation
  test_scoring.py           # C1/M_t/PositionScore formula verification

docs/
  STRATEGY.md               # Full strategy explanation
  ARCHITECTURE.md           # Module dependency diagram

research/
  backtest_simulation.py    # Full strategy simulation on Binance 1h data (Oct 2024–Jan 2025)
  ic_validation_extended.py # Per-signal IC test: 3 periods × 5 signals (cross-sectional momentum)
  ic_validation.py          # Baseline Spearman IC against forward 6h return
  generate_charts.py        # Equity curve, drawdown, and IC visualizations
  backtest_results.md       # Simulation results with fee-drag analysis
  ic_results_extended.md    # Full IC table: current, trending, regime-conditional
  charts/                   # PNG outputs: equity_curve, drawdown, ic_multi_horizon
```

**Tech stack:** Python 3.11+, requests, python-dotenv

**Supplementary data sources (public APIs, no authentication required):**
- Crypto Fear & Greed Index: alternative.me — refreshed daily; 0.15 weight in LSI stress calculation
- Binance perpetual funding rates: binance.com futures API — refreshed every 10 min; 0.20 weight in M_t maturity calculation

## 3. Strategy Explanation

See [docs/STRATEGY.md](docs/STRATEGY.md) for the full write-up.

**Scoring formula:**
```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
```

| Component | Role | Description |
|-----------|------|-------------|
| `C1_i` | Alpha signal | Cross-sectional z-score of weighted momentum (30m/2h/6h/24h + relative strength) |
| `λ_t` | Hazard rate | Market stress from Regime Engine (LSI/MPI/FEI); high λ collapses all scores exponentially |
| `M_t_i` | Diffusion maturity | Fraction of expected drift already reflected in price; `1−M_t` = remaining drift capacity (C3) |

**Entry conditions:**
- C1 z-score exceeds regime-specific threshold (0.60 in trend, 1.00 in neutral)
- M_t < 0.72 (drift not yet spent)
- PositionScore > 0 (long only)
- Not in re-entry lockout (2h after exit)
- Regime is not HAZARD_DEFENSIVE

**Exit conditions:**
- C1 z-score falls below 0.20 (signal decayed)
- Hard stop-loss: -4% from entry (market order)
- Trailing stop: activates at +3% gain, trails at 2.5%
- Max hold time: 72 hours

**Risk management:**
- Portfolio drawdown levels: -5% (caution), -8% (defensive), -12% (kill switch)
- BTC direct gate: -3% 2h return blocks entries; -6% triggers emergency exit
- Min holding period: 4h (prevents fee-drag churn)

**Position sizing:**
- Quarter-Kelly: `0.25 × (expected_return / downside_vol²)`
- Per-asset cap: max 30% NAV
- Regime gross cap: 85% (trend), 65% (neutral), 0% (defensive)

## 4. Setup and Running

### Prerequisites

```bash
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your API keys
```

### Run locally

```bash
python main.py
```

### Deploy on AWS EC2 (production)

```bash
# Start in persistent tmux session
tmux new-session -d -s bot 'python main.py'

# Reattach to session
tmux attach -t bot

# View logs
tail -f logs/state.jsonl
tail -f logs/trades.csv
tail -f logs/errors.log
```

### Run tests

```bash
python tests/test_features.py
python tests/test_precision.py
python tests/test_scoring.py
```

## 5. Logging

| File | Content | Purpose |
|------|---------|---------|
| `logs/trades.csv` | Every order event (timestamp, pair, side, qty, price, fill, fee) | Trade audit / Screen 1 compliance |
| `logs/state.jsonl` | Per-loop strategy state (regime, scores, drawdown, positions) | Strategy debugging |
| `logs/errors.log` | Warnings and errors | Operational monitoring |

## 6. Competition Notes

- **Round 1 keys:** Set `ROOSTOO_API_KEY` and `ROOSTOO_API_SECRET` in `.env` before Mar 21 8pm HKT
- **Bot runs autonomously** — no manual intervention after start
- **Every parameter change** during live trading is committed with a documented rationale
- **State persists** across restarts — the bot resumes where it left off if restarted within 2h
