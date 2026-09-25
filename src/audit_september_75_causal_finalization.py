#!/usr/bin/env python3
"""THE ICON — September 75-trade causal finalization audit.

READ ONLY with respect to existing data/strategy. Creates one new report CSV.
Purpose: test whether each frozen September benchmark trade can be produced at
T+3 using only candidate T plus the two completed 1m bars T+1/T+2.

No future next_same_extreme_time / supersession information is used.
No thresholds are changed.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

EXPECTED=Path("data/reports/2026-09_trades.csv")
OUT=Path("data/reports/2026-09_75_causal_finalization_audit.csv")
if not EXPECTED.exists(): raise RuntimeError(f"Missing {EXPECTED}")
if not Path(live.HIST).exists(): raise RuntimeError(f"Missing {live.HIST}")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

exp=pd.read_csv(EXPECTED)
exp["entry_time"]=et(exp.entry_time)
exp=exp[(exp.entry_time>=pd.Timestamp("2026-09-01",tz=live.TZ))&
        (exp.entry_time<pd.Timestamp("2026-10-01",tz=live.TZ))].copy()
if len(exp)!=75:
    raise RuntimeError(f"Benchmark guard failed: expected exactly 75 September trades, found {len(exp)}")

one=pd.read_parquet(live.HIST)[live.NEED].copy()
one["time_ny"]=et(one.time_ny)
# Include enough pre-September history for ATR/ranking context.
one=one[(one.time_ny>=pd.Timestamp("2026-08-28",tz=live.TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=live.TZ))].sort_values("time_ny").reset_index(drop=True)

# Build a strictly causal signal stream. At each minute N, evaluate only bars
# closed through N and use N+1 open as live_open. This mirrors shadow-live.
signals=[]
seen=set()
for j in range(1,len(one)):
    live_open=one.iloc[j]
    closed=one.iloc[:j].copy()
    now=pd.Timestamp(live_open.time_ny)
    if now<pd.Timestamp("2026-09-01",tz=live.TZ): continue
    if now>=pd.Timestamp("2026-10-01",tz=live.TZ): break
    for x in live.evaluate(closed, live_open=live_open):
        if pd.Timestamp(x["entry_time_et"])!=now: continue
        if x["signal_id"] in seen: continue
        seen.add(x["signal_id"]); signals.append(x)

got=pd.DataFrame(signals)
if got.empty: raise RuntimeError("Causal audit emitted zero signals")
got["entry_time"]=et(got.entry_time_et)

# Benchmark membership only. We intentionally do not cap/delete causal extras:
# this audit asks whether all 75 are independently knowable at their entry time.
keys=["entry_time","session","direction"]
match=exp[keys].merge(got[keys+["candidate_time_et","entry","stop","v15_score"]],
                      on=keys,how="left",indicator=True)
match["causally_reproduced"]=match["_merge"].eq("both")
match.drop(columns=["_merge"]).to_csv(OUT,index=False)

print("="*92)
print("THE ICON — SEPTEMBER 75-TRADE CAUSAL FINALIZATION AUDIT")
print("="*92)
print("Frozen benchmark:",len(exp))
print("Benchmark trades reproduced causally:",int(match.causally_reproduced.sum()))
print("Benchmark trades NOT reproduced causally:",int((~match.causally_reproduced).sum()))
print("All causal signals seen (including extras):",len(got))
print("\nBY DAY")
print(match.groupby(match.entry_time.dt.date).causally_reproduced.agg(["count","sum"]).to_string())
if (~match.causally_reproduced).any():
    print("\nMISSING BENCHMARK TRADES")
    print(match.loc[~match.causally_reproduced,keys].to_string(index=False))
print("\nSaved:",OUT)
print("READ ONLY — no strategy thresholds or existing data changed.")
