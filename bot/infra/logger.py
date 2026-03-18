"""
bot/infra/logger.py — Structured logging for the trading bot.

Three log streams:
  1. trades.csv      — one row per trade event (for audit / Screen 1)
  2. state.jsonl     — one JSON line per cycle (strategy state, scores, regime)
  3. errors.log      — Python logging for warnings and errors

All production output goes through this module. No print() statements.
"""
import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ── Directory setup ──────────────────────────────────────────────────────────
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

TRADE_LOG_PATH = LOGS_DIR / "trades.csv"
STATE_LOG_PATH = LOGS_DIR / "state.jsonl"
ERROR_LOG_PATH = LOGS_DIR / "errors.log"

# ── Trade log columns (required by hackathon rules + Screen 1 audit) ─────────
_TRADE_COLUMNS = [
    "timestamp_utc",
    "pair",
    "side",
    "order_type",
    "requested_qty",
    "requested_price",
    "order_id",
    "status",
    "filled_qty",
    "avg_fill_price",
    "fee_usd",
    "reason",
]


def _ensure_trade_header() -> None:
    """Write CSV header if the trade log does not yet exist."""
    if not TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_TRADE_COLUMNS)
            writer.writeheader()


def setup_logging() -> None:
    """
    Configure the root logger to write INFO+ to stderr and errors.log.
    Call once at bot startup.
    """
    _ensure_trade_header()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler — INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(console)

    # File handler — WARNING and above to errors.log
    file_handler = logging.FileHandler(ERROR_LOG_PATH)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(file_handler)


# ── Trade logger ─────────────────────────────────────────────────────────────

def log_trade(
    pair: str,
    side: str,
    order_type: str,
    requested_qty: float,
    requested_price: Optional[float],
    order_id: Optional[int],
    status: str,
    filled_qty: float = 0.0,
    avg_fill_price: float = 0.0,
    fee_usd: float = 0.0,
    reason: str = "",
) -> None:
    """Append one row to trades.csv. Called after every place_order / cancel_order response."""
    _ensure_trade_header()
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pair": pair,
        "side": side,
        "order_type": order_type,
        "requested_qty": requested_qty,
        "requested_price": requested_price,
        "order_id": order_id,
        "status": status,
        "filled_qty": filled_qty,
        "avg_fill_price": avg_fill_price,
        "fee_usd": fee_usd,
        "reason": reason,
    }
    with open(TRADE_LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_TRADE_COLUMNS)
        writer.writerow(row)


# ── Strategy state logger ─────────────────────────────────────────────────────

def log_state(data: Dict[str, Any]) -> None:
    """
    Append one JSON line to state.jsonl.
    Call once per loop with: cycle metrics, C1 scores, regime state, portfolio snapshot.
    """
    data["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_LOG_PATH, "a") as f:
        f.write(json.dumps(data) + "\n")
