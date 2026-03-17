"""
config.py — Central configuration for the crypto momentum bot.

All numeric thresholds, weights, and timings are defined here.
Each constant is annotated with the strategy concept it governs.
"""
from dataclasses import dataclass, field
from typing import Dict

# ──────────────────────────────────────────────────────────
# API
# ──────────────────────────────────────────────────────────
BASE_URL: str = "https://mock-api.roostoo.com"
RATE_LIMIT_PER_MIN: int = 30        # Hard API ceiling
TARGET_CALLS_PER_MIN: int = 5       # Normal operating budget
LOOP_INTERVAL_SECONDS: int = 60     # Main loop cadence (1 call/min for ticker)

# ──────────────────────────────────────────────────────────
# DATA / WARMUP
# ──────────────────────────────────────────────────────────
CACHE_MAXLEN: int = 300             # 300 snapshots ≈ 5 h at 1-min polling
MIN_PERIODS_FOR_FEATURES: int = 30  # Minimum snapshots to compute any feature (r_30m needs 30)

# Staged warmup thresholds (based on which return windows become available):
#   Phase 0 (<WARMUP_MIN_SAMPLES):     No trading — insufficient data.
#   Phase 1 (WARMUP_MIN_SAMPLES–WARMUP_PARTIAL_SAMPLES): Restricted mode.
#     Available: r_30m, r_24h (from Change field), cross-sectional RS.
#     r_2h and r_6h windows not yet available — C1 quality is reduced.
#   Phase 2 (WARMUP_PARTIAL_SAMPLES–WARMUP_FULL_SAMPLES): Partial mode.
#     r_2h now available; r_6h primary horizon still missing (0.35 weight).
#   Phase 3 (>=WARMUP_FULL_SAMPLES): Full mode — all signal windows available.
WARMUP_MIN_SAMPLES: int = 30        # Phase 0→1 gate (~30 min at 1-min polling)
WARMUP_PARTIAL_SAMPLES: int = 120   # Phase 1→2 gate: r_2h available (~2h)
WARMUP_FULL_SAMPLES: int = 360      # Phase 2→3 gate: r_6h available (~6h)

# Restricted mode overrides (Phase 1 and Phase 2 use tighter parameters)
WARMUP_PHASE1_MAX_POSITIONS: int = 2
WARMUP_PHASE1_GROSS_CAP: float = 0.30
WARMUP_PHASE1_C1_THRESHOLD: float = 1.50  # Higher bar during thin-signal phase

WARMUP_PHASE2_MAX_POSITIONS: int = 3
WARMUP_PHASE2_GROSS_CAP: float = 0.50
WARMUP_PHASE2_C1_THRESHOLD: float = 1.20

# ──────────────────────────────────────────────────────────
# C1 Raw Composite Weights (used internally in signals.py)
# raw_i = w1*r_30m + w2*r_2h + w3*r_6h + w4*r_24h + w5*(r_2h - median_r2h)
# This raw composite is NEGATED in the promoted signal (H1 reversal component).
# ──────────────────────────────────────────────────────────
C1_WEIGHT_R30M: float = 0.10        # 30m return (noisy at 1-min sampling)
C1_WEIGHT_R2H: float = 0.20         # 2h return
C1_WEIGHT_R6H: float = 0.35         # 6h return (primary horizon for 10-day window)
C1_WEIGHT_R24H: float = 0.25        # 24h return (uses ticker Change field directly)
C1_WEIGHT_CS_RS: float = 0.10       # Cross-sectional relative strength (vs median)

# ──────────────────────────────────────────────────────────
# Promoted Signal — GP-selected combination (Phase 3 of research pipeline)
# Formula: 0.7 × CS_z(−C1_raw) + 0.3 × CS_z(−realized_vol_6h)
# Validated in: research/03_validation/, research/04_gp_search/
# Economic description: "buy cross-sectional laggards with low realized volatility"
# IC at 4h horizon: train +0.047 (t=7.2), holdout +0.066 (t=10.6)
# ──────────────────────────────────────────────────────────
ALPHA_WEIGHT_REVERSAL: float = 0.70  # H1 anti-momentum: selects recent cross-sect. laggards
ALPHA_WEIGHT_STABILITY: float = 0.30 # H5 low-vol anomaly: selects stable low-vol coins

# ──────────────────────────────────────────────────────────
# Maturity M_t — Diffusion maturity per asset (C3 = 1 − M_t)
# M_t ∈ [0,1]: 0 = freshest entry, 1 = fully diffused / overextended
# Composed of: extension from SMA, RSI proxy, percentile rank
# ──────────────────────────────────────────────────────────
MT_WEIGHT_EXTENSION: float = 0.40   # Distance from 12h SMA (normalized by ATR) — primary overextension measure
MT_WEIGHT_RSI_PROXY: float = 0.15   # Avg-up / (avg-up + avg-dn) over 6h
MT_WEIGHT_PCT_RANK: float = 0.25    # r_6h percentile vs 48h window
MT_WEIGHT_FUNDING: float = 0.20     # Binance perp funding rate — crowded positioning proxy
MT_LOOKBACK_PERIODS: int = 48       # 48h of 1-min snapshots for percentile rank

# Funding rate normalization for M_t component
FUNDING_RATE_NEUTRAL: float = 0.0001    # 0.01%/8h — typical neutral; below this: no maturity signal
FUNDING_RATE_SCALE: float = 0.0008      # 0.08%/8h — at this level funding component reaches 1.0
FUNDING_RATE_REFRESH_LOOPS: int = 10    # Re-fetch every 10 loops (~10 min); funding changes every 8h

# ──────────────────────────────────────────────────────────
# Regime State Vector (B-layer / Regime Inference)
# LSI dominates all others — see STRATEGY.md dominance cascade.
# ──────────────────────────────────────────────────────────

# LSI — Liquidity Stress Index (HIGHEST dominance)
# Proxy from: BTC realized vol z-score, bid-ask spread z-score, dispersion collapse,
#             Crypto Fear & Greed Index (sentiment leading indicator from Alternative.me)
LSI_WEIGHT_BTC_VOL: float = 0.45
LSI_WEIGHT_SPREAD: float = 0.25
LSI_WEIGHT_DISP: float = 0.15
LSI_WEIGHT_FNG: float = 0.15        # Fear & Greed Index — extreme greed → leading stress signal

# Fear & Greed fetch cadence
FNG_REFRESH_HOURS: float = 24.0     # Refresh at most once per day (index updates daily)
LSI_LOOKBACK_PERIODS: int = 48      # 48h rolling window for LSI z-scores
LSI_THRESHOLD_DEFENSIVE: float = 0.60   # LSI > 0.60 → HAZARD_DEFENSIVE, λ_t = 4.0
LSI_THRESHOLD_EMERGENCY: float = 0.80   # LSI > 0.80 → HAZARD_DEFENSIVE, λ_t = 10.0
LSI_THRESHOLD_CAUTION: float = 0.40     # LSI > 0.40 → force NEUTRAL_MIXED

# MPI — Market Posture Index (trend vs chop)
# Proxy from: BTC trend strength, cross-section vol inverted
MPI_WEIGHT_BTC_TREND: float = 0.60
MPI_WEIGHT_CS_VOL_INV: float = 0.40
MPI_THRESHOLD_CHOP: float = 0.30        # MPI < 0.30 → force NEUTRAL_MIXED

# FEI — Flow Elasticity Index (momentum concentration)
# Proxy from: top quartile minus bottom quartile 6h return spread
FEI_THRESHOLD_HIGH: float = 0.55        # FEI > 0.55 → helps qualify TREND_SUPPORTIVE

# ──────────────────────────────────────────────────────────
# Regime → Parameter Mapping
# ──────────────────────────────────────────────────────────
REGIME_PARAMS: Dict[str, dict] = {
    "TREND_SUPPORTIVE": {
        "max_positions": 5,
        "gross_cap": 0.85,          # Deploy 85% of NAV
        "entry_c1_threshold": 0.60,  # C1 z-score must exceed 0.60 — allows earlier entries in confirmed trends
        "lambda_t": 0.30,
    },
    "NEUTRAL_MIXED": {
        "max_positions": 3,
        "gross_cap": 0.65,
        "entry_c1_threshold": 1.00,  # Tighter: top ~15%
        "lambda_t": 0.80,
    },
    "HAZARD_DEFENSIVE": {
        "max_positions": 0,
        "gross_cap": 0.00,
        "entry_c1_threshold": float("inf"),  # No entries
        "lambda_t": 4.00,
    },
}

# ──────────────────────────────────────────────────────────
# Entry / Exit Filters
# ──────────────────────────────────────────────────────────
MAX_MATURITY_FOR_ENTRY: float = 0.72    # Entry blocked if M_t > 0.72 (slightly more permissive; avoids blocking strong trends)
EXIT_C1_THRESHOLD: float = 0.20         # Exit if C1 z-score falls below 0.20

# ──────────────────────────────────────────────────────────
# Position Sizing (Quarter-Kelly targeting Sortino maximization)
# ──────────────────────────────────────────────────────────
KELLY_FRACTION: float = 0.25            # Quarter-Kelly for overconfidence control
MIN_POSITION_WEIGHT: float = 0.05       # Minimum 5% NAV per position
MAX_POSITION_WEIGHT: float = 0.30       # Maximum 30% NAV per position (concentration cap)

# ──────────────────────────────────────────────────────────
# Risk Management
# (Designed to maximize Sortino by being binary: full on / full off)
# ──────────────────────────────────────────────────────────

# Portfolio drawdown levels (from NAV peak)
DRAWDOWN_CAUTION: float = -0.05         # Level 1: −5% → reduce positions
DRAWDOWN_DEFENSIVE: float = -0.08       # Level 2: −8% → min positions
DRAWDOWN_KILL: float = -0.12            # Level 3: −12% → emergency exit all
DRAWDOWN_RECOVERY_GATE: float = -0.08   # No new trades until drawdown < -8%

# Per-position stops
STOP_LOSS_PCT: float = -0.04            # Hard stop: −4% from entry (market order)
TRAILING_STOP_ACTIVATION: float = 0.03  # Trailing stop activates after +3% gain
TRAILING_STOP_TRAIL_PCT: float = 0.025  # Trail at 2.5% from rolling high
MAX_HOLD_HOURS: float = 72.0            # Force exit after 72h regardless of score

# Trade timing constraints (Sortino protection via fee-drag prevention)
MIN_HOLD_SECONDS: int = 4 * 3600        # 4-hour minimum holding period
REENTRY_LOCKOUT_SECONDS: int = 2 * 3600 # 2-hour re-entry lockout after exit

# BTC direct gates (independent of LSI; catches fast BTC crashes)
BTC_BLOCK_NEW_ENTRIES_RETURN: float = -0.03     # BTC 2h return < -3%: block all new longs
BTC_EMERGENCY_EXIT_RETURN: float = -0.06         # BTC 2h return < -6%: emergency exit all

# ──────────────────────────────────────────────────────────
# Execution
# ──────────────────────────────────────────────────────────
LIMIT_PRICE_AGGRESSION: float = 0.20    # Place limit at mid ± 20% of spread (aggressive passive)
ORDER_TIMEOUT_ENTRY_SECONDS: int = 180  # Cancel unfilled entry after 3 minutes
ORDER_TIMEOUT_EXIT_SECONDS: int = 300   # Cancel unfilled exit after 5 minutes

# API polling cadences (to stay within rate budget)
BALANCE_POLL_EVERY_N_LOOPS: int = 5     # Poll balance every 5 loops (5 min)
PENDING_POLL_EVERY_N_LOOPS: int = 3     # Poll pending_count every 3 loops (3 min)
