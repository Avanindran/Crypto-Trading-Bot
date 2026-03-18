# OOS Reservation — H1 Reversal Strategy

**Written:** 2026-03-17
**Status:** LOCKED — No inspection of holdout data before strategy freeze

---

## Holdout Period

| Field | Value |
|-------|-------|
| Start | 2024-12-01 00:00 UTC |
| End   | 2025-01-31 23:00 UTC |
| Duration | ~61 days |
| HOLDOUT_START_TS | 1733011200000 (ms) |

## Training Period

| Field | Value |
|-------|-------|
| Start | 2024-10-01 |
| End   | 2024-11-30 |
| Duration | ~61 days |

## Reservation Declaration

The Dec 2024–Jan 2025 window was declared as OOS holdout **before** any data
download was initiated. It was not inspected during:
- IC threshold decisions
- GP weight search (inner train = Oct–Nov 2024 only)
- C2/C3 modifier screen decisions

The holdout was used for a single final validation after strategy freeze:
- `ic_validation_extended.py`: holdout IC = +0.066 (t=+10.6) vs train IC = +0.047
- `gp_search.py`: holdout IC > 0 at 4h after formula selected on inner train
- `backtest_simulation.py`: OOS sub-period metrics reported but NOT used for tuning

## Why Dec–Jan is a Valid Holdout

The Oct–Jan period (4 months) covers the BTC bull run (+61% peak, Oct→Dec) and
the Jan 2025 correction. The Dec–Jan holdout includes:
- The late-stage bull run (Nov–Dec)
- The correction peak (Dec 2024 ~$108k BTC)
- The subsequent drawdown (Jan 2025 ~$90k BTC)

The holdout contains a regime transition that was not represented in the training
period. If the signal worked only in trending markets, holdout IC would be lower.
Holdout IC = +0.066 > train IC = +0.047 confirms the signal generalises across
regime conditions.

## Temporal Ordering of Research Steps

Per doctrine (see `10_pipeline_index.md`), the holdout was used in this order:
1. Training period IC testing → signal selection (Steps 3A–2B)
2. Holdout IC validation → single inspection, reported but not used for tuning
3. Full-period backtest (Oct–Jan) → includes OOS period for illustration only

No parameter was changed after Step 2 based on holdout results.
