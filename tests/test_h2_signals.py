"""
tests/test_h2_signals.py — Unit tests for H2C BTC-Diffusion engine.

Tests:
  1. update_accumulates_history  — after N calls ≥1h apart, history has N entries
  2. update_respects_1h_cadence  — sub-1h calls don't add entries
  3. update_caps_at_window       — history is capped at H2C_BETA_WINDOW (48)
  4. compute_h2c_insufficient    — returns None when pairs < H2C_BETA_MIN_OBS obs
  5. compute_h2c_few_pairs       — returns None when <4 pairs qualify
  6. compute_h2c_known_data      — known beta + r_BTC → expected gap sign
  7. roundtrip_serialization     — to_dict / from_dict preserves all state
"""
import sys
import os
import math
import unittest
from collections import deque
from unittest.mock import MagicMock

# Resolve project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import config
from bot.strategy.h2_signals import BetaHistoryManager, compute_h2c_scores
from bot.data.feature_builder import AssetFeatures


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_cache(prices_by_pair: dict) -> MagicMock:
    """Build a MarketCache mock that returns fixed price lists."""
    cache = MagicMock()
    def _prices(pair, n):
        p = prices_by_pair.get(pair, [])
        return p[-n:] if len(p) >= n else p
    cache.prices.side_effect = _prices
    return cache


def _make_manager(pairs, btc_key="BTCUSDT"):
    return BetaHistoryManager(pairs, btc_key)


def _asset_feat(r_2h=None):
    """Return an AssetFeatures-like object with r_2h set."""
    feat = MagicMock(spec=AssetFeatures)
    feat.r_2h = r_2h
    return feat


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBetaHistoryManagerUpdate(unittest.TestCase):

    def test_update_accumulates_history(self):
        """After N calls at ≥1h intervals, each pair has N history entries."""
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        mgr   = _make_manager(pairs)

        # Build a cache with 61 constant prices per pair (1h return = 0)
        prices_by_pair = {p: [100.0] * 61 for p in pairs}
        cache = _make_cache(prices_by_pair)

        N = 5
        for i in range(N):
            ts_ms = (i + 1) * 3_600_000  # each call is exactly 1h apart (first at 1h since epoch=0)
            mgr.update(cache, ts_ms)

        for pair in ["ETHUSDT", "SOLUSDT"]:
            self.assertEqual(len(mgr._hist[pair]["r_i"]),   N)
            self.assertEqual(len(mgr._hist[pair]["r_btc"]), N)

    def test_update_respects_1h_cadence(self):
        """Calls within 1h of the previous update are ignored."""
        pairs = ["BTCUSDT", "ETHUSDT"]
        mgr   = _make_manager(pairs)

        prices_by_pair = {"BTCUSDT": [100.0] * 61, "ETHUSDT": [200.0] * 61}
        cache = _make_cache(prices_by_pair)

        mgr.update(cache, 3_600_000)   # t=1h — first update (triggers since _last_update_ms=0)
        mgr.update(cache, 5_400_000)   # t=1h30m — only 30min elapsed, ignored
        mgr.update(cache, 7_199_999)   # t=~2h-1ms — still < 1h since last, ignored

        self.assertEqual(len(mgr._hist["ETHUSDT"]["r_i"]), 1)

    def test_update_caps_at_window(self):
        """History list is capped at H2C_BETA_WINDOW entries."""
        pairs = ["BTCUSDT", "ETHUSDT"]
        mgr   = _make_manager(pairs)

        prices_by_pair = {"BTCUSDT": [100.0] * 61, "ETHUSDT": [200.0] * 61}
        cache = _make_cache(prices_by_pair)

        # Feed more than window entries
        n_calls = config.H2C_BETA_WINDOW + 5
        for i in range(n_calls):
            mgr.update(cache, i * 3_600_000)

        self.assertEqual(len(mgr._hist["ETHUSDT"]["r_i"]),   config.H2C_BETA_WINDOW)
        self.assertEqual(len(mgr._hist["ETHUSDT"]["r_btc"]), config.H2C_BETA_WINDOW)

    def test_btc_key_excluded_from_hist(self):
        """BTC itself is not tracked in _hist (it's the reference asset)."""
        pairs = ["BTCUSDT", "ETHUSDT"]
        mgr   = _make_manager(pairs)
        self.assertNotIn("BTCUSDT", mgr._hist)
        self.assertIn("ETHUSDT", mgr._hist)


class TestComputeH2cScores(unittest.TestCase):

    def _fill_history(self, mgr, r_i_val: float, r_btc_val: float,
                      n: int = None) -> None:
        """Directly fill manager history with constant returns."""
        n = n if n is not None else config.H2C_BETA_MIN_OBS
        for pair in mgr._hist:
            mgr._hist[pair]["r_i"]   = [r_i_val]  * n
            mgr._hist[pair]["r_btc"] = [r_btc_val] * n

    def test_returns_none_when_btc_r2h_none(self):
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        mgr   = _make_manager(pairs)
        self._fill_history(mgr, 0.01, 0.02)
        features = {p: _asset_feat(r_2h=0.01) for p in pairs if p != "BTCUSDT"}
        result = compute_h2c_scores(features, mgr, btc_r2h=None)
        self.assertIsNone(result)

    def test_returns_none_when_insufficient_observations(self):
        """Returns None when pairs have fewer than H2C_BETA_MIN_OBS obs."""
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        mgr   = _make_manager(pairs)
        # Only 3 observations — below minimum
        self._fill_history(mgr, 0.01, 0.02, n=3)
        features = {p: _asset_feat(r_2h=0.01) for p in pairs if p != "BTCUSDT"}
        result = compute_h2c_scores(features, mgr, btc_r2h=0.02)
        self.assertIsNone(result)

    def test_returns_none_when_fewer_than_4_pairs_qualify(self):
        """Returns None when <4 pairs have sufficient history."""
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        mgr   = _make_manager(pairs)
        # Only 2 non-BTC pairs; fill both but result still needs ≥4 pairs to qualify
        # Use 3 pairs total (non-BTC = 2) — must return None
        features = {p: _asset_feat(r_2h=0.01) for p in ["ETHUSDT", "SOLUSDT"]}
        self._fill_history(mgr, 0.01, 0.02)
        # Override BNBUSDT to have 0 obs
        mgr._hist["BNBUSDT"]["r_i"]   = []
        mgr._hist["BNBUSDT"]["r_btc"] = []
        result = compute_h2c_scores(features, mgr, btc_r2h=0.02)
        self.assertIsNone(result)

    def test_known_data_gap_sign(self):
        """Asset that lagged BTC's move should have a positive gap and positive z-score.

        Setup: β ≈ 1 for all assets, r_BTC,2h = +2%
        ETHUSDT r_2h = +1.5% → gap = 1.0×0.02 − 0.015 = +0.005  (laggard → buy signal)
        SOLUSDT r_2h = +2.5% → gap = 1.0×0.02 − 0.025 = −0.005  (leader → sell signal)
        """
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        mgr   = _make_manager(pairs)

        # Set β ≈ 1 by making r_i ≈ r_btc with a small spread
        for pair in mgr._hist:
            mgr._hist[pair]["r_i"]   = [0.02] * config.H2C_BETA_MIN_OBS
            mgr._hist[pair]["r_btc"] = [0.02] * config.H2C_BETA_MIN_OBS

        # ETHUSDT lagged BTC (r_2h < beta × r_BTC)
        features = {
            "ETHUSDT": _asset_feat(r_2h=0.015),   # gap = 0.02×1 - 0.015 = +0.005
            "SOLUSDT": _asset_feat(r_2h=0.025),   # gap = 0.02×1 - 0.025 = -0.005
            "BNBUSDT": _asset_feat(r_2h=0.020),   # gap ≈ 0
            "XRPUSDT": _asset_feat(r_2h=0.010),   # gap = +0.010
        }

        result = compute_h2c_scores(features, mgr, btc_r2h=0.02)
        self.assertIsNotNone(result)
        # ETH and XRP should have positive z-score (laggards — buy signal)
        self.assertGreater(result["ETHUSDT"], 0.0)
        self.assertGreater(result["XRPUSDT"], 0.0)
        # SOL should have negative z-score (ahead of BTC diffusion)
        self.assertLess(result["SOLUSDT"], 0.0)

    def test_output_is_zero_mean_unit_variance(self):
        """Output z-scores should be approximately zero-mean unit-variance."""
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        mgr   = _make_manager(pairs)

        # Varied beta history to produce meaningful variance
        returns = [0.01, 0.02, 0.015, 0.005, 0.025]
        for i, pair in enumerate(mgr._hist):
            r = returns[i % len(returns)]
            mgr._hist[pair]["r_i"]   = [r]   * config.H2C_BETA_MIN_OBS
            mgr._hist[pair]["r_btc"] = [0.02] * config.H2C_BETA_MIN_OBS

        features = {
            "ETHUSDT": _asset_feat(r_2h=0.01),
            "SOLUSDT": _asset_feat(r_2h=0.02),
            "BNBUSDT": _asset_feat(r_2h=0.015),
            "XRPUSDT": _asset_feat(r_2h=0.005),
        }

        result = compute_h2c_scores(features, mgr, btc_r2h=0.02)
        self.assertIsNotNone(result)

        vals  = list(result.values())
        mean  = sum(vals) / len(vals)
        var   = sum((v - mean) ** 2 for v in vals) / len(vals)
        std   = math.sqrt(var)
        self.assertAlmostEqual(mean, 0.0, places=10)
        self.assertAlmostEqual(std,  1.0, places=5)


class TestBetaHistoryManagerSerialization(unittest.TestCase):

    def test_roundtrip_preserves_history(self):
        """to_dict / from_dict roundtrip preserves all history and timestamp."""
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        mgr   = _make_manager(pairs)

        # Manually populate history
        mgr._hist["ETHUSDT"]["r_i"]   = [0.01, 0.02, 0.015]
        mgr._hist["ETHUSDT"]["r_btc"] = [0.02, 0.025, 0.018]
        mgr._hist["SOLUSDT"]["r_i"]   = [0.05, 0.04]
        mgr._hist["SOLUSDT"]["r_btc"] = [0.02, 0.021]
        mgr._last_update_ms = 12345678

        data = mgr.to_dict()
        mgr2  = BetaHistoryManager.from_dict(data, pairs, "BTCUSDT")

        self.assertEqual(mgr2._hist["ETHUSDT"]["r_i"],   [0.01, 0.02, 0.015])
        self.assertEqual(mgr2._hist["ETHUSDT"]["r_btc"], [0.02, 0.025, 0.018])
        self.assertEqual(mgr2._hist["SOLUSDT"]["r_i"],   [0.05, 0.04])
        self.assertEqual(mgr2._last_update_ms, 12345678)

    def test_from_dict_caps_at_window(self):
        """from_dict caps restored history at window length."""
        pairs = ["BTCUSDT", "ETHUSDT"]
        mgr   = _make_manager(pairs)

        # Inject history longer than window
        long_hist = list(range(config.H2C_BETA_WINDOW + 10))
        data = {
            "hist": {"ETHUSDT": {"r_i": long_hist, "r_btc": long_hist}},
            "last_update_ms": 0,
        }
        mgr2 = BetaHistoryManager.from_dict(data, pairs, "BTCUSDT")
        self.assertEqual(len(mgr2._hist["ETHUSDT"]["r_i"]), config.H2C_BETA_WINDOW)

    def test_from_dict_empty_starts_fresh(self):
        """from_dict with {} starts fresh with empty history."""
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        mgr   = BetaHistoryManager.from_dict({}, pairs, "BTCUSDT")
        self.assertEqual(mgr._hist["ETHUSDT"]["r_i"],   [])
        self.assertEqual(mgr._last_update_ms, 0)

    def test_min_observations(self):
        """min_observations returns the minimum across all pairs."""
        pairs = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        mgr   = _make_manager(pairs)
        mgr._hist["ETHUSDT"]["r_i"] = [0.01, 0.02]
        mgr._hist["SOLUSDT"]["r_i"] = [0.01, 0.02, 0.03]
        self.assertEqual(mgr.min_observations(), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
