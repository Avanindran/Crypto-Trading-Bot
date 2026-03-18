# H2 Maturity C3 — Proxy Universe

> These proxies gate H2C signal entry based on diffusion window exhaustion:
> "How much of the BTC-driven diffusion opportunity has already been realized?"
> When C3 fires, the H2C signal is stale — diffusion has largely propagated.

Unlike H1's C3 (which measures reversal maturity: how extended is the asset from
mean?), H2's C3 measures **diffusion maturity**: how far along is the BTC-to-alt
price propagation at the moment we observe the H2C gap?

---

## Candidate Registry

| Proxy ID | Formula | Mechanism | Status |
|----------|---------|-----------|--------|
| MAT2_GAP_REMAINING | `\|r_i,2h\| / \|β_i × r_BTC,2h\|` (gap closure fraction) | Direct diffusion progress: fraction of owed catch-up already realized | PENDING |
| MAT2_TIME_DECAY | `(t − t_peak_BTC) / 6h` (time since BTC's peak 1h move) | Temporal diffusion window: too much time → propagation mostly complete | PENDING |

---

## Approval Criterion

IC-conditional test: for each proxy, split timestamps into **fresh** vs **stale** buckets.

**APPROVE** if: IC(H2C | fresh bucket) > IC(H2C | unconditional full period)

Fresh definitions:
- MAT2_GAP_REMAINING: gap_closure < 0.30 (>70% of gap still open)
- MAT2_TIME_DECAY: time_decay < 0.40 (BTC's peak move was < 2.4h ago)

---

## Results

See `h2_modifier_screen.py` → `03_modifier_results.md` in `../../02_Candidates/Signal/`.

---

## Notes on Scope

**H2 C3 ≠ H1 C3:**

H1's maturity (M_t) asks: "Has the mean-reversion trade already been partially
captured?" It measures price extension from SMA, RSI overbought proxy, and
funding rate crowding.

H2's maturity asks: "Has the BTC diffusion wave already passed?" It measures gap
closure and time elapsed since BTC's directional impulse.

Both are mechanism-specific C3 filters — they are NOT cross-mechanism overlays.
The `overlays/` layer contains only the regime overlay (λ_t), which is the sole
cross-mechanism component that allocates between H1 and H2.
