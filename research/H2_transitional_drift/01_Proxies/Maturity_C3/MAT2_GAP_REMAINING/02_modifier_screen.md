# MAT2_GAP_REMAINING — C3 Modifier Screen

**Mechanism:** H2C BTC-Diffusion  
**Training period:** Oct 2024–Jan 2025  
**Approval criterion:** IC(H2C | fresh) > IC(H2C | unconditional)  

## IC Conditional on Proxy State

| Bucket | IC | N obs | Gate |
|--------|----|-------|------|
| Unconditional | +0.0233 (t=+2.64, n=713) | 713 | baseline |
| **Fresh** (proxy ≤ threshold) | +0.0223 (t=+0.75, n=206) | 206 | WORSE |
| Stale (proxy ≥ stale_thr) | +0.0323 (t=+3.04, n=640) | 640 | — |

## Interpretation

Fresh = gap_closure < 0.3 (>70% of BTC-expected catch-up still outstanding).  
Stale = gap_closure > 0.8 (>80% of expected catch-up already realized).  

## Decision

IC(fresh) = +0.0223 (t=+0.75, n=206)  
IC(unconditional) = +0.0233 (t=+2.64, n=713)  

**Status: REJECTED**

