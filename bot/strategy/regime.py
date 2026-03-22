"""
bot/strategy/regime.py — Market regime inference: converts market signals into hazard rate λ_t.

λ_t exponentially scales all position scores — near-zero under stress:
  PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)
  λ=0.3 → exp(−0.3)=74% retained (trend)  |  λ=4.0 → exp(−4)=2% retained (defensive)

Three indices drive the regime state:

  LSI_t — Liquidity Stress Index   [HIGHEST DOMINANCE — overrides all others]
    Components: BTC realized vol z-score (45%) + bid-ask spread z-score (25%)
                + cross-section dispersion collapse (15%) + Fear & Greed (15%)
    "Realized vol z-score": how many σ above the recent vol baseline BTC's hourly vol is.
    "Dispersion collapse": when all assets move together (low cross-sectional std of returns),
    it signals panic — correlated selloffs where diversification and reversal signals break down.
    When LSI elevated: de-gross immediately, no new entries.

  MPI_t — Market Posture Index
    Proxy: |r_BTC,2h| / realized_vol_BTC — ratio of BTC's directional move to its own
    typical volatility over 2h. High MPI = BTC trending cleanly. Low MPI = BTC choppy,
    directional signal noise, position count reduced.

  FEI_t — Flow Elasticity Index
    Proxy: top-quartile minus bottom-quartile of cross-section 6h returns.
    High spread = clear momentum leaders exist, concentrated capital flows are present.
    Low spread = all assets moving together, momentum differentiation unreliable.

Dominance cascade: LSI > MPI > FEI  (LSI overrides all — see docs/STRATEGY.md)
Output: (RegimeState, lambda_t) — λ_t passed directly into the scoring formula.
"""
import logging
import math
from collections import deque
from enum import Enum
from typing import Deque, Dict, Optional, Tuple

import config
from bot.data.feature_builder import AssetFeatures, CrossSectionalFeatures

logger = logging.getLogger(__name__)


class RegimeState(Enum):
    """
    Three-state regime classification using LSI/MPI/FEI dominance cascade.
    State drives maximum positions, gross exposure cap, and entry thresholds.
    """
    TREND_SUPPORTIVE = "TREND_SUPPORTIVE"
    NEUTRAL_MIXED = "NEUTRAL_MIXED"
    HAZARD_DEFENSIVE = "HAZARD_DEFENSIVE"


# ── Rolling stats buffer for z-score computation ─────────────────────────────

class RollingStats:
    """Maintains a rolling mean and std for z-score normalization."""

    def __init__(self, maxlen: int = 48) -> None:
        self._buf: Deque[float] = deque(maxlen=maxlen)

    def add(self, value: float) -> None:
        self._buf.append(value)

    def z_score(self, value: float) -> float:
        """Z-score of value relative to buffer. Returns 0 if < 3 observations."""
        n = len(self._buf)
        if n < 3:
            return 0.0
        mean = sum(self._buf) / n
        var = sum((x - mean) ** 2 for x in self._buf) / n
        std = math.sqrt(var) if var > 0 else 1e-8
        return (value - mean) / std

    def min_max_norm(self, value: float) -> float:
        """Min-max normalize value to [0, 1] relative to buffer."""
        if len(self._buf) < 2:
            return 0.5
        lo, hi = min(self._buf), max(self._buf)
        if hi <= lo:
            return 0.5
        return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _norm_to_01(z: float, clip_at: float = 3.0) -> float:
    """Map a z-score to [0, 1] by clipping at ±clip_at and rescaling."""
    clamped = max(-clip_at, min(clip_at, z))
    return (clamped + clip_at) / (2 * clip_at)


# ── Regime Engine ──────────────────────────────────────────────────────────────

class RegimeEngine:
    """
    Computes the market regime state vector from feature data.

    State is accumulated across loop cycles (rolling z-score buffers).
    Instantiate once; call compute() on each loop.
    """

    def __init__(self, lookback: int = config.LSI_LOOKBACK_PERIODS) -> None:
        # LSI rolling buffers
        self._btc_vol_stats = RollingStats(lookback)
        self._spread_stats = RollingStats(lookback)
        self._dispersion_stats = RollingStats(lookback)

        # MPI rolling buffer
        self._btc_trend_stats = RollingStats(lookback)
        self._cs_vol_stats = RollingStats(lookback)

        # FEI rolling buffer
        self._momentum_spread_stats = RollingStats(lookback)

        self._last_regime: RegimeState = RegimeState.NEUTRAL_MIXED
        self._last_lambda: float = config.REGIME_PARAMS["NEUTRAL_MIXED"]["lambda_t"]
        self._last_btc_vol_z: float = 0.0

    # ── Index computation ──────────────────────────────────────────────────────

    def _compute_fng_component(self, fng_value: Optional[float]) -> Optional[float]:
        """
        Normalize Fear & Greed Index to a [0, 1] LSI stress component.

        Extreme Greed (>75) signals euphoric positioning overextension:
        historically precedes corrections as leveraged longs unwind.
        This is a leading indicator for the LSI — it can raise the stress
        signal before price-based measures (vol, spread) react.

        Extreme Fear (<25) → 0.0 (fear is capitulation, not a new stress event)
        Neutral (25–75)    → linear interpolation
        None               → omit from LSI (graceful fallback)
        """
        if fng_value is None:
            return None
        if fng_value >= 75.0:
            return 1.0
        if fng_value <= 25.0:
            return 0.0
        return (fng_value - 25.0) / 50.0

    def _compute_lsi(
        self,
        btc_features: Optional[AssetFeatures],
        cs: CrossSectionalFeatures,
        fng_value: Optional[float] = None,
    ) -> float:
        """
        LSI_t ∈ [0, 1]. High LSI = stressed market.

        Components:
          - BTC realized vol z-score (vol spike → stress)
          - Median spread z-score (illiquidity → stress)
          - Cross-section dispersion collapse (all moving together → panic)
          - Fear & Greed Index sentiment (extreme greed → leading stress signal)

        Weights are normalized by the sum of contributing components,
        so LSI remains well-defined when F&G data is unavailable.
        """
        lsi_raw = 0.0
        weight_used = 0.0

        # Component 1: BTC vol z-score
        if btc_features and btc_features.realized_vol_1h is not None:
            self._btc_vol_stats.add(btc_features.realized_vol_1h)
            vol_z = self._btc_vol_stats.z_score(btc_features.realized_vol_1h)
            self._last_btc_vol_z = vol_z
            lsi_raw += config.LSI_WEIGHT_BTC_VOL * _norm_to_01(vol_z)
            weight_used += config.LSI_WEIGHT_BTC_VOL

        # Component 2: Bid-ask spread z-score (illiquidity)
        if cs.median_spread_pct > 0:
            self._spread_stats.add(cs.median_spread_pct)
            spread_z = self._spread_stats.z_score(cs.median_spread_pct)
            lsi_raw += config.LSI_WEIGHT_SPREAD * _norm_to_01(spread_z)
            weight_used += config.LSI_WEIGHT_SPREAD

        # Component 3: Cross-sectional dispersion collapse
        # (Low dispersion = panic / correlated selloff)
        if cs.std_r30m > 0:
            self._dispersion_stats.add(cs.std_r30m)
            # Invert: low dispersion = high stress
            disp_z = -self._dispersion_stats.z_score(cs.std_r30m)
            lsi_raw += config.LSI_WEIGHT_DISP * _norm_to_01(disp_z)
            weight_used += config.LSI_WEIGHT_DISP

        # Component 4: Fear & Greed sentiment (leading indicator)
        fng_component = self._compute_fng_component(fng_value)
        if fng_component is not None:
            lsi_raw += config.LSI_WEIGHT_FNG * fng_component
            weight_used += config.LSI_WEIGHT_FNG

        if weight_used == 0:
            return 0.3  # Default to mild stress when no data
        return lsi_raw / weight_used

    def _compute_mpi(
        self,
        btc_features: Optional[AssetFeatures],
        cs: CrossSectionalFeatures,
    ) -> float:
        """
        MPI_t ∈ [0, 1]. High MPI = strong trend environment.

        Components:
          - BTC trend strength: |r_2h_btc| / realized_vol_btc_2h
          - Cross-section vol inverted (low vol → trending)
        """
        mpi_raw = 0.0
        weight_used = 0.0

        # Component 1: BTC trend strength
        if btc_features and btc_features.r_2h is not None and btc_features.realized_vol_1h:
            trend_strength = abs(btc_features.r_2h) / (btc_features.realized_vol_1h + 1e-8)
            self._btc_trend_stats.add(trend_strength)
            mpi_raw += config.MPI_WEIGHT_BTC_TREND * self._btc_trend_stats.min_max_norm(trend_strength)
            weight_used += config.MPI_WEIGHT_BTC_TREND

        # Component 2: Cross-section vol inverted
        if cs.std_r30m > 0:
            self._cs_vol_stats.add(cs.std_r30m)
            # Low cross-section vol = trending (higher MPI)
            cs_vol_norm = 1.0 - self._cs_vol_stats.min_max_norm(cs.std_r30m)
            mpi_raw += config.MPI_WEIGHT_CS_VOL_INV * cs_vol_norm
            weight_used += config.MPI_WEIGHT_CS_VOL_INV

        if weight_used == 0:
            return 0.5
        return mpi_raw / weight_used

    def _compute_fei(
        self,
        asset_features: Dict[str, AssetFeatures],
        c1_scores: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        FEI_t ∈ [0, 1]. High FEI = clear momentum leaders, concentrated flow.

        Computed as: spread between top-quartile and bottom-quartile 6h returns.
        """
        r6h_vals = [
            (pair, f.r_6h)
            for pair, f in asset_features.items()
            if f.r_6h is not None
        ]
        if len(r6h_vals) < 4:
            return 0.5

        r6h_vals.sort(key=lambda x: x[1])  # type: ignore[arg-type]
        n = len(r6h_vals)
        q25 = n // 4
        q75 = (3 * n) // 4

        bottom_q = [v for _, v in r6h_vals[:q25]]
        top_q = [v for _, v in r6h_vals[q75:]]

        if not bottom_q or not top_q:
            return 0.5

        spread = sum(top_q) / len(top_q) - sum(bottom_q) / len(bottom_q)
        self._momentum_spread_stats.add(spread)
        return self._momentum_spread_stats.min_max_norm(spread)

    # ── Dominance cascade ──────────────────────────────────────────────────────

    def compute(
        self,
        asset_features: Dict[str, AssetFeatures],
        cs: CrossSectionalFeatures,
        btc_pair: str = "BTC/USD",
        fng_value: Optional[float] = None,
    ) -> Tuple[RegimeState, float]:
        """
        Run the full regime computation and return (RegimeState, lambda_t).

        Dominance hierarchy:
          LSI > MPI > FEI  (LSI overrides all others — see STRATEGY.md)

        Args:
            asset_features: Per-asset features dict from feature_builder.
            cs:             Cross-sectional features.
            btc_pair:       Symbol to use as BTC proxy.
            fng_value:      Optional Fear & Greed Index value (0–100).
                            When provided, incorporated into LSI as leading stress signal.

        Returns:
            (RegimeState, lambda_t) tuple.
        """
        btc_features = asset_features.get(btc_pair)

        lsi = self._compute_lsi(btc_features, cs, fng_value)
        mpi = self._compute_mpi(btc_features, cs)
        fei = self._compute_fei(asset_features)

        logger.debug(
            "Regime indices — LSI=%.3f MPI=%.3f FEI=%.3f F&G=%s",
            lsi, mpi, fei,
            f"{fng_value:.0f}" if fng_value is not None else "N/A",
        )

        # ── Dominance cascade ──────────────────────────────────────────────
        # LSI: HIGHEST dominance. When liquidity stress is elevated, go defensive immediately.
        if lsi > config.LSI_THRESHOLD_EMERGENCY:
            state = RegimeState.HAZARD_DEFENSIVE
            lambda_t = config.LAMBDA_HAZARD_EMERGENCY
        elif lsi > config.LSI_THRESHOLD_DEFENSIVE:
            state = RegimeState.HAZARD_DEFENSIVE
            lambda_t = config.REGIME_PARAMS["HAZARD_DEFENSIVE"]["lambda_t"]
        elif lsi > config.LSI_THRESHOLD_CAUTION or mpi < config.MPI_THRESHOLD_CHOP:
            state = RegimeState.NEUTRAL_MIXED
            lambda_t = config.LAMBDA_NEUTRAL_CAUTION
        elif fei > config.FEI_THRESHOLD_HIGH and mpi > 0.50:
            state = RegimeState.TREND_SUPPORTIVE
            lambda_t = config.REGIME_PARAMS["TREND_SUPPORTIVE"]["lambda_t"]
        else:
            state = RegimeState.NEUTRAL_MIXED
            lambda_t = config.REGIME_PARAMS["NEUTRAL_MIXED"]["lambda_t"]

        if state != self._last_regime:
            logger.info(
                "REGIME CHANGE: %s → %s (LSI=%.3f MPI=%.3f FEI=%.3f λ=%.2f)",
                self._last_regime.value, state.value, lsi, mpi, fei, lambda_t,
            )

        self._last_regime = state
        self._last_lambda = lambda_t

        return state, lambda_t

    @property
    def last_regime(self) -> RegimeState:
        return self._last_regime

    @property
    def last_lambda(self) -> float:
        return self._last_lambda

    @property
    def last_btc_vol_z(self) -> float:
        """Last computed BTC vol z-score (from LSI Component 1). Used for continuous H2C allocation."""
        return self._last_btc_vol_z
