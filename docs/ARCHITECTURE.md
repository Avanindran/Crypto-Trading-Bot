# Architecture: Module Dependency Diagram

## Role Separation

Each module serves exactly one role in the system. No module mixes concerns from different layers.

```
Role A (State Sensing):   feature_builder.py, market_cache.py
Role B (Regime Inference): regime.py
Role C (Governance):       kill_switch.py, drawdown.py, constraints.py
Role D (Control):          order_manager.py (timeout cancellation)
Role E (Allocation):       sizing.py, allocator.py
Role F (Signal/Alpha):     signals.py, maturity.py, ranking.py
```

## Module Dependency Flow

```
main.py
  │
  ├── reconcile.py         [startup checks + state sync]
  │     └── roostoo_client.py
  │
  ├── market_cache.py      [rolling price history]
  │     └── roostoo_client.py  [ticker ingestion]
  │
  ├── feature_builder.py   [Role A: State Sensing]
  │     └── market_cache.py
  │
  ├── regime.py            [Role B: Regime Inference]
  │     └── feature_builder.py
  │
  ├── signals.py           [Role F: Alpha Signal C1]
  │     └── feature_builder.py
  │
  ├── maturity.py          [Role F: Maturity M_t]
  │     └── feature_builder.py
  │
  ├── ranking.py           [Role F: PositionScore = C1 × exp(-λ) × C3]
  │     ├── signals.py
  │     ├── maturity.py
  │     └── regime.py  [reads λ_t]
  │
  ├── sizing.py            [Role E: Kelly weights]
  │     └── feature_builder.py  [downside vol]
  │
  ├── allocator.py         [Role E: Gross cap allocation]
  │     ├── sizing.py
  │     └── regime.py  [gross cap per regime]
  │
  ├── drawdown.py          [Role C: Drawdown tracking]
  ├── kill_switch.py       [Role C: Emergency exit + BTC gate]
  ├── constraints.py       [Role C: Hold period + lockout]
  │
  ├── order_manager.py     [Role D: Order lifecycle]
  │     └── roostoo_client.py
  │
  ├── state.py             [persistence]
  └── logger.py            [structured logging]
```

## Data Flow (Per Loop)

```
1. roostoo_client.get_ticker()
        ↓
2. market_cache.ingest(ticker_data)
        ↓
3. feature_builder.build_all_features(cache)
   → AssetFeatures (r_30m, r_2h, r_6h, r_24h, vol, spread, extension, rsi_proxy, pct_rank)
   → CrossSectionalFeatures (median_r2h, std_r30m, median_spread)
        ↓
4. regime_engine.compute(asset_features, cs)
   → (RegimeState, λ_t)
        ↓
5. Risk gates (kill_switch, drawdown, BTC gate)
   → block_entries flag, emergency exits if triggered
        ↓
6. signals.compute_c1_scores(asset_features, cs)
   → Dict[pair, C1_z]
        ↓
7. maturity.compute_all_maturity(asset_features)
   → Dict[pair, M_t]
        ↓
8. ranking.rank_assets(c1, maturity, λ_t, regime)
   → List[RankedAsset] sorted by PositionScore = C1 × exp(-λ_t) × C3
        ↓
9. Per-position exits (signal decay, stop-loss, trailing stop, max hold)
        ↓
10. allocator.compute_target_weights(ranked, features, regime)
    → Dict[pair, target_weight]
        ↓
11. order_manager.place_limit_order() for each new entry
        ↓
12. order_manager.cancel_timed_out_orders()
        ↓
13. state.save_state() + logger.log_state()
        ↓
14. sleep(60s)
```

## API Rate Budget

```
Normal (1 call/min):   ticker only
Active (2-4/min):      + balance (every 5 loops) + pending_count (every 3 loops)
Trading (4-8/min):     + place_order + cancel_order on-demand
Hard ceiling: 25/min   (5 below the 30/min API limit)
```
