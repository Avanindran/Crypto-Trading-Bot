# Maturity Overlay — Decision Record

**Date:** 2026-03-17
**Decision:** PARTIALLY VALIDATED — pct_rank proxy REJECTED; composite retained with caveat
**Status:** Live in `bot/strategy/maturity.py`

---

## Validation Gate — pct_rank Proxy

The validation test uses pct_rank as a standalone maturity proxy, comparing IC across maturity buckets.

### Test Specification

**Gate:** IC(fresh bucket, pct_rank < 30%) > IC(unconditional)

Fresh = pct_rank of r_6h in own 48h history < 30% → asset recently started recovering from laggard position.

If fresh assets have higher IC than unconditioned assets, pct_rank is a valid maturity filter.

### Results

| Maturity Bucket | Mean IC at 4h | N observations |
|-----------------|---------------|---------------|
| Fresh (pct_rank < 30%) | +0.018 | 410 |
| Mid (30–70%) | +0.030 | 611 |
| Stale (pct_rank > 70%) | +0.052 | 482 |
| Unconditional | +0.048 | 731 |

IC(fresh) = +0.018 < IC(unconditional) = +0.048

**Gate result: FAIL**

### Why It Failed

In the Oct–Jan 2024 trending period:
- "Stale" assets (pct_rank > 70%) have the **highest** IC (+0.052) — these are assets that have been recovering for a while, which in a trend means they have genuine momentum
- "Fresh" assets (pct_rank < 30%) have the **lowest** IC (+0.018) — recently started recovering, but in a trend these may be weaker assets just beginning a cycle that will take many periods to complete
- The pct_rank proxy inverts the intended relationship in trending conditions

**Root cause:** pct_rank mislabels ongoing momentum as "mature recovery." In a trending period, assets that have recently started moving are not in the late stage of a correction — they are in the early stage of a momentum move. The filter incorrectly excludes these assets.

---

## Decision: Composite Retained with Caveat

The four-component M_t composite includes SMA extension and funding rate, which were not tested in the pct_rank validation:

- **SMA extension:** Captures price-level overextension (not covered by return percentile)
- **Funding rate:** Captures crowded positioning in perpetual markets (externally sourced)

These components address different aspects of overextension than pct_rank alone. They are retained on economic grounds:

1. Funding rate is a direct market signal not derivable from price history
2. SMA extension is a geometric measure (price vs average), not a distributional measure (return percentile vs history)

The composite is accepted in the live bot with this documented caveat: only the pct_rank component was formally tested; the remaining components lack equivalent IC validation.

---

## Formal Status

| Component | Validation | Status |
|-----------|-----------|--------|
| pct_rank proxy (standalone) | IC gate FAIL | REJECTED |
| SMA extension | Not tested (different hypothesis) | Retained (economic basis) |
| RSI proxy | Not tested | Retained (economic basis) |
| Funding rate | Not tested (new component) | Retained (economic basis) |
| Composite M_t | Not formally tested as unit | PROVISIONAL |

---

## Vector Test Evidence

Adding the full M_t composite (C3) after C2 regime gate:

| Config | Sharpe | Sortino | Calmar | MaxDD |
|--------|--------|---------|--------|-------|
| C1 only (bare signal) | 1.87 | 2.31 | 5.07 | −37.6% |
| C1 + C2 regime | 3.02 | 3.94 | 18.13 | −23.3% |
| C1 + C2 + C3 maturity | 3.16 | 4.33 | 18.67 | −23.6% |

C3 adds marginal improvement (Sharpe 3.02 → 3.16, Sortino 3.94 → 4.33) but the difference is small relative to the C2 regime effect. The composite contributes through entry timing but is not the primary driver of risk-adjusted returns.

Full vector tests: [../../H1_reversal/03_results/05_vector_tests.md](../../H1_reversal/03_results/05_vector_tests.md).

---

## Navigation

| File | Content |
|------|---------|
| [00_mechanism.md](00_mechanism.md) | M_t mechanism theory |
| [01_proxy_universe.md](01_proxy_universe.md) | Component proxy specs |
| [../../H1_reversal/03_results/05_vector_tests.md](../../H1_reversal/03_results/05_vector_tests.md) | Full vector test (C3 contribution) |
