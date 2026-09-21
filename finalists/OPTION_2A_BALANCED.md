# OPTION 2A — BALANCED FREQUENCY / DRAWDOWN

Status: SAVED FINALIST / DO NOT OVERWRITE

## Core
- RR: 1:4
- Filter: reject only when BOTH early_reclaim_atr >= 0.576132 AND reclaim_x_wick >= 0.183258
- Equivalent keep rule: early_reclaim_atr < 0.576132 OR reclaim_x_wick < 0.183258

## Full result
- Trades: 958
- Active trading days: 289
- Active trades/day: 3.31
- Win rate: 65.45%
- Net: +2177R
- Expectancy: +2.27R/trade
- Max drawdown: 5R
- Max losing streak: 5
- Max trades/day: 6

## Robustness
10 chronological folds:
1 66.67%
2 62.50%
3 60.42%
4 67.71%
5 70.83%
6 61.46%
7 66.67%
8 61.46%
9 69.47%
10 67.37%

Worst fold WR: 60.42%
Every fold net positive.
Fold max DD: 3R–5R.

## Daily risk
- Days >=3R DD: 9
- Days >=4R DD: 1
- Days >=5R DD: 0
- Max trades/day: 6

## Monthly
All tested months Sep 2025–Sep 2026 were profitable.
Monthly WR range: 56.00%–71.08%.
Monthly max DD: 2R–5R.

## Note
Research/backtest finalist only. Requires costs/slippage, integer MNQ sizing, roll handling, timestamp/parity audit, and final independent validation before live use.
