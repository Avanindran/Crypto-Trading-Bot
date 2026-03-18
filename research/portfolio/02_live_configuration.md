# Portfolio — Current Live Configuration

**Written:** 2026-03-17
**Bot status:** Live from Mar 21, 2026

---

## Deployed Formula

```
PositionScore_i = C1_i × exp(−λ_t) × (1 − M_t_i)

C1_i = 0.70 × CS_z(−C1_raw_i) + 0.30 × CS_z(−realized_vol_6h_i)

C1_raw_i = 0.10×r_30m + 0.20×r_2h + 0.35×r_6h + 0.25×r_24h + 0.10×(r_2h − median_r2h)
```

H2C signal (`CS_z(β_i × r_BTC,2h − r_i,2h)`) has been validated (IC=+0.042 @ 1h, t=+9.85) and fully backtested with all modifiers (2026-03-18):

| H2C parameter | Value | Sweep |
|--------------|-------|-------|
| HAZ2_BTC_VOL_Z gate (z_thresh) | 0.75 | Version B — no discriminatory power (all thresholds equivalent) |
| BTC-direction exit | −1.0% | Version C — BTC-rev exit boosts Calmar from −0.40 → 4.65 |
| Hold cap | 6h | Version D |
| BTC magnitude gate | 0.3% | Version E — Calmar jumps to 14.81 |
| MAT2_TIME_DECAY gate | None | Version F — time decay filter hurts full-strategy metrics; not applied |
| TOP_N | 4 | Portfolio sweep |

**H2C Final:** ret=+74.0%, Sortino=1.99, Calmar=20.25, MaxDD=−20.6%

**Dual-engine allocation:** α_TREND_OPT=0.0 — H1 alone (Sortino=2.78, Calmar=12.13) beats any H1+H2 blend. H2C is a better standalone engine than a portfolio enhancement for H1. **H2C is not deployed in Round 1.** See [04_engine_integration.md](04_engine_integration.md) for bot architecture spec.

---

## Signal Layer

| Component | Value | Source |
|-----------|-------|--------|
| H1 reversal weight | 0.70 | GP search on train (Oct–Nov 2024) |
| H5 stability weight | 0.30 | GP search on train |
| H2 Transitional Drift | Not deployed | Proxy failed; mechanism confirmed |

**config.py parameters:**
```python
ALPHA_WEIGHT_REVERSAL = 0.70
ALPHA_WEIGHT_STABILITY = 0.30
```

---

## Regime Layer (λ_t)

```
LSI > 0.80 → EMERGENCY, λ = 10.0
LSI > 0.60 → HAZARD_DEFENSIVE, λ = 4.0
LSI > 0.40 OR MPI < 0.30 → NEUTRAL_MIXED, λ = 1.5
FEI > 0.55 AND MPI > 0.50 → TREND_SUPPORTIVE, λ = 0.3
else → NEUTRAL_MIXED, λ = 0.8
```

**LSI composition:**
```python
LSI_WEIGHT_BTC_VOL = 0.45
LSI_WEIGHT_SPREAD  = 0.25
LSI_WEIGHT_DISP    = 0.15
LSI_WEIGHT_FNG     = 0.15
```

---

## Portfolio Construction

| Parameter | Value |
|-----------|-------|
| Sizing method | Score-proportional |
| Min position | 5% NAV |
| Max position | 30% NAV |
| TREND gross cap | 85% NAV, max 5 positions |
| NEUTRAL gross cap | 65% NAV, max 3 positions |
| HAZARD gross cap | 0% (no new entries) |
| EMERGENCY | Exit all positions |

---

## Risk Layer

| Parameter | Value |
|-----------|-------|
| Hard stop loss | −4% per position |
| Trailing stop activation | +3% |
| Trailing stop trail | 2.5% |
| Max hold time | 72h |
| Min hold time | 4h |
| Re-entry lockout | 2h after exit |
| Portfolio drawdown caution | −5% |
| Portfolio drawdown defensive | −8% |
| Portfolio drawdown kill | −12% |

---

## Expected Regime Distribution

From regime allocation backtest (Oct 2024 – Jan 2025, 3-regime ladder):
- TREND_SUPPORTIVE: ~55.6% of periods
- NEUTRAL_MIXED: ~34.7% of periods
- HAZARD_DEFENSIVE: ~9.8% of periods

In a trending bull run (competition period), TREND_SUPPORTIVE is expected to dominate. In a sideways or declining market, NEUTRAL_MIXED will be more frequent.

---

## Research-Validated Parameter Changes (2026-03-17)

From mechanism-specific backtest sweeps:

| Config parameter | Old value | New value | Evidence |
|-----------------|-----------|-----------|---------|
| `STOP_LOSS_PCT` | −4% | **−4%** (confirmed) | H1 SL sweep: −4% best Calmar, stops <5%/period |
| `EXIT_C1_THRESHOLD` | 0.20 | **0.25** | H1 exit sweep: Sortino 1.86 vs 1.32 at 0.20 |

See `research/H1_reversal/02_Candidates/Strategy/02_backtest.md` for full sweep tables.
