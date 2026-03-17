"""
tests/test_precision.py — Unit tests for order precision and validation.

Tests that floor_to_precision and validate_order_params correctly handle
precision requirements and minimum order checks.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.data.roostoo_client import floor_to_precision, validate_order_params


class TestFloorToPrecision:
    def test_floor_not_round(self):
        # 1.999 with precision 2 → 1.99 (floor), NOT 2.00 (round)
        result = floor_to_precision(1.999, 2)
        assert abs(result - 1.99) < 1e-9, f"Expected 1.99, got {result}"

    def test_zero_precision(self):
        result = floor_to_precision(5.7, 0)
        assert result == 5.0

    def test_high_precision(self):
        result = floor_to_precision(0.123456789, 6)
        assert abs(result - 0.123456) < 1e-9

    def test_already_exact(self):
        result = floor_to_precision(1.50, 2)
        assert abs(result - 1.50) < 1e-9

    def test_very_small(self):
        result = floor_to_precision(0.00001234, 6)
        assert abs(result - 0.000012) < 1e-9


class TestValidateOrderParams:
    def _make_exchange_info(
        self,
        pair: str = "BTC/USD",
        amount_precision: int = 5,
        price_precision: int = 2,
        mini_order: float = 10.0,
    ) -> dict:
        return {
            "TradePairs": {
                pair: {
                    "AmountPrecision": amount_precision,
                    "PricePrecision": price_precision,
                    "MiniOrder": mini_order,
                }
            }
        }

    def test_valid_order(self):
        exchange_info = self._make_exchange_info()
        result, error = validate_order_params("BTC/USD", 0.001, 50000.0, exchange_info)
        assert error is None
        assert result is not None
        qty, price = result
        assert qty > 0
        assert price > 0

    def test_below_minimum_order(self):
        # qty=0.00001, price=1.0 → notional=0.00001 < MiniOrder=10
        exchange_info = self._make_exchange_info(mini_order=10.0)
        result, error = validate_order_params("BTC/USD", 0.00001, 1.0, exchange_info)
        assert result is None
        assert error is not None
        assert "MiniOrder" in error or "minimum" in error.lower() or "Notional" in error

    def test_pair_not_in_exchange_info(self):
        exchange_info = self._make_exchange_info("BTC/USD")
        result, error = validate_order_params("XYZ/USD", 1.0, 100.0, exchange_info)
        assert result is None
        assert error is not None

    def test_precision_applied(self):
        # Amount precision 2 → 0.12345 should floor to 0.12
        exchange_info = self._make_exchange_info(amount_precision=2, mini_order=1.0)
        result, error = validate_order_params("BTC/USD", 0.12999, 100.0, exchange_info)
        assert error is None
        qty, _ = result  # type: ignore
        assert abs(qty - 0.12) < 1e-9

    def test_zero_adjusted_quantity(self):
        # Very small qty, low precision → floors to 0 → error
        exchange_info = self._make_exchange_info(amount_precision=0, mini_order=1.0)
        result, error = validate_order_params("BTC/USD", 0.001, 100.0, exchange_info)
        assert result is None


if __name__ == "__main__":
    import traceback
    test_classes = [TestFloorToPrecision, TestValidateOrderParams]
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
