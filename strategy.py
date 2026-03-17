# Strategy implementation is in the bot/strategy/ package:
#   bot/strategy/regime.py    — Regime State Vector (LSI/MPI/FEI → RegimeState, λ_t)
#   bot/strategy/signals.py   — C1 alpha signal (cross-sectional momentum z-score)
#   bot/strategy/maturity.py  — M_t diffusion maturity → C3 = (1 − M_t)
#   bot/strategy/ranking.py   — PositionScore = C1 × exp(−λ_t) × C3
