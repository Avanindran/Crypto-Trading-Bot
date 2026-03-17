"""
bot/data/market_cache.py — Rolling price history store.

Accumulates ticker snapshots from the Roostoo API into per-asset deques.
All feature computation operates on this cache.

Design constraints:
  - Roostoo provides ticker SNAPSHOTS only (no OHLCV) — we build history ourselves.
  - 300 snapshots at 1-min polling = ~5 hours of coverage.
  - The 24h return is available free from the ticker Change field; stored separately.

TickerSnapshot namedtuple: (timestamp_ms, last_price, bid, ask, change_24h)
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Deque, List, NamedTuple, Optional, Set


class TickerSnapshot(NamedTuple):
    """One ticker observation for a single asset."""
    timestamp_ms: int       # Wall-clock time of this snapshot
    last_price: float       # LastPrice from ticker
    bid: float              # MaxBid
    ask: float              # MinAsk
    change_24h: float       # Change (24h pct, e.g. 0.0132 = +1.32%)


class MarketCache:
    """
    Rolling per-asset price history.

    Usage:
        cache = MarketCache(maxlen=300)
        cache.ingest(ticker_data)   # Call once per loop with full ticker dict
    """

    def __init__(self, maxlen: int = 300) -> None:
        self._maxlen = maxlen
        # Dict[pair, deque of TickerSnapshot]
        self._data: Dict[str, Deque[TickerSnapshot]] = {}
        self._last_ingest_ts: int = 0

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest(self, ticker_data: Dict) -> Set[str]:
        """
        Process one full ticker response and append snapshots.

        Args:
            ticker_data: The "Data" dict from /v3/ticker (all pairs).

        Returns:
            Set of pair symbols successfully ingested.
        """
        now_ms = int(time.time() * 1000)
        self._last_ingest_ts = now_ms
        ingested: Set[str] = set()

        for pair, info in ticker_data.items():
            try:
                snap = TickerSnapshot(
                    timestamp_ms=now_ms,
                    last_price=float(info["LastPrice"]),
                    bid=float(info["MaxBid"]),
                    ask=float(info["MinAsk"]),
                    change_24h=float(info.get("Change", 0.0)),
                )
            except (KeyError, ValueError, TypeError):
                continue

            if pair not in self._data:
                self._data[pair] = deque(maxlen=self._maxlen)
            self._data[pair].append(snap)
            ingested.add(pair)

        return ingested

    # ── Accessors ──────────────────────────────────────────────────────────────

    @property
    def pairs(self) -> List[str]:
        """All pairs with at least one snapshot."""
        return list(self._data.keys())

    def snapshot_count(self, pair: str) -> int:
        """Number of stored snapshots for a pair."""
        return len(self._data.get(pair, []))

    def latest(self, pair: str) -> Optional[TickerSnapshot]:
        """Most recent snapshot for a pair, or None if not available."""
        history = self._data.get(pair)
        if not history:
            return None
        return history[-1]

    def prices(self, pair: str, n: int) -> List[float]:
        """
        Return the last n close prices for a pair (oldest first).
        Returns fewer than n if insufficient history.
        """
        history = self._data.get(pair)
        if not history:
            return []
        data = list(history)
        return [s.last_price for s in data[-n:]]

    def timestamps_ms(self, pair: str, n: int) -> List[int]:
        """Return last n timestamps for a pair (oldest first)."""
        history = self._data.get(pair)
        if not history:
            return []
        data = list(history)
        return [s.timestamp_ms for s in data[-n:]]

    def spread_pct(self, pair: str) -> Optional[float]:
        """Current (ask - bid) / last_price for a pair."""
        snap = self.latest(pair)
        if snap is None or snap.last_price <= 0:
            return None
        return (snap.ask - snap.bid) / snap.last_price

    def is_warm(self, pair: str, min_periods: int) -> bool:
        """True when we have enough snapshots to compute features reliably."""
        return self.snapshot_count(pair) >= min_periods

    def global_warmup_complete(self, min_pairs: int, min_periods: int) -> bool:
        """
        True when at least min_pairs assets all have min_periods snapshots.
        Used as the gate before deploying any capital.
        """
        warm_pairs = sum(1 for p in self._data if self.is_warm(p, min_periods))
        return warm_pairs >= min_pairs

    def min_samples_across_pairs(self, pairs: List[str]) -> int:
        """
        Return the minimum snapshot count across the given pairs.

        Used to determine which signal windows are currently available:
          >= 30  → r_30m available (Phase 1 trading can begin)
          >= 120 → r_2h available (Phase 2 signal quality)
          >= 360 → r_6h available (Phase 3 / full signal quality)

        Args:
            pairs: List of pair symbols to check.

        Returns:
            Minimum snapshot count; 0 if any pair has no data.
        """
        if not pairs:
            return 0
        return min(self.snapshot_count(p) for p in pairs)

    def all_snapshots(self, pair: str) -> List[TickerSnapshot]:
        """Return full snapshot history for a pair (oldest first)."""
        history = self._data.get(pair)
        if not history:
            return []
        return list(history)
