"""
bot/data/funding_rate_client.py — Funding rate fetcher from Binance Futures public API.

Funding rate measures positioning overextension in perpetual futures markets.
High positive funding (longs pay shorts) signals crowded long positioning:
the expected drift has already been captured by leveraged participants,
indicating elevated diffusion maturity M_t for the underlying spot asset.

Data source: Binance Futures public API (no authentication required).
Refresh cadence: every FUNDING_RATE_REFRESH_LOOPS loops (~10 min) since
funding updates only every 8 hours.
"""
import logging
import time
from typing import Dict, Optional

import requests

import config

logger = logging.getLogger(__name__)

_BINANCE_FAPI_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
_REQUEST_TIMEOUT = 5  # seconds


class FundingRateClient:
    """
    Fetches current funding rates from Binance perpetual futures.

    Returns per-pair funding rates keyed by symbol (e.g. "BTCUSDT").
    Falls back to empty dict on any error — callers must handle missing values.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, float] = {}
        self._last_fetch_loop: int = -config.FUNDING_RATE_REFRESH_LOOPS  # Force fetch on first call

    def get_funding_rates(self, loop_count: int) -> Dict[str, float]:
        """
        Return funding rates for all available symbols.

        Refreshes every FUNDING_RATE_REFRESH_LOOPS loops; otherwise returns cache.

        Args:
            loop_count: Current main loop iteration count.

        Returns:
            Dict[symbol, last_funding_rate] — e.g. {"BTCUSDT": 0.0001, "ETHUSDT": 0.00012}
            Empty dict if fetch fails.
        """
        loops_since_fetch = loop_count - self._last_fetch_loop
        if loops_since_fetch < config.FUNDING_RATE_REFRESH_LOOPS:
            return self._cache

        return self._refresh(loop_count)

    def _refresh(self, loop_count: int) -> Dict[str, float]:
        """Fetch fresh data from Binance fapi and update cache."""
        try:
            resp = requests.get(_BINANCE_FAPI_URL, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            rates: Dict[str, float] = {}
            for entry in data:
                symbol = entry.get("symbol", "")
                rate_str = entry.get("lastFundingRate", None)
                if symbol and rate_str is not None:
                    try:
                        rates[symbol] = float(rate_str)
                    except (ValueError, TypeError):
                        pass

            self._cache = rates
            self._last_fetch_loop = loop_count
            logger.debug("Funding rates refreshed: %d symbols", len(rates))
            return rates

        except Exception as exc:
            logger.warning("Funding rate fetch failed: %s — using cached values", exc)
            return self._cache


def get_asset_funding_rate(
    funding_rates: Dict[str, float],
    pair: str,
) -> Optional[float]:
    """
    Look up funding rate for a Roostoo trading pair.

    Roostoo pairs use the same naming convention as Binance (e.g. "BTCUSDT"),
    so no translation is needed.

    Args:
        funding_rates: Output of FundingRateClient.get_funding_rates().
        pair:          Trading pair symbol (e.g. "BTCUSDT").

    Returns:
        Current funding rate (e.g. 0.0001 = 0.01%/8h), or None if not found.
    """
    return funding_rates.get(pair, None)
