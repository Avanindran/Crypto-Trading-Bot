"""
bot/strategy/h2_signals.py — H2C BTC-Diffusion Engine.

Signal formula:
    H2C_score_i = CS_z(β_i × r_BTC,2h − r_i,2h)

Where β_i is the rolling 48h OLS slope of r_i on r_BTC (hourly returns).
A positive gap (β_i × r_BTC > r_i) means the asset undershot relative to
BTC's move and is expected to catch up — i.e., the diffusion window is open.

Validated standalone: ret=+74.0%, Sortino=1.99, Calmar=20.25 (backtest 2026-03-18)
IC = +0.042 @ 1h, t = +9.85 (signal_search.py, promoted)

Deployed as disabled by default (H2C_ALPHA_TREND = 0.0 in config). Raise alpha
to 1.0 to run H2C standalone, or to an intermediate value to blend with H1.
"""
import logging
import math
from typing import Dict, List, Optional

import config
from bot.data.feature_builder import AssetFeatures
from bot.data.market_cache import MarketCache

logger = logging.getLogger(__name__)


# ── OLS helper ─────────────────────────────────────────────────────────────────

def _ols_beta(r_i: List[float], r_btc: List[float]) -> float:
    """Rolling OLS slope β = Cov(r_i, r_btc) / Var(r_btc).

    Returns 0 if variance is too small (BTC flat period).
    """
    n = len(r_i)
    if n < 2:
        return 0.0
    mi = sum(r_i) / n
    mb = sum(r_btc) / n
    cov = sum((r_i[j] - mi) * (r_btc[j] - mb) for j in range(n)) / n
    var = sum((r_btc[j] - mb) ** 2 for j in range(n)) / n
    return cov / var if var > 1e-10 else 0.0


# ── CS z-score normalization ───────────────────────────────────────────────────

def _cs_z(scores: Dict[str, float]) -> Dict[str, float]:
    """Cross-sectional z-score normalization."""
    vals = list(scores.values())
    mean = sum(vals) / len(vals)
    var  = sum((v - mean) ** 2 for v in vals) / len(vals)
    std  = math.sqrt(var) if var > 1e-8 else 1e-8
    return {pair: (s - mean) / std for pair, s in scores.items()}


# ── BetaHistoryManager ─────────────────────────────────────────────────────────

class BetaHistoryManager:
    """Rolling 48h OLS beta history for H2C signal computation.

    Maintains per-asset history of (r_i, r_BTC) hourly returns.
    Updates at 1h cadence regardless of loop frequency.
    Persists across bot restarts via state.json.

    During the first H2C_BETA_MIN_OBS hours after startup (or after
    a state miss), H2C returns None — H1 operates normally. This is
    the safe burn-in behaviour specified in the integration spec.
    """

    def __init__(
        self,
        pairs: List[str],
        btc_key: str,
        window: int = config.H2C_BETA_WINDOW,
    ) -> None:
        self._btc_key = btc_key
        self._window  = window
        self._last_update_ms: int = 0
        # pair → {"r_i": List[float], "r_btc": List[float]}
        self._hist: Dict[str, Dict[str, List[float]]] = {
            p: {"r_i": [], "r_btc": []}
            for p in pairs
            if p != btc_key
        }

    def update(self, cache: MarketCache, ts_ms: int) -> None:
        """Append 1h returns for all pairs if ≥1h has elapsed since last update.

        Uses wall-clock time (ts_ms) to determine cadence — independent of
        how many loop iterations have occurred.

        Requires 61 snapshots (~61 min of cache history) to compute 1h returns.
        Silently skips pairs with insufficient cache history.
        """
        if ts_ms - self._last_update_ms < 3_600_000:
            return  # < 1h since last update

        btc_prices = cache.prices(self._btc_key, 61)
        if len(btc_prices) < 61:
            return  # Not enough BTC history for 1h return

        r_btc = btc_prices[-1] / btc_prices[0] - 1.0

        updated = 0
        for pair, hist in self._hist.items():
            pp = cache.prices(pair, 61)
            if len(pp) >= 61:
                r_i = pp[-1] / pp[0] - 1.0
                hist["r_i"]   = (hist["r_i"]   + [r_i])  [-self._window:]
                hist["r_btc"] = (hist["r_btc"] + [r_btc])[-self._window:]
                updated += 1

        self._last_update_ms = ts_ms
        logger.debug("H2C beta history updated: %d pairs (max obs=%d)",
                     updated,
                     max((len(h["r_i"]) for h in self._hist.values()), default=0))

    def min_observations(self) -> int:
        """Minimum observation count across all tracked pairs."""
        if not self._hist:
            return 0
        return min(len(h["r_i"]) for h in self._hist.values())

    def to_dict(self) -> dict:
        """Serialize for state.json persistence."""
        return {
            "hist":           self._hist,
            "last_update_ms": self._last_update_ms,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        pairs: List[str],
        btc_key: str,
    ) -> "BetaHistoryManager":
        """Deserialize from state.json. Merges saved history into fresh manager.

        Unknown pairs in saved data are silently ignored.
        Missing pairs (new assets added since last save) start with empty history.
        """
        obj = cls(pairs, btc_key)
        saved_hist = data.get("hist", {})
        for pair in obj._hist:
            if pair in saved_hist:
                obj._hist[pair] = {
                    "r_i":   list(saved_hist[pair].get("r_i",   []))[-obj._window:],
                    "r_btc": list(saved_hist[pair].get("r_btc", []))[-obj._window:],
                }
        obj._last_update_ms = int(data.get("last_update_ms", 0))
        return obj


# ── H2C signal computation ─────────────────────────────────────────────────────

def compute_h2c_scores(
    asset_features: Dict[str, AssetFeatures],
    beta_manager: BetaHistoryManager,
    btc_r2h: Optional[float],
) -> Optional[Dict[str, float]]:
    """Compute H2C cross-sectional gap scores: CS_z(β_i × r_BTC,2h − r_i,2h).

    H2C mechanism: when BTC makes a directional move, secondary assets should
    reprice proportionally to their BTC beta (β_i × r_BTC). Assets that have
    not yet done so (positive gap) are in the diffusion window and expected to
    catch up within ~6h.

    Returns None if:
    - BTC 2h return is unavailable
    - Fewer than 4 pairs have ≥ H2C_BETA_MIN_OBS observations (24h burn-in)

    Note: H2C_VOL_Z_THRESH gate is intentionally omitted — the backtest B-sweep
    found all z-threshold levels produce equivalent performance (no discriminatory
    power). The regime LSI already gates entries when BTC vol is high (45% weight).
    Config parameter is retained for future tuning if needed.

    Args:
        asset_features: Per-asset features from feature_builder (for r_2h).
        beta_manager:   Rolling beta history manager.
        btc_r2h:        BTC 2h return (None if unavailable).

    Returns:
        Dict[pair, h2c_z_score] or None.
    """
    if btc_r2h is None:
        return None

    gaps: Dict[str, float] = {}
    for pair, hist in beta_manager._hist.items():
        if len(hist["r_i"]) < config.H2C_BETA_MIN_OBS:
            continue  # burn-in period — beta estimate unreliable

        feat = asset_features.get(pair)
        if feat is None or feat.r_2h is None:
            continue

        beta = _ols_beta(hist["r_i"], hist["r_btc"])
        gap  = beta * btc_r2h - feat.r_2h
        gaps[pair] = gap

    if len(gaps) < 4:
        logger.debug("H2C: only %d pairs with sufficient beta history — returning None", len(gaps))
        return None

    scores = _cs_z(gaps)
    logger.debug("H2C scores computed for %d pairs — top=%s",
                 len(scores),
                 sorted(scores.items(), key=lambda x: -x[1])[:3])
    return scores
