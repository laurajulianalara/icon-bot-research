#!/usr/bin/env python3
"""THE ICON — Sep 1 V11/V15 provenance debugger.

READ ONLY. No strategy changes.

Purpose:
For every Sep 1 causal signal, determine whether its candidate exists in:
  A) the full-day candidate generator
  B) the frozen original V11 population
and, when absent from V11, compare its causal V7/V8 features against the
frozen V7/V8 rules. This tells us whether "missing V11" means an earlier
V7/V8 rejection or a provenance/data-generation mismatch.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY=pd.Timestamp("2026-09-01").date()
CAUSAL=Path("data/reports/2026-09_true_bar_by_bar.csv")
HISTTR=Path("data/reports/2026-09_trades.csv")
V11=Path("data/v11_reversal_state_forensics.csv")

for p in [CAUSAL,HISTTR,V11,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

ca=pd.read_csv(CAUSAL)
ca["entry_time"]=et(ca.entry_time_et); ca["candidate_time"]=et(ca.candidate_time_et)
ca=ca[ca.entry_time.dt.date==DAY].copy().sort_values("entry_time")

ht=pd.read_csv(HISTTR); ht["entry_time"]=et(ht.entry_time)
ht=ht[ht.entry_time.dt.date==DAY].copy()
hkeys=set(zip(ht.entry_time.astype(str),ht.session.astype(str),ht.direction.astype(str)))

ref=pd.read_csv(V11)
ref["candidate_time"]=pd.to_datetime(ref.candidate_time,utc=True)
ref["candidate_time_et"]=ref.candidate_time.dt.tz_convert(live.TZ)
refkeys=set(zip(ref.candidate_time_et.astype(str),ref.direction.astype(str)))

# Load enough raw 1m data to reconstruct Sep 1 exactly and preserve ATR context.
one=pd.read_parquet(live.HIST)[live.NEED].copy(); one["time_ny"]=et(one.time_ny)
start=pd.Timestamp("2026-08-29",tz=live.TZ); end=pd.Timestamp("2026-09-02",tz=live.TZ)
one=one[(one.time_ny>=start)&(one.time_ny<end)].sort_values("time_ny").reset_index(drop=True)
pc=one.close.shift(1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()
cand=live.build_candidates(one)
cmap={(str(r.time_ny),str(r.direction)):r for _,r in cand.iterrows()}

rows=[]
for _,x in ca.iterrows():
    ck=(str(x.candidate_time),str(x.direction))
    c=cmap.get(ck)
    in_v11=ck in refkeys
    original=(str(x.entry_time),str(x.session),str(x.direction)) in hkeys

    rec={"entry_time":x.entry_time,"candidate_time":x.candidate_time,"session":x.session,
         "direction":x.direction,"original":original,"in_full_day_candidate":c is not None,
         "in_original_v11":in_v11}

    if c is None:
        rec["first_failure"]="CANDIDATE PROVENANCE MISMATCH"
        rows.append(rec); continue

    i=idx.get(c.time_ny)
    if i is None or i<20 or i+3>=len(one):
        rec["first_failure"]="INDEX/CONTEXT"; rows.append(rec); continue

    a=float(one.iloc[i].atr1); sg=1 if c.direction=="LONG" else -1
    vals={}
    for k in [1,2]:
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())

    first2=one.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first2.iloc[-1].close))/a

    v7a=vals["m1_move_atr"]<=.300
    v7b=vals["m1_close_pos"]>=.140
    v7c=vals["m2_close_pos"]<=.912
    v7=v7a and v7b and v7c
    v8a=reclaim<=.90
    v8b=vals["m2_close_pos"]<=.80
    v8c=float(c.wick_percent)<=.60
    v8d=vals["m2_move_atr"]<=.15
    v8e=vals["m2_dir_bars5"]<=4
    v8=v8a and v8b and v8c and v8d and v8e

    if not v7:
        fail="V7"
    elif not v8:
        fail="V8"
    elif not in_v11:
        fail="PASSES CURRENT V7/V8 BUT ABSENT FROM ORIGINAL V11"
    else:
        fail="REACHES ORIGINAL V11"

    rec.update({
      "m1_move_atr":vals["m1_move_atr"],"m1_close_pos":vals["m1_close_pos"],
      "m2_close_pos":vals["m2_close_pos"],"m2_move_atr":vals["m2_move_atr"],
      "m2_dir_bars5":vals["m2_dir_bars5"],"reclaim":reclaim,
      "wick_percent":float(c.wick_percent),"v7_pass":v7,"v8_pass":v8,
      "first_failure":fail})
    rows.append(rec)

out=pd.DataFrame(rows)
print("="*118)
print("THE ICON — SEP 1 V11/V15 PROVENANCE DEBUG")
print("="*118)
print(f"Causal signals: {len(out)} | historical originals among them: {int(out.original.sum())} | extras: {int((~out.original).sum())}")
print("\nEXTRAS — FIRST DIFFERENCE")
print(out[~out.original].first_failure.value_counts().to_string())
print("\nDETAIL")
cols=["entry_time","candidate_time","session","direction","original","in_full_day_candidate","v7_pass","v8_pass","in_original_v11","first_failure"]
print(out[cols].to_string(index=False))
print("\nIMPORTANT")
print("If extras say V7 or V8, the live/current reconstruction is disagreeing with an earlier frozen filter.")
print("If extras say PASSES CURRENT V7/V8 BUT ABSENT FROM ORIGINAL V11, then V11 provenance itself differs and we must inspect how the original V11 file was created before changing live code.")
print("READ ONLY — no Option 2B rules, thresholds, or live files changed.")
