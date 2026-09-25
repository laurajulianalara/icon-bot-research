#!/usr/bin/env python3
"""Fast classifier for sampled production extras. READ ONLY."""
from pathlib import Path
import sys, bisect, json
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]
TZ="America/New_York"
REF=ROOT/"data/v11_reversal_state_forensics.csv"
BENCH=ROOT/"data/reports/2026-09_trades.csv"
samples=[
("2026-09-01 02:27","LONG"),
("2026-09-01 03:36","LONG"),
("2026-09-01 03:57","LONG"),
("2026-09-02 02:39","SHORT"),
("2026-09-02 09:39","SHORT"),
]
def et(series):
    x=pd.to_datetime(series,errors="coerce",utc=True)
    return x.dt.tz_convert(TZ)
r=pd.read_csv(REF)
r["candidate_time_et"]=et(r["candidate_time"])
# Rebuild the exact historical V15 membership logic used by current reporter.
r["reclaim_x_wick"]=r.early_reclaim_atr*r.wick_percent
r["close_x_reclaim"]=r.m2_close_pos*r.early_reclaim_atr
r["sweep_minus_reclaim"]=r.sweep_atr-r.early_reclaim_atr
r["impulse_minus_reclaim"]=r.reversal_impulse-r.early_reclaim_atr
r["quality_balance"]=r.rejection_quality*r.impulse_to_reclaim/(1+r.reclaim_to_sweep)
parts=[]
for col,hi,w in [
("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),
("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),
("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]:
    q=r[col].rank(pct=True); parts += [(q if hi else 1-q)]*w
r["score"]=pd.concat(parts,axis=1).mean(axis=1)
thr=r.score.quantile(.07)
eligible=r[r.score>=thr].copy()
eligible["date_et"]=eligible.candidate_time_et.dt.date
eligible=eligible.sort_values("candidate_time_et")
eligible["early_v15_slot"]=eligible.groupby("date_et").cumcount()+1
allowed=eligible[eligible.early_v15_slot<=6].copy()
allowed_keys=set(zip(allowed.candidate_time_et.astype(str),allowed.direction.astype(str)))

b=pd.read_csv(BENCH)
cc="candidate_time_et" if "candidate_time_et" in b.columns else "candidate_time"
bc=pd.to_datetime(b[cc],errors="coerce")
if bc.dt.tz is None: bc=bc.dt.tz_localize(TZ)
else: bc=bc.dt.tz_convert(TZ)
bkeys=set(zip(bc.astype(str),b.direction.astype(str)))

print("="*100)
print("THE ICON — FAST EXTRA ROOT-CAUSE CLASSIFIER")
print("="*100)
print("V11 rows:",len(r),"| score threshold:",float(thr),"| historical V15 allowed after old early cap:",len(allowed))
print()
for ts,direction in samples:
    t=pd.Timestamp(ts,tz=TZ)
    rows=r[(r.candidate_time_et==t)&(r.direction.astype(str)==direction)]
    print(t,direction)
    if rows.empty:
        print("  V11 reference row: NO")
        print("  => Historical reporter treats this as historical but cannot admit it through frozen V15 membership.")
        continue
    x=rows.iloc[0]
    key=(str(t),direction)
    scorepass=bool(float(x.score)>=float(thr))
    slotrow=eligible[(eligible.candidate_time_et==t)&(eligible.direction.astype(str)==direction)]
    slot=int(slotrow.iloc[0].early_v15_slot) if len(slotrow) else None
    print("  V11 reference row: YES")
    print("  V15 score:",round(float(x.score),6),"| score passes:",scorepass)
    print("  old early-V15 slot:",slot)
    print("  historical V15 membership:",key in allowed_keys)
    print("  frozen 75 benchmark:",key in bkeys)
    if scorepass and slot is not None and slot>6:
        print("  ROOT-CAUSE FLAG: passes V15 score but is excluded ONLY by the reporter's old early 6/day V15 membership cap.")
    elif not scorepass:
        print("  ROOT-CAUSE FLAG: historical V15 score itself fails.")
    elif key in allowed_keys and key not in bkeys:
        print("  ROOT-CAUSE FLAG: passes historical V15; dropped at a later historical stage (V27/supersession/final cap/etc.).")
    print()
print("READ-ONLY. No strategy/report/data changed.")
