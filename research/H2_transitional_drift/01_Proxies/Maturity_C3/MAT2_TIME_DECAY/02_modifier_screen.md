# MAT2_TIME_DECAY — C3 Modifier Screen

**Mechanism:** H2C BTC-Diffusion  
**Training period:** Oct 2024–Jan 2025  
**Approval criterion:** IC(H2C | fresh) > IC(H2C | unconditional)  

## IC Conditional on Proxy State

| Bucket | IC | N obs | Gate |
|--------|----|-------|------|
| Unconditional | +0.0233 (t=+2.64, n=713) | 713 | baseline |
| **Fresh** (proxy ≤ threshold) | +0.0400 (t=+2.45, n=237) | 237 | BETTER |
| Stale (proxy ≥ stale_thr) | +0.0090 (t=+0.65, n=252) | 252 | — |

## Interpretation

Fresh = time_decay < 0.4 (BTC's peak move was < 2.4h ago).  
Stale = time_decay > 0.75 (BTC's peak move was > 4.5h ago).  

## Decision

IC(fresh) = +0.0400 (t=+2.45, n=237)  
IC(unconditional) = +0.0233 (t=+2.64, n=713)  

**Status: **APPROVED****

