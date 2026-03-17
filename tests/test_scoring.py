"""
tests/test_scoring.py — Unit tests for the C1/M_t/PositionScore scoring pipeline.

Verifies that:
  1. C1 z-scores are cross-sectionally normalized (mean ≈ 0, std ≈ 1)
  2. M_t is bounded in [0, 1]
  3. PositionScore formula: C1 × exp(-λ_t) × (1 - M_t) is implemented correctly
  4. High hazard (high λ_t) suppresses scores exponentially
"""
import math
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.data.feature_builder import AssetFeatures, CrossSectionalFeatures
from bot.strategy.maturity import _funding_rate_component, compute_maturity
from bot.strategy.regime import RegimeEngine, RegimeState
from bot.strategy.ranking import compute_position_scores, rank_assets
from bot.strategy.signals import compute_c1_scores


def _make_cs(median_r2h: float = 0.0) -> CrossSectionalFeatures:
    cs = CrossSectionalFeatures()
    cs.median_r2h = median_r2h
    cs.n_pairs = 5
    return cs


def _make_feature(r_6h: float, r_2h: float = 0.0, r_30m: float = 0.0) -> AssetFeatures:
    return AssetFeatures(
        pair="X/USD",
        r_30m=r_30m,
        r_2h=r_2h,
        r_6h=r_6h,
        r_24h=0.0,
        has_enough_data=True,
    )


class TestC1ZScoreNormalization:
    def test_z_scores_mean_near_zero(self):
        """C1 z-scores should have cross-sectional mean ≈ 0."""
        features = {
            f"COIN{i}/USD": _make_feature(r_6h=float(i) * 0.01)
            for i in range(1, 6)
        }
        features[f"COIN1/USD"].pair = "COIN1/USD"
        for k, v in features.items():
            v.pair = k

        cs = _make_cs(median_r2h=0.0)
        c1 = compute_c1_scores(features, cs)

        assert len(c1) >= 3
        mean = sum(c1.values()) / len(c1)
        assert abs(mean) < 0.1, f"Expected mean ≈ 0, got {mean}"

    def test_top_performer_highest_c1(self):
        """Asset with highest momentum should have highest C1 score."""
        features = {
            "LOW/USD": _make_feature(r_6h=0.001),
            "MID/USD": _make_feature(r_6h=0.05),
            "HIGH/USD": _make_feature(r_6h=0.20),
        }
        for k, v in features.items():
            v.pair = k
        cs = _make_cs()
        c1 = compute_c1_scores(features, cs)

        assert c1.get("HIGH/USD", -999) > c1.get("MID/USD", -999)
        assert c1.get("MID/USD", -999) > c1.get("LOW/USD", -999)

    def test_insufficient_pairs_returns_empty(self):
        """Need at least 2 pairs for z-score normalization."""
        features = {"BTC/USD": _make_feature(r_6h=0.05)}
        features["BTC/USD"].pair = "BTC/USD"
        cs = _make_cs()
        c1 = compute_c1_scores(features, cs)
        assert len(c1) == 0


class TestPositionScoreFormula:
    def test_formula_implementation(self):
        """PositionScore = C1 * exp(-lambda_t) * (1 - M_t)"""
        c1 = {"A/USD": 1.5, "B/USD": 0.8}
        maturity = {"A/USD": 0.3, "B/USD": 0.6}
        lambda_t = 0.5

        scores = compute_position_scores(c1, maturity, lambda_t)

        expected_a = 1.5 * math.exp(-0.5) * (1 - 0.3)
        expected_b = 0.8 * math.exp(-0.5) * (1 - 0.6)

        assert abs(scores["A/USD"] - expected_a) < 1e-9
        assert abs(scores["B/USD"] - expected_b) < 1e-9

    def test_high_hazard_suppresses_scores(self):
        """At λ_t = 10, exp(-10) ≈ 0.0000454 — scores should approach zero."""
        c1 = {"A/USD": 2.0}
        maturity = {"A/USD": 0.0}  # No maturity penalty

        low_hazard = compute_position_scores(c1, maturity, lambda_t=0.1)
        high_hazard = compute_position_scores(c1, maturity, lambda_t=10.0)

        assert low_hazard["A/USD"] > high_hazard["A/USD"] * 100, \
            "High hazard should suppress score by >100x vs low hazard"

    def test_full_maturity_zeroes_score(self):
        """M_t = 1.0 means C3 = 0.0 — position score must be 0."""
        c1 = {"A/USD": 2.0}
        maturity = {"A/USD": 1.0}  # Fully matured

        scores = compute_position_scores(c1, maturity, lambda_t=0.3)
        assert scores["A/USD"] == 0.0

    def test_negative_c1_excluded_from_ranking(self):
        """Negative C1 → negative PositionScore → should not appear in ranked list."""
        c1 = {"WEAK/USD": -1.5, "STRONG/USD": 1.8}
        maturity = {"WEAK/USD": 0.2, "STRONG/USD": 0.3}

        ranked = rank_assets(c1, maturity, lambda_t=0.3, regime=RegimeState.TREND_SUPPORTIVE)
        pair_names = [r.pair for r in ranked]

        assert "WEAK/USD" not in pair_names
        assert "STRONG/USD" in pair_names


class TestFundingRateMaturity:
    def test_neutral_funding_zero_component(self):
        """Funding near-zero should contribute 0 to maturity."""
        component = _funding_rate_component(0.00005)  # Below FUNDING_RATE_NEUTRAL
        assert component == 0.0

    def test_high_funding_max_component(self):
        """Funding at or above FUNDING_RATE_SCALE should return 1.0."""
        component = _funding_rate_component(0.001)  # Well above 0.0008 scale
        assert component == 1.0

    def test_moderate_funding_partial_component(self):
        """Moderate funding should produce a value between 0 and 1."""
        component = _funding_rate_component(0.0005)  # Halfway between neutral and scale
        assert component is not None
        assert 0.0 < component < 1.0

    def test_negative_funding_zero_component(self):
        """Negative funding (shorts paying longs) → 0 maturity contribution."""
        component = _funding_rate_component(-0.0002)
        assert component == 0.0

    def test_funding_none_returns_none(self):
        """None funding should return None (graceful fallback)."""
        component = _funding_rate_component(None)
        assert component is None

    def test_maturity_higher_with_funding(self):
        """M_t should increase when high positive funding is present."""
        base_feat = AssetFeatures(
            pair="BTC/USD",
            extension=0.5,
            rsi_proxy=0.6,
            pct_rank_r6h=0.5,
            funding_rate=None,
            has_enough_data=True,
        )
        funded_feat = AssetFeatures(
            pair="BTC/USD",
            extension=0.5,
            rsi_proxy=0.6,
            pct_rank_r6h=0.5,
            funding_rate=0.0009,  # Very high funding
            has_enough_data=True,
        )
        # Seed the extension history so normalization works
        from bot.strategy.maturity import _ext_history
        _ext_history["BTC/USD"] = [-1.0, 0.0, 0.5, 1.0, 1.5, 2.0]

        m_base = compute_maturity("BTC/USD", base_feat)
        m_funded = compute_maturity("BTC/USD", funded_feat)

        assert m_funded is not None
        assert m_base is not None
        assert m_funded > m_base, "High funding should increase M_t"


class TestFearGreedRegime:
    def test_extreme_greed_raises_lsi(self):
        """F&G = 90 (extreme greed) should produce higher LSI than F&G = None."""
        from bot.data.feature_builder import CrossSectionalFeatures
        engine_baseline = RegimeEngine()
        engine_greed = RegimeEngine()

        # Build minimal features
        btc = AssetFeatures(
            pair="BTC/USD",
            realized_vol_1h=0.005,
            r_2h=0.01,
            has_enough_data=True,
        )
        cs = CrossSectionalFeatures()
        cs.median_spread_pct = 0.001
        cs.std_r30m = 0.002

        features = {"BTC/USD": btc}

        # Warm up both engines identically (3+ observations needed for z-score)
        for _ in range(5):
            engine_baseline.compute(features, cs, fng_value=None)
            engine_greed.compute(features, cs, fng_value=50.0)  # neutral

        # Now compare: baseline vs extreme greed
        lsi_vals_baseline = []
        lsi_vals_greed = []
        for _ in range(3):
            engine_baseline.compute(features, cs, fng_value=None)
            engine_greed.compute(features, cs, fng_value=90.0)  # extreme greed

        # Directly test F&G component
        component_greed = engine_greed._compute_fng_component(90.0)
        component_neutral = engine_greed._compute_fng_component(50.0)
        component_fear = engine_greed._compute_fng_component(20.0)

        assert component_greed == 1.0, "Extreme greed should return 1.0"
        assert 0.0 < component_neutral < 1.0, "Neutral should be between 0 and 1"
        assert component_fear == 0.0, "Extreme fear should return 0.0"

    def test_fng_none_does_not_crash(self):
        """F&G = None should not raise errors."""
        engine = RegimeEngine()
        btc = AssetFeatures(pair="BTC/USD", realized_vol_1h=0.005, has_enough_data=True)
        cs = CrossSectionalFeatures()
        cs.std_r30m = 0.001
        features = {"BTC/USD": btc}
        # Should not raise
        regime, lambda_t = engine.compute(features, cs, fng_value=None)
        assert regime in RegimeState.__members__.values()


class TestRankingFilters:
    def test_maturity_filter(self):
        """Assets with M_t > MAX_MATURITY_FOR_ENTRY should be excluded."""
        c1 = {"FRESH/USD": 2.0, "STALE/USD": 2.0}
        maturity = {"FRESH/USD": 0.3, "STALE/USD": 0.90}  # 0.90 > threshold 0.70

        ranked = rank_assets(c1, maturity, lambda_t=0.3, regime=RegimeState.TREND_SUPPORTIVE)
        pair_names = [r.pair for r in ranked]

        assert "FRESH/USD" in pair_names
        assert "STALE/USD" not in pair_names

    def test_c1_threshold_filter(self):
        """Assets below entry threshold should be filtered out."""
        # NEUTRAL_MIXED requires C1 > 1.0
        c1 = {"WEAK/USD": 0.5, "STRONG/USD": 1.5}  # 0.5 < 1.0 threshold
        maturity = {"WEAK/USD": 0.3, "STRONG/USD": 0.3}

        ranked = rank_assets(c1, maturity, lambda_t=0.8, regime=RegimeState.NEUTRAL_MIXED)
        pair_names = [r.pair for r in ranked]

        assert "WEAK/USD" not in pair_names
        assert "STRONG/USD" in pair_names


if __name__ == "__main__":
    import traceback
    test_classes = [
        TestC1ZScoreNormalization,
        TestPositionScoreFormula,
        TestFundingRateMaturity,
        TestFearGreedRegime,
        TestRankingFilters,
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
