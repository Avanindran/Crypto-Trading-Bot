"""
tests/test_engine_aggregator.py — Unit tests for multi-engine portfolio aggregation.

Tests:
  1. fraction_zero_returns_h1_unchanged   — h2c_fraction=0.0 → h1_weights, same object
  2. empty_h2c_returns_h1_unchanged       — h2c_weights={} → h1_weights unchanged
  3. fraction_one_returns_h2c_only        — h2c_fraction=1.0 → h2c weights only
  4. mixed_fraction_scales_proportionally — fraction=0.4 → each weight scaled correctly
  5. overlapping_assets_weights_add       — both engines hold ETH → weights are additive
  6. gross_cap_preserved                  — combined gross = individual gross × 1
"""
import sys
import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from bot.strategy.engine_aggregator import aggregate_engine_portfolios


class TestAggregateEnginePortfolios(unittest.TestCase):

    def test_fraction_zero_returns_h1_unchanged(self):
        """h2c_fraction=0.0 is the no-op fast path — must return exactly h1_weights."""
        h1  = {"ETHUSDT": 0.40, "SOLUSDT": 0.30}
        h2c = {"AAVEUSDT": 0.50}
        result = aggregate_engine_portfolios(h1, h2c, h2c_capital_fraction=0.0)
        self.assertIs(result, h1)

    def test_empty_h2c_returns_h1_unchanged(self):
        """h2c_weights={} → returns h1_weights unchanged (same object)."""
        h1 = {"ETHUSDT": 0.40, "SOLUSDT": 0.30}
        result = aggregate_engine_portfolios(h1, {}, h2c_capital_fraction=0.4)
        self.assertIs(result, h1)

    def test_fraction_one_returns_h2c_only(self):
        """h2c_fraction=1.0 → h2c weights unchanged; h1 pairs contribute 0."""
        h1  = {"ETHUSDT": 0.40}
        h2c = {"AAVEUSDT": 0.50, "BTCUSDT": 0.35}
        result = aggregate_engine_portfolios(h1, h2c, h2c_capital_fraction=1.0)
        # h1 fraction = 0.0 → h1 pair weight is 0.0; h2c fraction = 1.0
        self.assertAlmostEqual(result.get("ETHUSDT", 0.0), 0.0,  places=10)
        self.assertAlmostEqual(result["AAVEUSDT"], 0.50, places=10)
        self.assertAlmostEqual(result["BTCUSDT"],  0.35, places=10)

    def test_mixed_fraction_scales_proportionally(self):
        """fraction=0.4 → each engine's weights scaled by its fraction."""
        h1  = {"ETHUSDT": 0.50, "SOLUSDT": 0.30}
        h2c = {"AAVEUSDT": 0.60}
        result = aggregate_engine_portfolios(h1, h2c, h2c_capital_fraction=0.4)

        self.assertAlmostEqual(result["ETHUSDT"],  0.50 * 0.6, places=10)
        self.assertAlmostEqual(result["SOLUSDT"],  0.30 * 0.6, places=10)
        self.assertAlmostEqual(result["AAVEUSDT"], 0.60 * 0.4, places=10)

    def test_overlapping_assets_weights_add(self):
        """Both engines hold ETH → combined weight is additive."""
        h1  = {"ETHUSDT": 0.40, "SOLUSDT": 0.30}
        h2c = {"ETHUSDT": 0.20, "AAVEUSDT": 0.30}
        result = aggregate_engine_portfolios(h1, h2c, h2c_capital_fraction=0.5)

        expected_eth = 0.40 * 0.5 + 0.20 * 0.5   # = 0.30
        expected_sol = 0.30 * 0.5                 # = 0.15
        expected_aave = 0.30 * 0.5                # = 0.15

        self.assertAlmostEqual(result["ETHUSDT"],  expected_eth,  places=10)
        self.assertAlmostEqual(result["SOLUSDT"],  expected_sol,  places=10)
        self.assertAlmostEqual(result["AAVEUSDT"], expected_aave, places=10)

    def test_gross_cap_preserved(self):
        """Combined gross exposure = sum(h1)*h1_frac + sum(h2c)*h2c_frac."""
        h1  = {"A": 0.40, "B": 0.30}    # sum = 0.70 (gross_cap 70%)
        h2c = {"C": 0.40, "D": 0.30}    # sum = 0.70
        fraction = 0.4
        result = aggregate_engine_portfolios(h1, h2c, h2c_capital_fraction=fraction)

        combined_gross = sum(result.values())
        expected_gross = 0.70 * (1 - fraction) + 0.70 * fraction  # = 0.70
        self.assertAlmostEqual(combined_gross, expected_gross, places=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
