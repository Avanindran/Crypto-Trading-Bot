"""
tests/test_risk.py — Unit tests for DrawdownTracker, gross cap overrides,
and per-position stop logic.

All tests are pure in-memory — no API calls, no file I/O.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.risk.drawdown import DrawdownLevel, DrawdownTracker
from bot.risk.kill_switch import per_position_stop_check


class TestDrawdownTracker(unittest.TestCase):

    def test_caution_at_exactly_minus_5pct(self):
        """−5% from peak triggers CAUTION, not NORMAL."""
        dt = DrawdownTracker(1_000_000)
        state = dt.update(950_000, {}, {})
        self.assertEqual(state.level, DrawdownLevel.CAUTION)

    def test_defensive_at_minus_8pct(self):
        """−8% from peak triggers DEFENSIVE."""
        dt = DrawdownTracker(1_000_000)
        state = dt.update(920_000, {}, {})
        self.assertEqual(state.level, DrawdownLevel.DEFENSIVE)

    def test_emergency_at_minus_12pct_sets_recovery(self):
        """−12% triggers EMERGENCY and sets in_recovery=True."""
        dt = DrawdownTracker(1_000_000)
        state = dt.update(880_000, {}, {})
        self.assertEqual(state.level, DrawdownLevel.EMERGENCY)
        self.assertTrue(state.in_recovery)

    def test_peak_updates_on_new_high(self):
        """After a new NAV high, drawdown is measured from the new peak, not start."""
        dt = DrawdownTracker(1_000_000)
        dt.update(1_100_000, {}, {})          # new peak = 1,100,000
        state = dt.update(1_000_000, {}, {})  # −9.09% from 1.1M peak
        self.assertLess(state.drawdown_pct, -0.09)
        self.assertEqual(state.level, DrawdownLevel.DEFENSIVE)

    def test_recovery_gate_blocks_then_unblocks(self):
        """After kill switch, in_recovery blocks until drawdown recovers above −8%."""
        dt = DrawdownTracker(1_000_000)
        dt.update(880_000, {}, {})            # −12% → EMERGENCY, in_recovery=True
        state = dt.update(910_000, {}, {})    # −9% from peak → still in recovery
        self.assertTrue(state.in_recovery)
        state = dt.update(930_000, {}, {})    # −7% from peak → gate passes
        self.assertFalse(state.in_recovery)

    def test_positions_included_in_nav(self):
        """NAV correctly sums free USD and open position value."""
        dt = DrawdownTracker(1_000_000)
        # 500k free + 2 ETH at $200k each = 900k NAV → −10% → DEFENSIVE
        state = dt.update(500_000, {"ETH/USD": 2.0}, {"ETH/USD": 200_000.0})
        self.assertAlmostEqual(state.current_nav, 900_000, delta=1.0)
        self.assertEqual(state.level, DrawdownLevel.DEFENSIVE)

    def test_persistence_round_trip(self):
        """to_dict / from_dict preserves peak_nav and in_recovery across restart."""
        dt = DrawdownTracker(1_000_000)
        dt.update(1_100_000, {}, {})   # push peak to 1.1M
        dt.update(880_000, {}, {})     # trigger emergency (−20% from 1.1M)
        saved = dt.to_dict()
        # Simulate restart at 880k NAV
        dt2 = DrawdownTracker(880_000)
        dt2.from_dict(saved)
        self.assertAlmostEqual(dt2.peak_nav, 1_100_000, delta=1.0)
        self.assertTrue(dt2.in_recovery)

    def test_normal_below_caution_threshold(self):
        """NAV at −4.9% (just above CAUTION threshold) stays NORMAL."""
        dt = DrawdownTracker(1_000_000)
        state = dt.update(951_000, {}, {})  # −4.9%
        self.assertEqual(state.level, DrawdownLevel.NORMAL)


class TestGrossCapOverride(unittest.TestCase):

    def test_override_values_match_config(self):
        """Gross cap overrides match documented drawdown thresholds."""
        dt = DrawdownTracker(1_000_000)
        self.assertIsNone(dt.gross_cap_override(DrawdownLevel.NORMAL))
        self.assertEqual(dt.gross_cap_override(DrawdownLevel.CAUTION), 0.50)
        self.assertEqual(dt.gross_cap_override(DrawdownLevel.DEFENSIVE), 0.30)
        self.assertEqual(dt.gross_cap_override(DrawdownLevel.EMERGENCY), 0.00)


class TestPerPositionStop(unittest.TestCase):

    def test_hard_stop_triggers_below_stop_price(self):
        """Hard stop fires when price drops below entry × (1 + STOP_LOSS_PCT)."""
        # STOP_LOSS_PCT = −0.03 → stop at 970.0; 969 < 970 → should stop
        should_stop, reason = per_position_stop_check("X", 1000.0, 969.0, 1000.0)
        self.assertTrue(should_stop)
        self.assertIn("Hard stop", reason)

    def test_hard_stop_not_triggered_above_stop_price(self):
        """No hard stop when current price is above stop price threshold."""
        # stop at 970.0; 971 > 970 → should not stop
        should_stop, _ = per_position_stop_check("X", 1000.0, 971.0, 1000.0)
        self.assertFalse(should_stop)

    def test_trailing_stop_triggers_after_gain(self):
        """Trailing stop fires once gain ≥ TRAILING_STOP_ACTIVATION and price retraces."""
        # Entry 1000, high 1050 (+5% ≥ +3% activation), trail at 1050×0.975=1023.75
        # current 1022 < 1023.75 → trailing stop fires
        should_stop, reason = per_position_stop_check("X", 1000.0, 1022.0, 1050.0)
        self.assertTrue(should_stop)
        self.assertIn("Trailing stop", reason)

    def test_trailing_stop_not_active_before_activation(self):
        """Trailing stop is silent when max gain < TRAILING_STOP_ACTIVATION (+3%)."""
        # Entry 1000, high 1020 (+2% < +3% threshold) → trailing stop inactive
        # Hard stop at 970; price=990 > 970 → no hard stop either
        should_stop, _ = per_position_stop_check("X", 1000.0, 990.0, 1020.0)
        self.assertFalse(should_stop)


if __name__ == "__main__":
    unittest.main()
