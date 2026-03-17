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

H2C signal (`CS_z(β_i × r_BTC,2h − r_i,2h)`) has been validated (IC=+0.042 @ 1h, t=+9.85) and backtested standalone (Sortino 1.34, Calmar 2.96). Dual-engine allocation sweep found α_TREND_OPT=0.0 — H1 dominates in TREND_ACTIVE periods; H2C and H1 select overlapping laggard assets without additive diversification. **H2C is not deployed in Round 1.** Deploying H2C would require live β_i rolling OLS in `feature_builder.py` — planned for post-Round-1.

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
