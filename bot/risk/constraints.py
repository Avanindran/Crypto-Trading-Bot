"""
bot/risk/constraints.py — Trade timing and position constraints.

Enforces rules that protect Sortino by preventing fee-drag from excessive turnover:

  1. Minimum holding period (4h) — prevents noise-driven churn at 0.10% round-trip cost
  2. Re-entry lockout (2h) — avoids immediately re-buying a just-sold asset
  3. Max hold time (72h) — forces exit of stale positions regardless of signal

Also tracks per-position metadata needed by kill_switch.py:
  - Entry price (for hard stop calculation)
  - High since entry (for trailing stop)
  - Entry timestamp (for hold duration checks)
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import config

logger = logging.getLogger(__name__)


@dataclass
class PositionRecord:
    """Metadata for one open position."""
    pair: str
    entry_price: float
    entry_time: float       # time.time()
    high_since_entry: float  # Rolling high price since entry (for trailing stop)
    qty: float

    def age_seconds(self) -> float:
        return time.time() - self.entry_time

    def age_hours(self) -> float:
        return self.age_seconds() / 3600.0

    def update_high(self, current_price: float) -> None:
        if current_price > self.high_since_entry:
            self.high_since_entry = current_price


class ConstraintEngine:
    """
    Tracks timing constraints and position metadata.

    All constraint checks return (allowed, reason) tuples for logging.
    """

    def __init__(self) -> None:
        self._positions: Dict[str, PositionRecord] = {}
        self._last_exit_time: Dict[str, float] = {}  # pair → exit timestamp

    def record_entry(self, pair: str, entry_price: float, qty: float) -> None:
        """Record a new position entry."""
        self._positions[pair] = PositionRecord(
            pair=pair,
            entry_price=entry_price,
            entry_time=time.time(),
            high_since_entry=entry_price,
            qty=qty,
        )
        logger.info("Position entered: %s @ %.6f qty=%.6f", pair, entry_price, qty)

    def record_exit(self, pair: str) -> None:
        """Record a position exit for re-entry lockout tracking."""
        self._last_exit_time[pair] = time.time()
        self._positions.pop(pair, None)
        logger.info("Position exited: %s", pair)

    def update_price(self, pair: str, current_price: float) -> None:
        """Update the rolling high for an open position (for trailing stop)."""
        record = self._positions.get(pair)
        if record:
            record.update_high(current_price)

    def can_enter(self, pair: str) -> tuple[bool, str]:
        """
        Check if a new entry is allowed for a pair.

        Blocks if:
          - Already have a position in this pair (no double entry)
          - Re-entry lockout is active (within 2h of last exit)
        """
        if pair in self._positions:
            return False, f"Already holding {pair}"

        last_exit = self._last_exit_time.get(pair)
        if last_exit is not None:
            lockout_remaining = config.REENTRY_LOCKOUT_SECONDS - (time.time() - last_exit)
            if lockout_remaining > 0:
                return False, f"Re-entry lockout active for {pair} ({lockout_remaining:.0f}s remaining)"

        return True, ""

    def can_exit(self, pair: str) -> tuple[bool, str]:
        """
        Check if exit is allowed (minimum holding period).
        Returns (True, "") for emergency exits — override by passing ignore_hold=True.
        """
        record = self._positions.get(pair)
        if record is None:
            return True, ""  # Not holding — nothing to prevent

        age = record.age_seconds()
        min_hold = config.MIN_HOLD_SECONDS
        if age < min_hold:
            remaining = min_hold - age
            return False, f"Min hold period not met for {pair} ({remaining:.0f}s remaining)"

        return True, ""

    def should_force_exit(self, pair: str) -> tuple[bool, str]:
        """Check if max hold time has been exceeded — force exit regardless of signal."""
        record = self._positions.get(pair)
        if record is None:
            return False, ""
        if record.age_hours() >= config.MAX_HOLD_HOURS:
            return True, f"Max hold time {config.MAX_HOLD_HOURS}h exceeded for {pair}"
        return False, ""

    def get_position_record(self, pair: str) -> Optional[PositionRecord]:
        return self._positions.get(pair)

    def all_positions(self) -> Dict[str, PositionRecord]:
        return dict(self._positions)

    def to_dict(self) -> dict:
        """Serialize for state persistence."""
        return {
            "positions": {
                pair: {
                    "entry_price": r.entry_price,
                    "entry_time": r.entry_time,
                    "high_since_entry": r.high_since_entry,
                    "qty": r.qty,
                }
                for pair, r in self._positions.items()
            },
            "last_exit_time": dict(self._last_exit_time),
        }

    def from_dict(self, data: dict) -> None:
        """Restore from saved state."""
        for pair, pd in data.get("positions", {}).items():
            self._positions[pair] = PositionRecord(
                pair=pair,
                entry_price=pd["entry_price"],
                entry_time=pd["entry_time"],
                high_since_entry=pd["high_since_entry"],
                qty=pd["qty"],
            )
        self._last_exit_time = data.get("last_exit_time", {})
