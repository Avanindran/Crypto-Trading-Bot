# Logging is in bot/infra/logger.py:
#   - log_trade()  → appends to logs/trades.csv  (per-trade audit log)
#   - log_state()  → appends to logs/state.jsonl  (per-loop strategy state)
#   - setup_logging() → configures Python logging → logs/errors.log
