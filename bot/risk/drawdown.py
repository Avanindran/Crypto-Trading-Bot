"""
bot/risk/drawdown.py — Portfolio NAV tracking and drawdown level management.

Tracks portfolio NAV over time and triggers risk responses at three levels.
Designed to maximize Sortino by preventing large negative return episodes
and to protect Calmar by hard-capping max drawdown at -12%.

Drawdown levels (from peak NAV):
  NORMAL:     drawdown > -5%   → full strategy parameters
  CAUTION:    -8% < dd ≤ -5%  → reduce positions and gross cap
  DEFENSIVE:  -12% < dd ≤ -8% → minimal exposure
  EMERGENCY:  dd ≤ -12%        → kill switch (emergency exit all)

Recovery gate: After a kill-switch event, no new trades until drawdown
recovers to RECOVERY_GATE level (-8%), preventing re-entry into a falling market.
"""
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import config

logger = logging.getLogger(__name__)


class DrawdownLevel(Enum):
    """Drawdown severity classification driving portfolio risk response."""
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    DEFENSIVE = "DEFENSIVE"
    EMERGENCY = "EMERGENCY"


@dataclass
class DrawdownState:
    """Current drawdown metrics."""
    peak_nav: float
    current_nav: float
    drawdown_pct: float      # Negative number, e.g. -0.07 = -7% drawdown
    level: DrawdownLevel
    in_recovery: bool        # True after kill switch until recovery gate passed


class DrawdownTracker:
    """
    Tracks portfolio NAV and classifies current drawdown severity.

    NAV is computed as: USD free + sum(position_qty × last_price)
    Updated on every loop with the latest balance and prices.
    """

    def __init__(self, initial_nav: float) -> None:
        self._peak_nav: float = initial_nav
        self._current_nav: float = initial_nav
        self._nav_history: List[Tuple[float, float]] = [(time.time(), initial_nav)]
        self._in_recovery: bool = False
        self._level: DrawdownLevel = DrawdownLevel.NORMAL

    def update(
        self,
        usd_free: float,
        usd_locked: float,
        positions: dict,  # pair → qty
        prices: dict,     # pair → last_price
    ) -> DrawdownState:
        """
        Recompute current NAV and return updated drawdown state.

        Args:
            usd_free:    Free USD in wallet.
            usd_locked:  Locked USD in pending orders.
            positions:   Dict[pair, qty] of open positions.
            prices:      Dict[pair, last_price] from latest ticker.

        Returns:
            DrawdownState with current metrics.
        """
        # Compute position value (includes both free and locked coins)
        position_value = 0.0
        for pair, qty in positions.items():
            price = prices.get(pair)
            if price and price > 0 and qty > 0:
                position_value += qty * price

        # Calculate total USD (free + locked)
        total_usd = usd_free + usd_locked
        
        # Calculate total NAV: USD (free + locked) + position value
        current_nav = total_usd + position_value
        
        # Debug logging for NAV breakdown
        logger.info(f"NAV Breakdown - Cash: ${total_usd:.2f} | Assets: ${position_value:.2f} | Total: ${current_nav:.2f}")
        
        self._current_nav = current_nav
        self._nav_history.append((time.time(), current_nav))

        # Keep last 1440 observations (24h at 1-min polling)
        if len(self._nav_history) > 1440:
            self._nav_history = self._nav_history[-1440:]

        # Update peak
        if current_nav > self._peak_nav:
            self._peak_nav = current_nav

        # Compute drawdown
        drawdown_pct = (current_nav - self._peak_nav) / self._peak_nav if self._peak_nav > 0 else 0.0

        # Classify level
        if drawdown_pct <= config.DRAWDOWN_KILL:
            level = DrawdownLevel.EMERGENCY
        elif drawdown_pct <= config.DRAWDOWN_DEFENSIVE:
            level = DrawdownLevel.DEFENSIVE
        elif drawdown_pct <= config.DRAWDOWN_CAUTION:
            level = DrawdownLevel.CAUTION
        else:
            level = DrawdownLevel.NORMAL

        # Recovery gate management
        if level == DrawdownLevel.EMERGENCY:
            self._in_recovery = True
            logger.warning(
                "KILL SWITCH TRIGGERED — NAV=%.2f peak=%.2f drawdown=%.2f%%",
                current_nav, self._peak_nav, drawdown_pct * 100,
            )
        elif self._in_recovery and drawdown_pct > config.DRAWDOWN_RECOVERY_GATE:
            self._in_recovery = False
            logger.info(
                "Recovery gate passed — drawdown=%.2f%% resuming normal trading",
                drawdown_pct * 100,
            )

        self._level = level

        if level != DrawdownLevel.NORMAL:
            logger.info(
                "Drawdown status: %s — NAV=%.2f peak=%.2f dd=%.2f%%",
                level.value, current_nav, self._peak_nav, drawdown_pct * 100,
            )

        return DrawdownState(
            peak_nav=self._peak_nav,
            current_nav=current_nav,
            drawdown_pct=drawdown_pct,
            level=level,
            in_recovery=self._in_recovery,
        )

    def gross_cap_override(self, level: DrawdownLevel) -> Optional[float]:
        """
        Return a gross cap override based on drawdown level.
        Returns None to use regime default when drawdown is normal.
        """
        if level == DrawdownLevel.CAUTION:
            return 0.50    # Max 50% NAV deployed
        if level == DrawdownLevel.DEFENSIVE:
            return 0.30    # Max 30% NAV deployed
        if level == DrawdownLevel.EMERGENCY:
            return 0.00    # No new positions
        return None        # Use regime default

    @property
    def current_nav(self) -> float:
        return self._current_nav

    @property
    def peak_nav(self) -> float:
        return self._peak_nav

    @property
    def in_recovery(self) -> bool:
        return self._in_recovery

    @property
    def level(self) -> DrawdownLevel:
        return self._level

    def to_dict(self) -> dict:
        """Serialize drawdown state for crash-safe restart."""
        return {
            "peak_nav": self._peak_nav,
            "in_recovery": self._in_recovery,
        }

    def from_dict(self, data: dict) -> None:
        """
        Restore peak NAV and recovery gate from saved state.

        IMPORTANT: Only restores peak if the saved value exceeds current NAV.
        This guards against stale state from a different trading session where
        the bot restarted with a higher initial balance.

        However, if the saved peak is much higher than current NAV (indicating
        a significant portfolio change), we should NOT restore it as it would
        cause incorrect drawdown calculations.
        """
        saved_peak = data.get("peak_nav", 0.0)
        current_nav = self._current_nav
        
        # Only restore peak if:
        # 1. Saved peak is higher than current peak (normal case)
        # 2. Saved peak is not significantly higher than current NAV (prevents stale state)
        # Use a threshold of 50% to detect stale state
        if saved_peak > self._peak_nav and saved_peak <= current_nav * 1.5:
            self._peak_nav = saved_peak
            logger.info("Restored peak NAV from saved state: %.2f", saved_peak)
        elif saved_peak > current_nav * 1.5:
            logger.warning(
                "Saved peak NAV (%.2f) is much higher than current NAV (%.2f) - ignoring stale state",
                saved_peak, current_nav
            )
        else:
            logger.info("Saved peak NAV (%.2f) not higher than current peak (%.2f) - keeping current",
                       saved_peak, self._peak_nav)
        
        self._in_recovery = data.get("in_recovery", False)
