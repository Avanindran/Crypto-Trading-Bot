---
proxy_id: HAZ_MPI_CHOP
family: Hazard_C2
formula: fraction of assets with positive r_1h < 0.30 → block entries
status: REJECTED
ic_best: N/A
---

# HAZ_MPI_CHOP — Mechanism

## Formula

Market Participation Index (MPI): fraction of universe assets with positive 1h return < 0.30
→ block new entries

```
mpi = mean(r_1h[all_assets] > 0)   # fraction positive
block_entry if mpi < 0.30
```

## Economic Rationale

When fewer than 30% of assets post a positive 1-hour return, the market is in a
broad-based decline — a "participation collapse" that may indicate the early stages
of a risk-off event. In theory, this should precede continued selling pressure that
would render reversal entries premature. However, empirically, MPI < 0.30 also fires
during healthy pullback-and-recovery sequences within uptrends. Many of these episodes
are followed immediately by sharp rebounds — precisely the conditions where the
C1 laggard signal is most predictive. Blocking entries at this threshold cuts off
profitable reversal trades while providing insufficient protection against true drawdown
events.

## Signal Family

C2 Hazard — market breadth / participation gate

## Decision

**Status:** REJECTED — MaxDD change −14.3%; the MPI gate misfires significantly,
blocking profitable reversal entries during pullbacks without successfully filtering
genuine drawdown events; the MPI is more useful as a confirming signal than a hard gate.
