# H2C — C2 Hazard + C3 Maturity Modifier Screens

**Mechanism:** H2 BTC-Diffusion (H2C beta-adjusted gap)  
**Training period:** Oct 2024–Jan 2025  

## C2 Hazard Gate Results

| Proxy ID | MaxDD (bare) | MaxDD (gated) | MaxDD rel Δ | Worst 30d Δ | Blocked% | Status |
|----------|-------------|---------------|-------------|-------------|----------|--------|
| `HAZ2_BTC_VOL_Z` | -66.2% | -57.4% | +13.4% | +11.4pp | 9.9% | **APPROVED** |
| `HAZ2_CORR_COLLAPSE` | -66.2% | -69.7% | -5.3% | -0.0pp | 4.9% | REJECTED |

## C3 Maturity Scaler Results

| Proxy ID | IC(unconditional) | IC(fresh) | IC(stale) | Fresh obs | Status |
|----------|------------------|-----------|-----------|-----------|--------|
| `MAT2_GAP_REMAINING` | +0.0233 | +0.0223 | +0.0323 | 206 | REJECTED |
| `MAT2_TIME_DECAY` | +0.0233 | +0.0400 | +0.0090 | 237 | **APPROVED** |

## Approved Modifiers

**C2 approved:** `HAZ2_BTC_VOL_Z`
**C3 approved:** `MAT2_TIME_DECAY`

See individual proxy folders for details.
