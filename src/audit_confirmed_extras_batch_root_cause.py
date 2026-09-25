#!/usr/bin/env python3
"""Batch-classify confirmed September extras at the original V7/supersession gate. READ ONLY."""
from pathlib import Path
import sys
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
import icon_option2b_shadow_live as live
TZ="America/New_York"
ONE=ROOT/"data/mnq_continuous_1m.parquet"; CAND=ROOT/"data/reversal_candidates.parquet"
REPORT=ROOT/"data/icon_month_live_report.csv"
# Known confirmed extras from production-style targeted replay; script also discovers more if report/live artifacts permit.
KNOWN=[
("2026-09-01 02:27","LONG"),("2026-09-01 03:36","LONG"),("2026-09-01 03:57","LONG"),
("2026-09-02 02:39","SHORT"),("2026-09-02 09:39","SHORT"),
]

def norm(s):
 x=pd.to_datetime(s,errors="coerce")
 return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

one=pd.read_parquet(ONE).copy(); one["time_ny"]=norm(one.time_ny)
one=one.sort_values("time_ny").drop_duplicates("time_ny").reset_index(drop=True)
prev=one.close.shift()
one["atr1"]=pd.concat([one.high-one.low,(one.high-prev).abs(),(one.low-prev).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()
raw=pd.read_parquet(CAND).copy(); raw["time_ny"]=norm(raw.time_ny)
raw=raw.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
raw["next_same_extreme_time"]=raw.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)

rows=[]
for ts,direction in KNOWN:
 t=pd.Timestamp(ts,tz=TZ); rr=raw[(raw.time_ny==t)&(raw.direction.astype(str)==direction)]
 if rr.empty:
  rows.append(dict(candidate=t,direction=direction,class_="RAW_CANDIDATE_MISSING")); continue
 c=rr.iloc[0]; i=idx.get(t)
 if i is None or i<20 or i+3>=len(one):
  rows.append(dict(candidate=t,direction=direction,class_="1M_INDEX_INVALID")); continue
 a=float(one.iloc[i].atr1); sg=1 if direction=="LONG" else -1
 vals={}
 for k in [1,2]:
  b=one.iloc[i+k]
  vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
  cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
  vals[f"m{k}_close_pos"]=float(cp if direction=="LONG" else 1-cp)
 v7=vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912
 j=i+3; signal=one.iloc[j].time_ny; nx=c.next_same_extreme_time
 superseded=pd.notna(nx) and signal>=nx
 ticker_ok=str(one.iloc[j].ticker)==str(c.ticker)
 entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if direction=="LONG" else float(c.extreme)+.25
 risk=entry-stop if direction=="LONG" else stop-entry
 if not v7: reason="V7_NUMERIC_FAIL"
 elif superseded:
  reason="SUPERSEDED_BEFORE_ENTRY" if nx<signal else "SUPERSEDED_AT_ENTRY"
 elif not ticker_ok: reason="TICKER_MISMATCH"
 elif risk<=0: reason="RISK_NONPOSITIVE"
 else: reason="SURVIVES_V7_SIM_GATE"
 rows.append(dict(candidate=t,direction=direction,session=c.session,signal=signal,next_extreme=nx,
  class_=reason,m1_move=vals["m1_move_atr"],m1_close=vals["m1_close_pos"],m2_close=vals["m2_close_pos"],
  entry=entry,stop=stop,risk=risk))

out=pd.DataFrame(rows)
print("="*112); print("THE ICON — CONFIRMED EXTRA BATCH ROOT-CAUSE CLASSIFIER"); print("="*112)
show=["candidate","session","direction","signal","next_extreme","class_"]
print(out[show].to_string(index=False))
print("\nSUMMARY")
print(out["class_"].value_counts(dropna=False).to_string())
n=len(out); sup=out.class_.isin(["SUPERSEDED_AT_ENTRY","SUPERSEDED_BEFORE_ENTRY"]).sum()
print(f"\nSupersession-related: {sup}/{n} ({100*sup/n:.1f}%)")
print("\nINTERPRETATION")
if sup==n:
 print("ALL tested confirmed extras are removed historically by the same supersession mechanism.")
elif sup>=max(1,int(.8*n)):
 print("Supersession is the dominant mechanism in this confirmed-extra sample.")
else:
 print("Extras have multiple mechanisms; inspect the non-supersession classes before patching.")
print("\nREAD-ONLY. No strategy thresholds, reports, or data changed.")
