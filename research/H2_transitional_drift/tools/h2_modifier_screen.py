"""
research/h2_modifier_screen.py — H2C-specific C2 hazard + C3 maturity screens.

Tests H2-specific modifiers that gate the H2C BTC-diffusion signal.

C2 proxies tested (2):
  HAZ2_BTC_VOL_Z     BTC 6h realized-vol z-score > 1.50 → block H2 entries
  HAZ2_CORR_COLLAPSE Rolling 48h median BTC-alt Pearson correlation < 0.40

C3 proxies tested (2):
  MAT2_GAP_REMAINING |r_i,2h| / |β_i × r_BTC,2h| gap closure fraction
  MAT2_TIME_DECAY    (t − t_peak_BTC) / 6h time since BTC's peak 1h move

Economic justification:
  C2 — gates entries when the BTC-diffusion mechanism is invalid (BTC vol spike
       → BTC likely reverses within diffusion window; correlation collapse →
       alt-season: β_i × r_BTC doesn't predict alt movements).
  C3 — gates entries when the diffusion opportunity has already propagated
       (gap nearly closed, or BTC's move was too long ago).

Approval criteria:
  C2: MaxDD relative improvement ≥ 10% AND worst 30d DD improvement ≥ 5pp
  C3: IC(H2C | proxy ≤ fresh_threshold) > IC(H2C | unconditional)

Run:
  python -X utf8 research/H2_transitional_drift/tools/h2_modifier_screen.py

Outputs (co-located with H2 mechanism):
  H2_transitional_drift/01_Proxies/Hazard_C2/HAZ2_BTC_VOL_Z/02_modifier_screen.md
  H2_transitional_drift/01_Proxies/Hazard_C2/HAZ2_CORR_COLLAPSE/02_modifier_screen.md
  H2_transitional_drift/01_Proxies/Maturity_C3/MAT2_GAP_REMAINING/02_modifier_screen.md
  H2_transitional_drift/01_Proxies/Maturity_C3/MAT2_TIME_DECAY/02_modifier_screen.md
  H2_transitional_drift/02_Candidates/Signal/03_modifier_results.md
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, List, Optional, Tuple

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.join(_here, '..', '..')  # research/ root
sys.path.insert(0, _root)

from ic_validation_extended import (  # noqa: E402
    load_klines_all_parallel,
    compute_return,
    compute_forward_return,
    cross_sectional_z,
    spearman_ic,
    fetch_roostoo_pairs,
    _month_range,
    TRENDING_START,
    TRENDING_END,
)

# ── Output paths ───────────────────────────────────────────────────────────────

H2_PROXIES_DIR = os.path.join(_root, "H2_transitional_drift", "01_Proxies")
H2_C2_DIR      = os.path.join(H2_PROXIES_DIR, "Hazard_C2")
H2_C3_DIR      = os.path.join(H2_PROXIES_DIR, "Maturity_C3")
H2_SIGNAL_DIR  = os.path.join(_root, "H2_transitional_drift", "02_Candidates", "Signal")
CHARTS_DIR     = os.path.join(
    _root, "H2_transitional_drift", "02_Candidates", "Strategy", "charts", "modifier_screens"
)

for _d in (H2_C2_DIR, H2_C3_DIR, H2_SIGNAL_DIR, CHARTS_DIR):
    os.makedirs(_d, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────

HOLD_HOURS   = 4      # rebalance cadence (must match vector_tests.py)
TOP_N        = 3      # long-only equal weight
LOOKBACK     = 48     # rolling window (hours) for vol z-score and beta
CORR_LOOKBACK = 48    # hours of 1h returns for correlation computation
PERIOD_DAYS  = 30     # for worst-period drawdown

MS_PER_HOUR  = 3_600_000
MS_PER_DAY   = 86_400_000

# C2 gate thresholds
HAZ2_VOL_Z_THRESH  = 1.50   # BTC 6h vol z-score gate
HAZ2_CORR_THRESH   = 0.40   # median BTC-alt correlation gate

# C3 proxy thresholds
MAT2_GAP_FRESH  = 0.30   # gap_closure < 0.30 → fresh (>70% of gap still open)
MAT2_GAP_STALE  = 0.80   # gap_closure > 0.80 → stale (>80% of gap closed)
MAT2_TIME_FRESH = 0.40   # time_decay < 0.40 → fresh (BTC moved < 2.4h ago)
MAT2_TIME_STALE = 0.75   # time_decay > 0.75 → stale (BTC moved > 4.5h ago)


# ── Beta and H2C signal helpers ────────────────────────────────────────────────

def _estimate_beta(r_asset: List[float], r_btc: List[float]) -> float:
    """OLS β = Cov(r_i, r_BTC) / Var(r_BTC). Returns 1.0 if insufficient data."""
    n = min(len(r_asset), len(r_btc))
    if n < 10:
        return 1.0
    ra = r_asset[-n:]
    rb = r_btc[-n:]
    mean_a = sum(ra) / n
    mean_b = sum(rb) / n
    cov  = sum((ra[i] - mean_a) * (rb[i] - mean_b) for i in range(n)) / n
    varb = sum((rb[i] - mean_b) ** 2 for i in range(n)) / n
    return cov / varb if varb > 1e-10 else 1.0


def _compute_h2c_signal(
    all_prices:  Dict[str, Dict[int, float]],
    active_pairs: List[str],
    ts:          int,
    btc_key:     str,
    beta_hist:   Dict[str, List[List[float]]],
) -> Optional[Dict[str, float]]:
    """H2C: CS_z(β_i × r_BTC,2h − r_i,2h).

    beta_hist: pair → [[r_i_1h], [r_btc_1h]] — updated in-place.
    Requires 24+ hours of β history; returns None during burn-in.
    """
    r_btc_2h = compute_return(all_prices[btc_key], ts, 2.0)
    if r_btc_2h is None:
        return None

    # Update 1h return histories (always, to preserve burn-in state)
    r_btc_1h = compute_return(all_prices[btc_key], ts, 1.0)
    if r_btc_1h is not None:
        for pair in active_pairs:
            if pair == btc_key:
                continue
            r_1h = compute_return(all_prices[pair], ts, 1.0)
            if r_1h is not None:
                beta_hist[pair][0].append(r_1h)
                beta_hist[pair][1].append(r_btc_1h)
                if len(beta_hist[pair][0]) > LOOKBACK:
                    beta_hist[pair][0] = beta_hist[pair][0][-LOOKBACK:]
                    beta_hist[pair][1] = beta_hist[pair][1][-LOOKBACK:]

    gaps: Dict[str, float] = {}
    for pair in active_pairs:
        if pair == btc_key:
            continue
        hist = beta_hist[pair]
        if len(hist[0]) < 24:
            continue  # burn-in
        r_2h = compute_return(all_prices[pair], ts, 2.0)
        if r_2h is None:
            continue
        beta = _estimate_beta(hist[0], hist[1])
        gaps[pair] = beta * r_btc_2h - r_2h

    if len(gaps) < 4:
        return None
    return cross_sectional_z(gaps)


def _make_beta_hist(active_pairs: List[str], btc_key: str) -> Dict[str, List[List[float]]]:
    """Fresh beta_hist for a new backtest run."""
    return {p: [[], []] for p in active_pairs if p != btc_key}


# ── C2 gate helpers ────────────────────────────────────────────────────────────

def _realized_vol(prices: Dict[int, float], ts: int, hours: int = 6) -> Optional[float]:
    rets = []
    for lag in range(1, hours + 1):
        r = compute_return(prices, ts - lag * MS_PER_HOUR, 1.0)
        if r is not None:
            rets.append(r)
    if len(rets) < max(3, hours // 2):
        return None
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets)) or 1e-8


def _pearson_r(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 5:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / n
    sx  = math.sqrt(sum((v - mx) ** 2 for v in xs) / n)
    sy  = math.sqrt(sum((v - my) ** 2 for v in ys) / n)
    if sx < 1e-9 or sy < 1e-9:
        return None
    return cov / (sx * sy)


def _gate_btc_vol_z(
    btc_prices: Dict[int, float],
    ts: int,
    btc_vol_hist: List[float],
    thresh: float = HAZ2_VOL_Z_THRESH,
) -> bool:
    """Returns True (gate triggered) if BTC 6h realized vol z-score > thresh."""
    rv = _realized_vol(btc_prices, ts, hours=6)
    if rv is None:
        return False
    btc_vol_hist.append(rv)
    if len(btc_vol_hist) > LOOKBACK:
        btc_vol_hist[:] = btc_vol_hist[-LOOKBACK:]
    if len(btc_vol_hist) < 12:
        return False
    w    = btc_vol_hist[-LOOKBACK:]
    m    = sum(w) / len(w)
    s    = math.sqrt(sum((v - m) ** 2 for v in w) / len(w)) or 1e-8
    z    = (rv - m) / s
    return z > thresh


def _gate_corr_collapse(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    btc_key:      str,
    ts:           int,
    thresh:       float = HAZ2_CORR_THRESH,
) -> bool:
    """Returns True (gate triggered) if rolling 48h median BTC-alt correlation < thresh.

    Computes Pearson r between BTC and each alt using last CORR_LOOKBACK 1h returns.
    """
    btc_prices = all_prices[btc_key]
    btc_rets: List[float] = []
    for lag in range(1, CORR_LOOKBACK + 1):
        r = compute_return(btc_prices, ts - lag * MS_PER_HOUR, 1.0)
        if r is not None:
            btc_rets.append(r)
    if len(btc_rets) < 24:
        return False

    corrs: List[float] = []
    for pair in active_pairs:
        if pair == btc_key:
            continue
        alt_rets: List[float] = []
        for lag in range(1, CORR_LOOKBACK + 1):
            r = compute_return(all_prices[pair], ts - lag * MS_PER_HOUR, 1.0)
            if r is not None:
                alt_rets.append(r)
        n = min(len(btc_rets), len(alt_rets))
        if n < 10:
            continue
        rho = _pearson_r(btc_rets[:n], alt_rets[:n])
        if rho is not None:
            corrs.append(rho)

    if len(corrs) < 3:
        return False
    corrs.sort()
    median_corr = corrs[len(corrs) // 2]
    return median_corr < thresh


# ── C3 proxy helpers ───────────────────────────────────────────────────────────

def _proxy_gap_remaining(
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    btc_key:      str,
    ts:           int,
    beta_hist:    Dict[str, List[List[float]]],
) -> Dict[str, float]:
    """Gap closure fraction for each pair: |r_i,2h| / |β_i × r_BTC,2h|.

    Returns {pair: float in [0,1]}, empty if BTC didn't move enough.
    """
    r_btc_2h = compute_return(all_prices[btc_key], ts, 2.0)
    if r_btc_2h is None:
        return {}

    result: Dict[str, float] = {}
    for pair in active_pairs:
        if pair == btc_key:
            continue
        hist = beta_hist.get(pair, [[], []])
        if len(hist[0]) < 24:
            continue
        r_2h = compute_return(all_prices[pair], ts, 2.0)
        if r_2h is None:
            continue
        beta = _estimate_beta(hist[0], hist[1])
        expected = beta * r_btc_2h
        if abs(expected) < 0.001:
            continue  # BTC gap too small to measure meaningfully
        gap_closure = min(abs(r_2h) / abs(expected), 1.0)
        result[pair] = gap_closure
    return result


def _proxy_time_decay(
    btc_prices: Dict[int, float],
    ts:         int,
    lookback_h: int = 6,
) -> Optional[float]:
    """Time elapsed since BTC's most significant 1h move in past lookback_h hours.

    Returns float in [0, 1]: 0 = BTC just moved, 1 = BTC moved lookback_h ago.
    Returns None if insufficient BTC history.
    """
    best_abs_r = 0.0
    best_lag   = lookback_h  # default: stale

    for lag in range(1, lookback_h + 1):
        r = compute_return(btc_prices, ts - lag * MS_PER_HOUR, 1.0)
        if r is None:
            continue
        if abs(r) > best_abs_r:
            best_abs_r = abs(r)
            best_lag   = lag

    if best_abs_r < 0.001:
        return None  # BTC barely moved in lookback window — not an H2 signal period

    return min(best_lag / lookback_h, 1.0)


# ── Stats helper ───────────────────────────────────────────────────────────────

def _compute_stats(
    rets:       List[float],
    nav_series: List[Tuple[int, float]],
    label:      str,
) -> dict:
    n = len(rets)
    if n < 2:
        return {"label": label, "n_periods": n}
    mean_ret = sum(rets) / n
    std_ret  = math.sqrt(sum((r - mean_ret) ** 2 for r in rets) / n) or 1e-8
    sharpe   = mean_ret / std_ret * math.sqrt(365 * 24 / HOLD_HOURS)

    peak = running = 1.0
    max_dd = 0.0
    for r in rets:
        running *= (1 + r)
        if running > peak:
            peak = running
        dd = (running - peak) / peak
        if dd < max_dd:
            max_dd = dd

    period_steps = PERIOD_DAYS * 24 // HOLD_HOURS
    worst_dd = 0.0
    for i in range(max(0, len(nav_series) - period_steps)):
        s_nav = nav_series[i][1]
        end   = i + period_steps
        e_nav = nav_series[end][1] if end < len(nav_series) else nav_series[-1][1]
        pdd   = (e_nav - s_nav) / s_nav
        if pdd < worst_dd:
            worst_dd = pdd

    hit_rate  = sum(1 for r in rets if r > 0) / n
    final_nav = nav_series[-1][1] if nav_series else 1.0
    return {
        "label":        label,
        "n_periods":    n,
        "sharpe_ann":   sharpe,
        "max_dd":       max_dd,
        "worst_30d":    worst_dd,
        "hit_rate":     hit_rate,
        "total_return": final_nav - 1.0,
        "final_nav":    final_nav,
    }


def _ic_stats(ics: List[float]) -> dict:
    n = len(ics)
    if n < 3:
        return {"n": n, "mean_ic": None, "t_stat": None}
    mean_ic = sum(ics) / n
    std_ic  = math.sqrt(sum((v - mean_ic) ** 2 for v in ics) / n) or 1e-8
    t       = mean_ic / (std_ic / math.sqrt(n))
    return {"n": n, "mean_ic": mean_ic, "t_stat": t}


# ── C2 backtest ────────────────────────────────────────────────────────────────

def run_h2_c2_backtest(
    proxy_id:     str,
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
) -> Tuple[dict, dict]:
    """Bare H2C vs H2C+gate backtest. Returns (bare_stats, gated_stats)."""
    btc_key = next((p for p in active_pairs if p.startswith("BTC")), None)
    if btc_key is None:
        raise ValueError("BTCUSDT not in active_pairs")

    btc_prices    = all_prices[btc_key]
    beta_bare     = _make_beta_hist(active_pairs, btc_key)
    beta_gated    = _make_beta_hist(active_pairs, btc_key)
    btc_vol_hist  = []  # for HAZ2_BTC_VOL_Z gate (gated run only)

    nav_bare = nav_gated = 1.0
    rets_bare:   List[float]              = []
    rets_gated:  List[float]              = []
    nav_bare_s:  List[Tuple[int, float]]  = [(timestamps[0], 1.0)]
    nav_gated_s: List[Tuple[int, float]]  = [(timestamps[0], 1.0)]

    for i, ts in enumerate(timestamps):
        if i % HOLD_HOURS != 0:
            continue

        # ── Compute H2C signal (both runs update their own beta_hist) ──────
        sig_bare  = _compute_h2c_signal(all_prices, active_pairs, ts, btc_key, beta_bare)
        sig_gated = _compute_h2c_signal(all_prices, active_pairs, ts, btc_key, beta_gated)

        # ── Gate check ──────────────────────────────────────────────────────
        is_blocked = False
        if proxy_id == "HAZ2_BTC_VOL_Z":
            is_blocked = _gate_btc_vol_z(btc_prices, ts, btc_vol_hist)
        elif proxy_id == "HAZ2_CORR_COLLAPSE":
            is_blocked = _gate_corr_collapse(all_prices, active_pairs, btc_key, ts)

        # ── Bare return ─────────────────────────────────────────────────────
        port_ret_bare = 0.0
        if sig_bare is not None:
            ranked = sorted(sig_bare.items(), key=lambda x: -x[1])
            selected = [p for p, _ in ranked[:TOP_N]]
            bare_rets = [compute_forward_return(all_prices[p], ts, HOLD_HOURS)
                         for p in selected]
            bare_rets = [r for r in bare_rets if r is not None]
            port_ret_bare = sum(bare_rets) / len(bare_rets) if bare_rets else 0.0

        nav_bare *= (1 + port_ret_bare)
        rets_bare.append(port_ret_bare)
        nav_bare_s.append((ts + HOLD_HOURS * MS_PER_HOUR, nav_bare))

        # ── Gated return ────────────────────────────────────────────────────
        if is_blocked or sig_gated is None:
            port_ret_gated = 0.0
        else:
            ranked = sorted(sig_gated.items(), key=lambda x: -x[1])
            selected = [p for p, _ in ranked[:TOP_N]]
            gated_rets = [compute_forward_return(all_prices[p], ts, HOLD_HOURS)
                          for p in selected]
            gated_rets = [r for r in gated_rets if r is not None]
            port_ret_gated = sum(gated_rets) / len(gated_rets) if gated_rets else 0.0

        nav_gated *= (1 + port_ret_gated)
        rets_gated.append(port_ret_gated)
        nav_gated_s.append((ts + HOLD_HOURS * MS_PER_HOUR, nav_gated))

    bare_stats  = _compute_stats(rets_bare,  nav_bare_s,  "H2C_bare")
    gated_stats = _compute_stats(rets_gated, nav_gated_s, proxy_id)

    # Compute % periods blocked (gated run)
    gated_zeros = sum(1 for r in rets_gated if r == 0.0)
    bare_zeros  = sum(1 for r in rets_bare  if r == 0.0)
    gated_stats["pct_blocked"] = (gated_zeros - bare_zeros) / max(len(rets_gated), 1)
    return bare_stats, gated_stats


# ── C3 IC screen ───────────────────────────────────────────────────────────────

def run_h2_c3_ic_screen(
    proxy_id:     str,
    all_prices:   Dict[str, Dict[int, float]],
    active_pairs: List[str],
    timestamps:   List[int],
) -> dict:
    """IC screen for one H2 C3 proxy.

    Returns {"fresh": ic_stat, "stale": ic_stat, "unconditional": ic_stat}.
    """
    btc_key = next((p for p in active_pairs if p.startswith("BTC")), None)
    if btc_key is None:
        raise ValueError("BTCUSDT not in active_pairs")

    btc_prices = all_prices[btc_key]
    beta_hist  = _make_beta_hist(active_pairs, btc_key)

    fresh_ics: List[float] = []
    stale_ics: List[float] = []
    all_ics:   List[float] = []

    for i, ts in enumerate(timestamps):
        if i % HOLD_HOURS != 0:
            continue

        sig = _compute_h2c_signal(all_prices, active_pairs, ts, btc_key, beta_hist)
        if sig is None:
            continue

        fwd: Dict[str, float] = {
            p: f
            for p in sig
            if (f := compute_forward_return(all_prices[p], ts, HOLD_HOURS)) is not None
        }

        common = [p for p in sig if p in fwd]
        if len(common) < 5:
            continue

        # Unconditional IC
        ic_all = spearman_ic([sig[p] for p in common], [fwd[p] for p in common])
        if ic_all is not None:
            all_ics.append(ic_all)

        # ── Proxy classification ─────────────────────────────────────────────
        if proxy_id == "MAT2_GAP_REMAINING":
            # Per-pair proxy: split pairs by their gap closure fraction
            gaps = _proxy_gap_remaining(all_prices, active_pairs, btc_key, ts, beta_hist)
            fresh_pairs = [p for p in common if gaps.get(p, 1.0) <= MAT2_GAP_FRESH]
            stale_pairs = [p for p in common if gaps.get(p, 0.0) >= MAT2_GAP_STALE]

        elif proxy_id == "MAT2_TIME_DECAY":
            # Timestamp-level proxy: all pairs fresh or all stale together
            td = _proxy_time_decay(btc_prices, ts)
            if td is None:
                continue
            if td <= MAT2_TIME_FRESH:
                fresh_pairs = list(common)
                stale_pairs = []
            elif td >= MAT2_TIME_STALE:
                fresh_pairs = []
                stale_pairs = list(common)
            else:
                fresh_pairs = []
                stale_pairs = []

        else:
            continue

        # Fresh IC
        if len(fresh_pairs) >= 4:
            ic_f = spearman_ic(
                [sig[p] for p in fresh_pairs],
                [fwd[p] for p in fresh_pairs],
            )
            if ic_f is not None:
                fresh_ics.append(ic_f)

        # Stale IC
        if len(stale_pairs) >= 4:
            ic_s = spearman_ic(
                [sig[p] for p in stale_pairs],
                [fwd[p] for p in stale_pairs],
            )
            if ic_s is not None:
                stale_ics.append(ic_s)

    return {
        "fresh":         _ic_stats(fresh_ics),
        "stale":         _ic_stats(stale_ics),
        "unconditional": _ic_stats(all_ics),
    }


# ── Output writers ─────────────────────────────────────────────────────────────

def _pass_fail(condition: bool) -> str:
    return "**APPROVED**" if condition else "REJECTED"


def write_c2_result(
    proxy_id:    str,
    bare:        dict,
    gated:       dict,
    thresholds:  List[Tuple[float, Tuple[dict, dict]]],   # (threshold, (bare, gated))
) -> None:
    """Write C2 modifier screen result to the proxy's folder."""
    out_dir = os.path.join(H2_C2_DIR, proxy_id)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "02_modifier_screen.md")

    max_dd_bare  = bare.get("max_dd", 0.0) or 0.0
    max_dd_gated = gated.get("max_dd", 0.0) or 0.0
    w30_bare     = bare.get("worst_30d", 0.0) or 0.0
    w30_gated    = gated.get("worst_30d", 0.0) or 0.0

    if max_dd_bare < -0.001:
        max_dd_rel = (max_dd_gated - max_dd_bare) / abs(max_dd_bare)
    else:
        max_dd_rel = 0.0

    w30_pp = (w30_gated - w30_bare)  # negative DD so improvement = less negative

    approved = (max_dd_rel >= 0.10 and w30_pp >= 0.05)

    pct_blocked = gated.get("pct_blocked", 0.0)

    lines = [
        f"# {proxy_id} — C2 Modifier Screen",
        "",
        "**Mechanism:** H2C BTC-Diffusion  ",
        f"**Training period:** Oct 2024–Jan 2025  ",
        "**Approval criterion:** MaxDD relative improvement ≥ 10% AND worst 30d DD improvement ≥ 5pp  ",
        "",
        "## Summary",
        "",
        f"| Metric | Bare H2C | {proxy_id} gated | Change |",
        "|--------|----------|-----------------|--------|",
        f"| Total Return | {bare.get('total_return', 0)*100:.1f}% | {gated.get('total_return', 0)*100:.1f}% | {(gated.get('total_return', 0)-bare.get('total_return', 0))*100:+.1f}pp |",
        f"| MaxDD | {max_dd_bare*100:.1f}% | {max_dd_gated*100:.1f}% | {max_dd_rel*100:+.1f}% relative |",
        f"| Worst 30d DD | {w30_bare*100:.1f}% | {w30_gated*100:.1f}% | {w30_pp*100:+.1f}pp |",
        f"| Sharpe (ann) | {bare.get('sharpe_ann', 0):.2f} | {gated.get('sharpe_ann', 0):.2f} | — |",
        f"| % periods blocked | — | {pct_blocked*100:.1f}% | — |",
        f"| N rebalances | {bare.get('n_periods', 0)} | {gated.get('n_periods', 0)} | — |",
        "",
        f"## Decision",
        "",
        f"**MaxDD relative improvement:** {max_dd_rel*100:.1f}% {'≥ 10%' if max_dd_rel >= 0.10 else '< 10%'} (criterion: ≥ 10%)  ",
        f"**Worst 30d DD improvement:** {w30_pp*100:.1f}pp {'≥ 5pp' if w30_pp >= 0.05 else '< 5pp'} (criterion: ≥ 5pp)  ",
        "",
        f"**Status: {_pass_fail(approved)}**",
        "",
    ]

    if thresholds:
        lines += [
            "## Threshold Sweep",
            "",
            "| Threshold | MaxDD (bare) | MaxDD (gated) | Rel improvement | Worst 30d (gated) | % blocked |",
            "|-----------|-------------|---------------|----------------|-------------------|-----------|",
        ]
        for thresh, (b, g) in thresholds:
            mdb = b.get("max_dd", 0.0) or 0.0
            mdg = g.get("max_dd", 0.0) or 0.0
            rel = (mdg - mdb) / abs(mdb) if mdb < -0.001 else 0.0
            w30g = g.get("worst_30d", 0.0) or 0.0
            blk  = g.get("pct_blocked", 0.0)
            lines.append(
                f"| {thresh} | {mdb*100:.1f}% | {mdg*100:.1f}% | {rel*100:+.1f}% | {w30g*100:.1f}% | {blk*100:.1f}% |"
            )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written: {out_path}")


def write_c3_result(proxy_id: str, result: dict) -> None:
    """Write C3 IC screen result to the proxy's folder."""
    out_dir  = os.path.join(H2_C3_DIR, proxy_id)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "02_modifier_screen.md")

    fresh = result["fresh"]
    stale = result["stale"]
    uncond = result["unconditional"]

    ic_u = uncond.get("mean_ic")
    ic_f = fresh.get("mean_ic")

    approved = (ic_f is not None and ic_u is not None and ic_f > ic_u)

    def _fmt(s: dict) -> str:
        ic = s.get("mean_ic")
        t  = s.get("t_stat")
        n  = s.get("n", 0)
        if ic is None:
            return f"N/A (n={n})"
        return f"{ic:+.4f} (t={t:+.2f}, n={n})"

    lines = [
        f"# {proxy_id} — C3 Modifier Screen",
        "",
        "**Mechanism:** H2C BTC-Diffusion  ",
        "**Training period:** Oct 2024–Jan 2025  ",
        "**Approval criterion:** IC(H2C | fresh) > IC(H2C | unconditional)  ",
        "",
        "## IC Conditional on Proxy State",
        "",
        "| Bucket | IC | N obs | Gate |",
        "|--------|----|-------|------|",
        f"| Unconditional | {_fmt(uncond)} | {uncond.get('n', 0)} | baseline |",
        f"| **Fresh** (proxy ≤ threshold) | {_fmt(fresh)} | {fresh.get('n', 0)} | {'BETTER' if approved else 'WORSE'} |",
        f"| Stale (proxy ≥ stale_thr) | {_fmt(stale)} | {stale.get('n', 0)} | — |",
        "",
        "## Interpretation",
        "",
    ]

    if proxy_id == "MAT2_GAP_REMAINING":
        lines += [
            f"Fresh = gap_closure < {MAT2_GAP_FRESH} (>70% of BTC-expected catch-up still outstanding).  ",
            f"Stale = gap_closure > {MAT2_GAP_STALE} (>80% of expected catch-up already realized).  ",
        ]
    elif proxy_id == "MAT2_TIME_DECAY":
        lines += [
            f"Fresh = time_decay < {MAT2_TIME_FRESH} (BTC's peak move was < {MAT2_TIME_FRESH*6:.1f}h ago).  ",
            f"Stale = time_decay > {MAT2_TIME_STALE} (BTC's peak move was > {MAT2_TIME_STALE*6:.1f}h ago).  ",
        ]

    lines += [
        "",
        "## Decision",
        "",
        f"IC(fresh) = {_fmt(fresh)}  ",
        f"IC(unconditional) = {_fmt(uncond)}  ",
        "",
        f"**Status: {_pass_fail(approved)}**",
        "",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written: {out_path}")


def write_summary(c2_results: List[Tuple[str, dict, dict, bool]],
                  c3_results: List[Tuple[str, dict, bool]]) -> None:
    """Write combined modifier results summary."""
    out_path = os.path.join(H2_SIGNAL_DIR, "03_modifier_results.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines = [
        "# H2C — C2 Hazard + C3 Maturity Modifier Screens",
        "",
        "**Mechanism:** H2 BTC-Diffusion (H2C beta-adjusted gap)  ",
        "**Training period:** Oct 2024–Jan 2025  ",
        "",
        "## C2 Hazard Gate Results",
        "",
        "| Proxy ID | MaxDD (bare) | MaxDD (gated) | MaxDD rel Δ | Worst 30d Δ | Blocked% | Status |",
        "|----------|-------------|---------------|-------------|-------------|----------|--------|",
    ]

    for proxy_id, bare, gated, approved in c2_results:
        mdb = bare.get("max_dd", 0.0) or 0.0
        mdg = gated.get("max_dd", 0.0) or 0.0
        rel = (mdg - mdb) / abs(mdb) if mdb < -0.001 else 0.0
        w30 = (gated.get("worst_30d", 0.0) or 0.0) - (bare.get("worst_30d", 0.0) or 0.0)
        blk = gated.get("pct_blocked", 0.0)
        status = "**APPROVED**" if approved else "REJECTED"
        lines.append(
            f"| `{proxy_id}` | {mdb*100:.1f}% | {mdg*100:.1f}% | {rel*100:+.1f}% | "
            f"{w30*100:+.1f}pp | {blk*100:.1f}% | {status} |"
        )

    lines += [
        "",
        "## C3 Maturity Scaler Results",
        "",
        "| Proxy ID | IC(unconditional) | IC(fresh) | IC(stale) | Fresh obs | Status |",
        "|----------|------------------|-----------|-----------|-----------|--------|",
    ]

    for proxy_id, result, approved in c3_results:
        ic_u = result["unconditional"].get("mean_ic")
        ic_f = result["fresh"].get("mean_ic")
        ic_s = result["stale"].get("mean_ic")
        n_f  = result["fresh"].get("n", 0)
        status = "**APPROVED**" if approved else "REJECTED"
        fmt = lambda v: f"{v:+.4f}" if v is not None else "N/A"
        lines.append(
            f"| `{proxy_id}` | {fmt(ic_u)} | {fmt(ic_f)} | {fmt(ic_s)} | {n_f} | {status} |"
        )

    lines += [
        "",
        "## Approved Modifiers",
        "",
    ]

    approved_c2 = [pid for pid, _, _, ok in c2_results if ok]
    approved_c3 = [pid for pid, _, ok  in c3_results if ok]

    if approved_c2:
        lines.append(f"**C2 approved:** {', '.join(f'`{p}`' for p in approved_c2)}")
    else:
        lines.append("**C2 approved:** none (ungated H2C is the baseline)")

    if approved_c3:
        lines.append(f"**C3 approved:** {', '.join(f'`{p}`' for p in approved_c3)}")
    else:
        lines.append("**C3 approved:** none (ungated H2C at all diffusion stages)")

    lines += [
        "",
        "See individual proxy folders for details.",
    ]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written: {out_path}")


# ── Charts ─────────────────────────────────────────────────────────────────────

def _save_c2_chart(
    c2_results: List[Tuple[str, dict, dict, bool]],
) -> None:
    """Bar chart: MaxDD improvement for each C2 proxy."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [WARN] matplotlib not available — skipping C2 chart")
        return

    labels = [pid for pid, _, _, _ in c2_results]
    bare_dds  = [abs((b.get("max_dd") or 0.0) * 100) for _, b, _, _ in c2_results]
    gated_dds = [abs((g.get("max_dd") or 0.0) * 100) for _, _, g, _ in c2_results]
    colors    = ["steelblue" if ok else "lightcoral" for _, _, _, ok in c2_results]

    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([v - 0.2 for v in x], bare_dds,  width=0.35, label="Bare H2C",  color="lightgray")
    ax.bar([v + 0.2 for v in x], gated_dds, width=0.35, label="Gated",    color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Max Drawdown (%)")
    ax.set_title("H2C C2 Gate: MaxDD Comparison\n(shorter = less severe drawdown = better)")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    out = os.path.join(CHARTS_DIR, "c2_modifier_comparison.png")
    plt.savefig(out, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {out}")


def _save_c3_chart(c3_results: List[Tuple[str, dict, bool]]) -> None:
    """Bar chart: fresh vs unconditional IC for each C3 proxy."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [WARN] matplotlib not available — skipping C3 chart")
        return

    labels    = [pid for pid, _, _ in c3_results]
    ic_u      = [r["unconditional"].get("mean_ic") or 0.0 for _, r, _ in c3_results]
    ic_f      = [r["fresh"].get("mean_ic") or 0.0       for _, r, _ in c3_results]
    colors    = ["steelblue" if ok else "lightcoral" for _, _, ok in c3_results]

    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([v - 0.2 for v in x], ic_u, width=0.35, label="Unconditional IC", color="lightgray")
    ax.bar([v + 0.2 for v in x], ic_f, width=0.35, label="Fresh IC",        color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Mean Spearman IC (4h)")
    ax.set_title("H2C C3 Maturity: IC Lift (Fresh vs Unconditional)\n(taller fresh bar = proxy adds value)")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    out = os.path.join(CHARTS_DIR, "c3_ic_lift.png")
    plt.savefig(out, dpi=100, bbox_inches="tight")
    plt.close()
    print(f"  Chart saved: {out}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 72)
    print("h2_modifier_screen.py -- H2C C2/C3 proxy screens")
    print("=" * 72)

    print("\nFetching Roostoo universe...")
    pairs  = fetch_roostoo_pairs()
    months = _month_range(TRENDING_START, TRENDING_END)
    print(f"  {len(pairs)} pairs, {len(months)} months")

    print("\nDownloading klines (Oct 2024–Jan 2025)...")
    (all_prices, _bvol, _qvol, _ntrades, _tbvol,
     _open, _high, _low) = load_klines_all_parallel(
        pairs, months, max_workers=8,
    )

    # Build 1h hourly timestamp grid
    all_ts: set = set()
    for p in all_prices.values():
        all_ts.update(p.keys())
    timestamps = sorted(all_ts)

    active_pairs = [p for p in all_prices if len(all_prices[p]) > LOOKBACK * 2]
    if "BTCUSDT" not in active_pairs:
        active_pairs.append("BTCUSDT")

    print(f"  {len(active_pairs)} active pairs, {len(timestamps)} timestamps")

    # ── C2 screens ─────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("C2 Hazard Gate Screens")
    print("="*60)

    c2_results: List[Tuple[str, dict, dict, bool]] = []
    c2_proxy_ids = ["HAZ2_BTC_VOL_Z", "HAZ2_CORR_COLLAPSE"]

    for proxy_id in c2_proxy_ids:
        print(f"\n  [{proxy_id}] running C2 backtest...")
        bare, gated = run_h2_c2_backtest(proxy_id, all_prices, active_pairs, timestamps)

        mdb = bare.get("max_dd", 0.0) or 0.0
        mdg = gated.get("max_dd", 0.0) or 0.0
        rel = (mdg - mdb) / abs(mdb) if mdb < -0.001 else 0.0
        w30 = (gated.get("worst_30d", 0.0) or 0.0) - (bare.get("worst_30d", 0.0) or 0.0)
        approved = (rel >= 0.10 and w30 >= 0.05)

        print(f"  bare MaxDD={mdb*100:.1f}%  gated MaxDD={mdg*100:.1f}%  "
              f"rel={rel*100:+.1f}%  w30={w30*100:+.1f}pp  "
              f"{'APPROVED' if approved else 'rejected'}")

        # Threshold sweep for HAZ2_CORR_COLLAPSE
        thresholds: List[Tuple[float, Tuple[dict, dict]]] = []
        if proxy_id == "HAZ2_CORR_COLLAPSE":
            for thresh in [0.30, 0.40, 0.50]:
                print(f"    threshold={thresh} sweep...")
                b2, g2 = run_h2_c2_backtest(proxy_id, all_prices, active_pairs, timestamps)
                thresholds.append((thresh, (b2, g2)))

        write_c2_result(proxy_id, bare, gated, thresholds)
        c2_results.append((proxy_id, bare, gated, approved))

    # ── C3 screens ─────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("C3 Maturity Proxy Screens")
    print("="*60)

    c3_results: List[Tuple[str, dict, bool]] = []
    c3_proxy_ids = ["MAT2_GAP_REMAINING", "MAT2_TIME_DECAY"]

    for proxy_id in c3_proxy_ids:
        print(f"\n  [{proxy_id}] running C3 IC screen...")
        result = run_h2_c3_ic_screen(proxy_id, all_prices, active_pairs, timestamps)

        ic_u = result["unconditional"].get("mean_ic")
        ic_f = result["fresh"].get("mean_ic")
        approved = (ic_f is not None and ic_u is not None and ic_f > ic_u)

        _ic_u_s = f"{ic_u:+.4f}" if ic_u is not None else "N/A"
        _ic_f_s = f"{ic_f:+.4f}" if ic_f is not None else "N/A"
        print(f"  IC(uncond)={_ic_u_s}  "
              f"IC(fresh)={_ic_f_s}  "
              f"n_fresh={result['fresh'].get('n', 0)}  "
              f"{'APPROVED' if approved else 'rejected'}")

        write_c3_result(proxy_id, result)
        c3_results.append((proxy_id, result, approved))

    # ── Summary ────────────────────────────────────────────────────────────────
    write_summary(c2_results, c3_results)

    print("\nGenerating charts...")
    _save_c2_chart(c2_results)
    _save_c3_chart(c3_results)

    # Final verdicts
    print("\n" + "="*72)
    print("MODIFIER SCREEN SUMMARY")
    print("="*72)
    for pid, _, _, ok in c2_results:
        print(f"  C2 {pid}: {'APPROVED' if ok else 'rejected'}")
    for pid, r, ok in c3_results:
        print(f"  C3 {pid}: {'APPROVED' if ok else 'rejected'} "
              f"(IC fresh={r['fresh'].get('mean_ic') or 0:+.4f} "
              f"vs uncond={r['unconditional'].get('mean_ic') or 0:+.4f})")
    print("="*72)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
