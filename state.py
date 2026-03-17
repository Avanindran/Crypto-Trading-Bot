"""
state.py — Bot state persistence.

Saves and loads the full bot state to/from bot_state.json.
On crash or restart, if the state file is fresh (< STATE_MAX_AGE_SECONDS),
the bot resumes with the same positions and timing constraints.

Stale state files (> 2h) are ignored — the bot starts fresh with a
reconciliation against the live API balance.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent / "bot_state.json"
STATE_MAX_AGE_SECONDS = 2 * 3600  # Ignore state files older than 2h


def save_state(data: Dict[str, Any]) -> None:
    """
    Persist bot state to disk. Called once per loop iteration.

    Args:
        data: State dict. Must be JSON-serializable.
    """
    data["saved_at"] = time.time()
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.warning("Failed to save state: %s", exc)


def load_state() -> Optional[Dict[str, Any]]:
    """
    Load state from disk if the file is fresh enough.

    Returns:
        State dict if valid and recent, None otherwise (start fresh).
    """
    if not STATE_FILE.exists():
        return None

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("Failed to load state file: %s", exc)
        return None

    saved_at = data.get("saved_at", 0)
    age = time.time() - saved_at
    if age > STATE_MAX_AGE_SECONDS:
        logger.info("State file is %.0f minutes old — too stale, starting fresh", age / 60)
        return None

    logger.info("Loaded state from %.0f minutes ago", age / 60)
    return data


def clear_state() -> None:
    """Delete the state file (used after emergency exit or explicit reset)."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        logger.info("State file cleared")
