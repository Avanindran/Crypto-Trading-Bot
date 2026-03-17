# Portfolio Construction Test — Step 6

**Generated:** 2026-03-17 09:25 UTC
**Period:** Oct–Nov 2024 (train only; holdout Dec–Jan unseen)
**Signal:** 0.70×H1_reversal + 0.30×H5_low_vol (promoted formula)
**Regime gate:** C2 BTC vol z > 1.5 → skip rebalance
**Gross cap:** 85% | Max positions: 5

## Decision Gate

**Gate:** Quarter-Kelly Sortino >= Equal-weight Sortino
**Result: PASS** (Kelly = +10.48, EW = +10.48)

## Scheme Comparison

| Scheme | Sortino | Sharpe | Calmar | MaxDD | Total Ret |
|--------|---------|--------|--------|-------|-----------|
| A: Equal weight | +10.48 | +6.25 | 347.2 | −9.5% | +78.7% |
| B: Score-proportional | +11.35 | +6.51 | 589.8 | −10.4% | +97.2% |
| C: Quarter-Kelly | +10.48 | +6.25 | 347.2 | −9.5% | +78.7% |
| D: Risk parity | +10.08 | +6.05 | 210.5 | −9.5% | +65.0% |

## Economic Rationale

**Quarter-Kelly (Scheme C)** is the live bot choice (KELLY_FRACTION = 0.25 in config.py).
Kelly sizing allocates proportional to signal strength (C1_z) and inversely to risk (downside_vol^2), concentrating capital in high-conviction, low-risk positions. This maximises long-run expected log-wealth under the Bernoulli criterion.

**Equal weight (Scheme A)** is the baseline. Quarter-Kelly matches EW here because all top-K assets have raw Kelly weights >> MAX_POSITION_WEIGHT (0.30). With KELLY_MU = 0.005 and typical downvol ~0.02:
```
raw_kelly_i ≈ 0.25 × 1.0 × 0.005 / 0.02² = 3.125  >> 0.30 (MAX_POSITION_WEIGHT cap)
```
All top-K assets hit the 30% cap, producing equal weight.

**Score-proportional (Scheme B)** produces the best Sortino (11.35) by tilting slightly toward higher-scored assets without full Kelly concentration. This is the deployed method.

**Risk parity (Scheme D)** produces the worst Sortino (10.08). Pure risk-based allocation with no signal conviction weighting — underweights the best signal assets.

## Decision

Quarter-Kelly PASS (Sortino +10.48 = EW). The Kelly framework provides theoretical correctness with no practical cost at the current universe size. Score-proportional (Scheme B) retained as live method for marginal improvement.

See `config.py`: `KELLY_FRACTION = 0.25`, `MAX_POSITION_WEIGHT = 0.30`.
