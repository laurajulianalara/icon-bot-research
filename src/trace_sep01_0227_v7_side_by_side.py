#!/usr/bin/env python3
"""Sep-01 02:27 LONG — original V7 vs current-live side-by-side. READ ONLY."""
from pathlib import Path
import sys
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
import icon_option2b_shadow_live as live
TZ="America/New_York"; T=pd.Timestamp("2026-09-01 02:27",tz=TZ); D="LONG"
ONE=ROOT/"data/mnq_continuous_1m.parquet"; CAND=ROOT/"data/reversal_candidates.parquet"

def norm(s):
    x=pd.to_datetime(s,errors="coerce")
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

one=pd.read_parquet(ONE).copy(); one["time_ny"]=norm(one["time_ny"])
one=one.sort_values("time_ny").drop_duplicates("time_ny").reset_index(drop=True)
prev=one.close.shift()
one["atr1"]=pd.concat([one.high-one.low,(one.high-prev).abs(),(one.low-prev).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict(); i=idx[T]

raw=pd.read_parquet(CAND).copy(); raw["time_ny"]=norm(raw["time_ny"])
rr=raw[(raw.time_ny==T)&(raw.direction.astype(str)==D)]
if rr.empty: raise SystemExit("Target missing from raw reversal_candidates.")
c=rr.iloc[0]

def v7_vals(extreme):
    a=float(one.iloc[i].atr1); sg=1
    vals={}
    for k in [1,2]:
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
    passed=vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912
    return a,vals,passed

# Current live candidate as knowable at 02:30.
closed=one[one.time_ny<T+pd.Timedelta(minutes=3)].tail(5000).copy()
lc=live.build_candidates(closed)
lr=lc[(lc.time_ny==T)&(lc.direction.astype(str)==D)]
if lr.empty: raise SystemExit("Target missing from current live build_candidates.")
l=lr.iloc[0]

a,vals,v7pass=v7_vals(float(c.extreme))
print("="*100);print("THE ICON — SEP01 02:27 LONG V7 SIDE-BY-SIDE");print("="*100)
print("Candidate:",T,D)
print("\nCANDIDATE FIELDS")
for name in ["extreme","atr","sweep_distance","wick_percent"]:
    ov=float(c[name]) if name in c.index and pd.notna(c[name]) else np.nan
    lv=float(l[name]) if name in l.index and pd.notna(l[name]) else np.nan
    print(f"  {name:18s} original={ov:.12f} | live={lv:.12f} | delta={lv-ov:.12f}")

print("\nV7 INPUTS (same 1m source formula)")
print("  atr1:",a)
checks=[
("m1_move_atr",vals["m1_move_atr"],"<=",.300),
("m1_close_pos",vals["m1_close_pos"],">=",.140),
("m2_close_pos",vals["m2_close_pos"],"<=",.912)]
for n,v,op,th in checks:
    ok=(v<=th if op=="<=" else v>=th)
    print(f"  {n:18s} {v:.12f} {op} {th:.3f} -> {'PASS' if ok else 'FAIL'}")
print("  V7 RULE RESULT:", "PASS" if v7pass else "FAIL")

# Reproduce original V7 simulate() gate exactly.
# Original reversal_candidates carries next_same_extreme based on session_id+direction.
rall=raw.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
if "session_id" not in rall.columns:
    raise SystemExit("Raw reversal_candidates has no session_id; cannot reproduce original supersession gate.")
rall["next_same_extreme_time"]=rall.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
oc=rall[(rall.time_ny==T)&(rall.direction.astype(str)==D)].iloc[0]
j=i+3; signal=one.iloc[j].time_ny
ticker_ok=str(one.iloc[j].ticker)==str(oc.ticker)
nextx=oc.next_same_extreme_time
superseded=pd.notna(nextx) and signal>=nextx
entry=float(one.iloc[j].open); stop=float(oc.extreme)-.25; risk=entry-stop
sim_ok=ticker_ok and not superseded and risk>0
print("\nORIGINAL V7 simulate() GATE")
print("  signal/entry time:",signal)
print("  next_same_extreme_time:",nextx)
print("  superseded:",superseded)
print("  ticker match:",ticker_ok,"| entry ticker:",one.iloc[j].ticker,"| candidate ticker:",oc.ticker)
print("  entry:",entry,"| stop:",stop,"| risk:",risk,"| risk>0:",risk>0)
print("  simulate gate before outcome:", "PASS" if sim_ok else "FAIL")

# Current live at boundary.
live_open=one.iloc[j].to_dict()
outs=[x for x in live.evaluate(closed,live_open=live_open) if pd.Timestamp(x["candidate_time_et"])==T and x["direction"]==D]
print("\nCURRENT LIVE FINAL AT 02:30:", "PRESENT" if outs else "ABSENT")
if outs: print("  live entry:",outs[0]["entry"],"| stop:",outs[0]["stop"],"| V15:",outs[0]["v15_score"])

print("\nFIRST EXACT REASON")
if not v7pass:
    print("  Original candidate fails the numeric V7 rule above.")
elif superseded:
    print("  ORIGINAL V7 REMOVES IT IN simulate(): a later same-session LONG extreme is already known to full-history V7.")
    print("  Current live cannot know that later extreme yet at 02:30, so it emits the earlier candidate.")
elif not ticker_ok:
    print("  Original V7 removes it on ticker mismatch.")
elif risk<=0:
    print("  Original V7 removes it because risk <= 0.")
else:
    print("  Numeric V7 + pre-outcome simulate gate both pass; absence from V7 artifact must be outcome-window/other artifact construction. Inspect next.")
print("\nREAD-ONLY. No strategy/data/report changed.")
