# H2 BTC-Diffusion Mechanism Test

**Run:** 2026-03-17 05:53 UTC
**Period:** Oct 2024 – Jan 2025 (trending period)

## Research Question

H2 hypothesis: BTC reprices new information first; alts that lagged BTC's move
should catch up within 1–6h (expectation diffusion lag).

**The H2a collapse:** CS_z(alt_r - btc_r) = CS_z(-alt_r) [mathematical identity].
BTC return is a cross-sectional constant removed by z-normalization.
H2a provides zero independent information beyond H1 (reversal) in CS z-score space.

**Proper test:** If H2 is the mechanism, IC of the laggard signal should be
**HIGHER** when BTC has moved significantly vs when BTC is flat.
If H1 is the mechanism (generic reversal), IC should be stable regardless of BTC move.

**Additionally:** Does the raw BTC gap (btc_r_2h - alt_r_2h, NOT z-scored)
have HIGHER IC than plain H1 (-alt_r_2h)? This would confirm the BTC contribution adds info.

## IC by BTC Regime — H1_neg_r2h Signal

| BTC Regime | IC at 2h | IC at 4h |
|------------|----------|----------|
| BTC flat (|btc_r_2h| < 0.5%) | +0.0352* (t=6.6, n=1917) | +0.0237* (t=4.4, n=1916) |
| BTC moderate (0.5%–1.5%) | +0.0558* (t=6.5, n=827) | +0.0548* (t=6.2, n=826) |
| BTC large UP (|btc_r_2h| >= 1.5%, positive) | +0.0882* (t=3.3, n=97) | +0.1101* (t=4.0, n=97) |
| BTC large DOWN (|btc_r_2h| >= 1.5%, negative) | +0.0249 (t=0.7, n=85) | +0.0424 (t=1.4, n=85) |
| Unconditional (all timestamps) | +0.0425* (t=9.5, n=2926) | +0.0359* (t=8.0, n=2924) |

## IC by BTC Regime — Promoted Signal (0.70×H1 + 0.30×H5_neg_vol)

| BTC Regime | IC at 2h | IC at 4h |
|------------|----------|----------|
| BTC flat (|btc_r_2h| < 0.5%) | +0.0539* (t=10.1, n=1917) | +0.0534* (t=9.8, n=1916) |
| BTC moderate (0.5%–1.5%) | +0.0559* (t=6.5, n=827) | +0.0600* (t=7.1, n=826) |
| BTC large UP (|btc_r_2h| >= 1.5%, positive) | +0.1035* (t=3.8, n=97) | +0.1194* (t=4.3, n=97) |
| BTC large DOWN (|btc_r_2h| >= 1.5%, negative) | +0.0223 (t=0.8, n=85) | +0.0323 (t=1.2, n=85) |
| Unconditional (all timestamps) | +0.0552* (t=12.5, n=2926) | +0.0569* (t=12.7, n=2924) |

## IC by BTC Regime — Raw H2 Diffusion Gap (btc_r_2h - alt_r_2h, NOT z-scored)

| BTC Regime | IC at 2h | IC at 4h |
|------------|----------|----------|
| BTC flat (|btc_r_2h| < 0.5%) | +0.0352* (t=6.6, n=1917) | +0.0237* (t=4.4, n=1916) |
| BTC moderate (0.5%–1.5%) | +0.0558* (t=6.5, n=827) | +0.0548* (t=6.2, n=826) |
| BTC large UP (|btc_r_2h| >= 1.5%, positive) | +0.0882* (t=3.3, n=97) | +0.1101* (t=4.0, n=97) |
| BTC large DOWN (|btc_r_2h| >= 1.5%, negative) | +0.0249 (t=0.7, n=85) | +0.0424 (t=1.4, n=85) |
| Unconditional (all timestamps) | +0.0425* (t=9.5, n=2926) | +0.0359* (t=8.0, n=2924) |

## Interpretation

### Gate: Does H2 add over H1?

**BTC-conditioning test (IC uplift = IC_large_move - IC_flat at 4h):**
  H1_neg_r2h: IC_large_up = 0.1101, IC_flat = 0.0237, uplift = +0.0864

**Result: H2 MECHANISM CONFIRMED** (uplift > 0.010)
IC of the laggard signal is meaningfully higher when BTC has moved.
The signal exploits BTC-diffusion lag, not just generic cross-sectional reversal.
Implication: C2 regime filter should key on BTC move direction/magnitude.

**Raw diffusion gap test (does keeping BTC's contribution improve IC?):**
  H2_raw IC at 4h = 0.0359, H1_raw IC at 4h = 0.0359, lift = +0.0000

Raw H2 gap IC <= H1 IC — confirming the BTC contribution does not add information.

## Connection to Existing Research

**Why H2a collapsed:** In cross-sectional z-score space, CS_z(alt_r - btc_r) = CS_z(alt_r - constant) = CS_z(alt_r).
BTC return is a cross-sectional constant. Z-normalization removes it. H2a = H1 in CS z-score space.
This was documented in 08_limitations_and_rejections.md. This test confirms whether the
BTC contribution adds information in NON-z-scored space.

**Previous H2b test:** Lagged BTC return as a market-level predictor (same value for all alts).
Result: Pearson r = -0.003. No diffusion lag at 1h aggregation.

**Current test:** BTC-conditioned IC of the laggard signal (H1). This is the only
test that can distinguish H2 from H1 empirically.

See `research/charts/05_h2_mechanism/ic_btc_conditioned.png` for visual IC profiles by BTC regime.
