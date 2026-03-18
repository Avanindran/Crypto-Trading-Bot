# H2 Hazard C2 — Proxy Universe

> These proxies gate H2C signal entry based on conditions that invalidate the
> BTC-diffusion mechanism. Each proxy answers: "Is the BTC-to-altcoin diffusion
> channel currently functional?"

---

## Candidate Registry

| Proxy ID | Formula | Mechanism Failure Mode | Status |
|----------|---------|----------------------|--------|
| HAZ2_BTC_VOL_Z | BTC 6h realized vol z-score > 1.50 | High BTC vol → BTC reversal within diffusion window → gap misdirected | PENDING |
| HAZ2_CORR_COLLAPSE | 48h median Spearman ρ(r_BTC, r_i) < 0.40 | Alt-season correlation collapse → β_i estimates unreliable → H2C mechanism invalid | PENDING |

---

## Approval Criterion

For each proxy: run H2C backtest with and without gate (training period Oct–Nov 2024).
**APPROVE** if:
- MaxDD relative improvement ≥10% vs ungated baseline
- Worst 30-day drawdown improvement ≥5pp

---

## Results

See `h2_modifier_screen.py` → `02_modifier_results.md` in `../../02_Candidates/Signal/`.

---

## Notes on Scope

H2 C2 proxies are fundamentally different from H1 C2 proxies:

- **H1 C2** gates on market stress (liquidations, panic) — failure mode is cascade
- **H2 C2** gates on BTC mechanism validity — failure mode is BTC-alt channel breakdown

Some signals (HAZ2_BTC_VOL_Z) overlap with H1's approved proxies because elevated
BTC vol is a precursor to both cascade risk AND BTC reversal risk. However, the
economic chains are distinct: the same indicator blocks entry for different reasons.

The true H2-unique gate is HAZ2_CORR_COLLAPSE: no H1 analogue exists because H1
does not depend on BTC correlation.
