"""
bot/data/fear_greed_client.py — Crypto Fear & Greed Index from Alternative.me.

The Fear & Greed Index is a composite sentiment measure (0–100):
  0–24: Extreme Fear       (capitulation — potential contrarian buy signal)
  25–49: Fear
  50–74: Greed
  75–100: Extreme Greed    (euphoria — elevated reversal risk)

Unlike our price-based LSI components (which are backward-looking), F&G is a
leading sentiment signal: extreme greed historically precedes price corrections
as leveraged positioning unwinds. Adding it to LSI provides early-warning
capability before realized volatility spikes.

Data source: Alternative.me public API (no authentication required).
Update cadence: once daily — cached for FNG_REFRESH_HOURS hours.
"""
import logging
import time
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

_FNG_URL = "https://api.alternative.me/fng/?limit=1"
_REQUEST_TIMEOUT = 5  # seconds


class FearGreedClient:
    """
    Fetches the current Crypto Fear & Greed Index from Alternative.me.

    Returns a value 0–100, or None on failure.
    Caches the result for FNG_REFRESH_HOURS to avoid redundant calls.
    """

    def __init__(self) -> None:
        self._cached_value: Optional[float] = None
        self._last_fetch_ts: float = 0.0

    def get_fear_greed_value(self) -> Optional[float]:
        """
        Return current Fear & Greed Index value (0–100).

        Refreshes at most once every FNG_REFRESH_HOURS hours.
        Returns None on fetch failure — callers must handle gracefully.
        """
        age_hours = (time.time() - self._last_fetch_ts) / 3600.0
        if self._cached_value is not None and age_hours < config.FNG_REFRESH_HOURS:
            return self._cached_value

        return self._refresh()

    def _refresh(self) -> Optional[float]:
        """Fetch fresh Fear & Greed value from Alternative.me."""
        try:
            resp = requests.get(_FNG_URL, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            entries = data.get("data", [])
            if not entries:
                logger.warning("Fear & Greed API returned empty data")
                return self._cached_value

            value_str = entries[0].get("value", None)
            if value_str is None:
                return self._cached_value

            value = float(value_str)
            self._cached_value = value
            self._last_fetch_ts = time.time()

            classification = entries[0].get("value_classification", "")
            logger.info("Fear & Greed Index refreshed: %.0f (%s)", value, classification)
            return value

        except Exception as exc:
            logger.warning("Fear & Greed fetch failed: %s — using cached value", exc)
            return self._cached_value
