"""
tests/test_features.py — Unit tests for feature_builder.py.

Tests that returns, volatility, and cross-sectional aggregates are
computed correctly from known price series.
"""
import sys
import os

# Allow imports from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.data.feature_builder import (
    _safe_return,
    _realized_vol,
    _downside_vol,
    _rsi_proxy,
    _percentile_rank,
    _sma,
    compute_cross_sectional,
    AssetFeatures,
)


class TestSafeReturn:
    def test_basic_return(self):
        # Price goes from 100 to 110 over 30 steps
        prices = [100.0] * 30 + [110.0]
        result = _safe_return(prices, 30)
        assert abs(result - 0.10) < 1e-9, f"Expected 10% return, got {result}"

    def test_insufficient_data(self):
        prices = [100.0] * 5
        result = _safe_return(prices, 30)
        assert result is None

    def test_zero_base_price(self):
        prices = [0.0] * 30 + [100.0]
        result = _safe_return(prices, 30)
        assert result is None

    def test_negative_return(self):
        prices = [110.0] * 30 + [100.0]
        result = _safe_return(prices, 30)
        assert result is not None
        assert result < 0, "Expected negative return"
        assert abs(result - (-10/110)) < 1e-9


class TestRealizedVol:
    def test_constant_prices_zero_vol(self):
        # Constant price → zero returns → zero vol
        prices = [100.0] * 100
        result = _realized_vol(prices, window=60, step=30)
        assert result is not None
        assert result == 0.0 or result < 1e-10

    def test_varying_prices_nonzero_vol(self):
        # Prices that vary at step=30 boundaries: use multiples of 31 in the pattern
        # so samples at [0, 30, 60, 90, ...] are not all the same
        import math
        prices = [100.0 + 5 * math.sin(i * 0.2) for i in range(200)]
        result = _realized_vol(prices, window=120, step=30)
        assert result is not None
        assert result > 0

    def test_insufficient_data_returns_none(self):
        prices = [100.0] * 5
        result = _realized_vol(prices, window=60, step=30)
        assert result is None


class TestDownsideVol:
    def test_all_positive_returns_returns_none_or_zero(self):
        # Monotonically increasing prices → no negative returns
        prices = list(range(100, 200))
        result = _downside_vol(prices, window=60, step=30)
        # Either None (not enough negative obs) or 0
        assert result is None or result == 0.0

    def test_mixed_returns(self):
        import math
        # Prices oscillating to ensure some negative returns
        prices = [100.0 + 5 * math.sin(i * 0.5) for i in range(200)]
        result = _downside_vol(prices, window=120, step=30)
        assert result is not None
        assert result > 0


class TestRsiProxy:
    def test_trending_up_high_rsi(self):
        # Monotonically increasing → all moves up → RSI ~ 1.0
        prices = list(range(100, 460))  # 360 points
        result = _rsi_proxy(prices, window=360)
        assert result is not None
        assert result > 0.8

    def test_trending_down_low_rsi(self):
        # Monotonically decreasing → all moves down → RSI ~ 0.0
        prices = list(range(460, 100, -1))  # 360 points
        result = _rsi_proxy(prices, window=360)
        assert result is not None
        assert result < 0.2

    def test_flat_market_near_neutral(self):
        # Constant prices → no moves → RSI = 0.5
        prices = [100.0] * 361
        result = _rsi_proxy(prices, window=360)
        assert result == 0.5


class TestPercentileRank:
    def test_above_all(self):
        result = _percentile_rank(100.0, [1, 2, 3, 4, 5])
        assert result == 1.0

    def test_below_all(self):
        result = _percentile_rank(0.0, [1, 2, 3, 4, 5])
        assert result == 0.0

    def test_middle(self):
        result = _percentile_rank(3.0, [1, 2, 3, 4, 5])
        assert result is not None
        assert 0.3 < result < 0.7

    def test_empty_series(self):
        result = _percentile_rank(5.0, [])
        assert result is None


class TestSMA:
    def test_basic_sma(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _sma(prices, 5)
        assert abs(result - 3.0) < 1e-9

    def test_insufficient_data(self):
        result = _sma([1.0, 2.0], 5)
        assert result is None


class TestCrossSectional:
    def test_median_r2h(self):
        # Create features with known r_2h values
        features = {
            "A/USD": AssetFeatures(pair="A/USD", r_2h=0.05, r_6h=0.10, has_enough_data=True),
            "B/USD": AssetFeatures(pair="B/USD", r_2h=0.10, r_6h=0.15, has_enough_data=True),
            "C/USD": AssetFeatures(pair="C/USD", r_2h=0.15, r_6h=0.20, has_enough_data=True),
        }
        cs = compute_cross_sectional(features)
        assert cs.n_pairs == 3
        # Median of [0.05, 0.10, 0.15] = 0.10
        assert abs(cs.median_r2h - 0.10) < 1e-9


if __name__ == "__main__":
    # Simple test runner without pytest dependency
    import traceback

    test_classes = [
        TestSafeReturn,
        TestRealizedVol,
        TestDownsideVol,
        TestRsiProxy,
        TestPercentileRank,
        TestSMA,
        TestCrossSectional,
    ]

    passed = 0
    failed = 0
    for cls in test_classes:
        instance = cls()
        for method_name in dir(instance):
            if not method_name.startswith("test_"):
                continue
            try:
                getattr(instance, method_name)()
                print(f"  PASS: {cls.__name__}.{method_name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL: {cls.__name__}.{method_name}")
                traceback.print_exc()
                failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
