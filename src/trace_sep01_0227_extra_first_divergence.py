#!/usr/bin/env python3
"""Trace one confirmed live extra to the FIRST historical/live divergence. READ ONLY."""
from pathlib import Path
import sys
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
import icon_option2b_shadow_live as live
TZ="America/New_York"; TARGET=pd.Timestamp("2026-09-01 02:27",tz=TZ); DIRECTION="LONG"
HIST=ROOT/"data/mnq_continuous_1m.parquet"; CAND=ROOT/"data/reversal_candidates.parquet"
V7=ROOT/"data/v7_base_trade_quality.parquet"; V11=ROOT/"data/v11_reversal_state_forensics.csv"

def times(df):
    for c in ["time_ny","candidate_time","candidate_time_et","time"]:
        if c in df.columns:
            x=pd.to_datetime(df[c],errors="coerce",utc=True)
            return c,x.dt.tz_convert(TZ)
    return None,None
def find(path,label):
    if not path.exists(): return label,"FILE_MISSING",0,None
    d=pd.read_parquet(path) if path.suffix==".parquet" else pd.read_csv(path)
    tc,t=times(d)
    if tc is None:return label,"NO_TIME_COLUMN",0,None
    dirs=d["direction"].astype(str).str.upper() if "direction" in d.columns else pd.Series([""]*len(d))
    m=(t==TARGET)&(dirs==DIRECTION)
    return label,("PRESENT" if m.any() else "ABSENT"),int(m.sum()),list(d.columns)

one=pd.read_parquet(HIST)
one["time_ny"]=pd.to_datetime(one.time_ny,errors="coerce")
if one.time_ny.dt.tz is None:one["time_ny"]=one.time_ny.dt.tz_localize(TZ)
else:one["time_ny"]=one.time_ny.dt.tz_convert(TZ)
one=one.sort_values("time_ny").reset_index(drop=True)
# Production/live candidate existence at the exact 02:30 entry boundary.
closed=one[one.time_ny<TARGET+pd.Timedelta(minutes=3)].tail(5000).copy()
live_open=one[one.time_ny==TARGET+pd.Timedelta(minutes=3)].iloc[0].to_dict()
lc=live.build_candidates(closed)
lm=(lc.time_ny==TARGET)&(lc.direction.astype(str)==DIRECTION) if len(lc) else pd.Series([],dtype=bool)
ls=[x for x in live.evaluate(closed,live_open=live_open) if pd.Timestamp(x["candidate_time_et"])==TARGET and x["direction"]==DIRECTION]

stages=[
("RAW reversal_candidates",CAND),
("V7 base_trade_quality",V7),
("V11 reversal_state_forensics",V11),
]
print("="*96);print("THE ICON — SINGLE EXTRA FIRST-DIVERGENCE TRACE");print("="*96)
print("Target:",TARGET,DIRECTION,"-> entry boundary",TARGET+pd.Timedelta(minutes=3))
print("\nLIVE / CURRENT PIPELINE")
print("  build_candidates:", "PRESENT" if len(lc) and lm.any() else "ABSENT")
print("  evaluate final eligible at boundary:", "PRESENT" if ls else "ABSENT")
if ls:
    x=ls[0]; print("  V15:",round(x["v15_score"],6),"entry:",x["entry"],"stop:",x["stop"])
print("\nORIGINAL HISTORICAL RESEARCH ARTIFACTS")
first=None
for label,path in stages:
    lab,status,n,cols=find(path,label)
    print(f"  {lab}: {status}"+(f" ({n} row)" if n else ""))
    if first is None and status=="ABSENT":first=lab
print("\nFIRST OBSERVED DIVERGENCE:",first or "none in inspected artifacts")
if first=="RAW reversal_candidates":
    print("MEANING: the extra did not originate in the original raw historical candidate universe. The difference is BEFORE V7/V8/V11/V15.")
elif first=="V7 base_trade_quality":
    print("MEANING: raw historical candidate existed, but it did not survive the original V7/simulation construction.")
elif first=="V11 reversal_state_forensics":
    print("MEANING: it survived original V7 artifact but disappeared before V11; inspect the V8/V11 construction next.")
else:
    print("MEANING: it survives through V11; divergence is later.")
print("\nREAD-ONLY. No strategy/data/report changed.")
