#!/usr/bin/env python3
"""THE ICON — Sep 21 04:42 benchmark feature-parity diagnostic.

READ-ONLY. No strategy/data mutation.
Compares the exact 04:42 LONDON SHORT candidate using:
  A) full historical context
  B) causal context available at the 04:45 entry boundary

The goal is to identify the FIRST field/stage that differs.
"""
from pathlib import Path
import sys, bisect
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

T=pd.Timestamp("2026-09-21 04:42:00",tz=live.TZ)
ENTRY=T+pd.Timedelta(minutes=3)

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

frames=[]
h=pd.read_parquet(live.HIST)[live.NEED].copy();h["time_ny"]=et(h.time_ny);frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(live.NEED).issubset(q.columns):continue
        q=q[live.NEED].copy();q["time_ny"]=et(q.time_ny);frames.append(q)
    except Exception:pass
all1=(pd.concat(frames,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last")
      .sort_values("time_ny").reset_index(drop=True))
all1=all1[(all1.time_ny>=T-pd.Timedelta(days=4))&(all1.time_ny<T+pd.Timedelta(hours=2))].copy()

def inspect(label, one):
    one=one.copy().sort_values("time_ny").reset_index(drop=True)
    pc=one.close.shift(1)
    one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
    cand=live.build_candidates(one)
    x=cand[(cand.time_ny==T)&(cand.session=="LONDON")&(cand.direction=="SHORT")]
    print("\n"+"="*88);print(label);print("="*88)
    if x.empty:
        print("CANDIDATE: MISSING");return None
    c=x.iloc[0]
    idx=pd.Series(one.index,index=one.time_ny).to_dict();i=idx.get(T)
    print("candidate_time",c.time_ny)
    print("extreme",float(c.extreme))
    print("candidate_atr_3m",float(c.atr))
    print("sweep_distance",float(c.sweep_distance))
    print("wick_percent",float(c.wick_percent))
    print("next_same_extreme_time",c.next_same_extreme_time)
    if i is None:
        print("1m row: MISSING");return None
    a=float(one.iloc[i].atr1);sg=-1;vals={}
    print("atr1",a)
    for k in [1,2]:
        if i+k>=len(one):
            print(f"m{k}: MISSING");return None
        b=one.iloc[i+k];pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(1-cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
    for k,v in vals.items():print(k,v)
    v7=vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912
    first2=one.iloc[i+1:i+3]
    reclaim=(float(c.extreme)-float(first2.iloc[-1].close))/a
    v8=(reclaim<=.90 and vals["m2_close_pos"]<=.80 and float(c.wick_percent)<=.60
        and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4)
    rq=(1-min(max(vals["m2_close_pos"],0),1))*(1-min(max(float(c.wick_percent),0),1))
    ri=-vals["m2_move_atr"];ca=float(c.atr)
    sa=float(c.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
    rts=reclaim/(abs(sa)+.05);itr=ri/(abs(reclaim)+.05);rxw=reclaim*float(c.wick_percent)
    feats={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,
           "reversal_impulse":ri,"reclaim_x_wick":rxw,"close_x_reclaim":vals["m2_close_pos"]*reclaim,
           "sweep_minus_reclaim":sa-reclaim,"impulse_minus_reclaim":ri-reclaim,
           "quality_balance":rq*itr/(1+rts)}
    sc=live.score(feats)
    v27=not(reclaim>=live.RTH and rxw>=live.WTH)
    print("reclaim",reclaim);print("sweep_atr",sa)
    for k,v in feats.items():print(k,v)
    print("V7",v7);print("V8",v8);print("V15_score",sc,"threshold",live.V15_THRESHOLD,"pass",bool(np.isfinite(sc) and sc>=live.V15_THRESHOLD))
    print("V27",v27)
    return {"candidate":c,"atr1":a,**vals,"reclaim":reclaim,"sweep_atr":sa,**feats,
            "V7":v7,"V8":v8,"V15_score":sc,"V27":v27}

hist=inspect("A) FULL HISTORICAL CONTEXT",all1)
causal_closed=all1[all1.time_ny<ENTRY].copy()
causal=inspect("B) CAUSAL CONTEXT AVAILABLE AT 04:45",causal_closed)

print("\n"+"="*88);print("C) FIELD-BY-FIELD DIFFERENCES");print("="*88)
if hist is None or causal is None:
    print("Cannot compare because candidate is missing in one context.")
else:
    keys=[k for k in hist if k!="candidate"]
    diffs=0
    for k in keys:
        a,b=hist[k],causal[k]
        if isinstance(a,(bool,np.bool_)) or isinstance(b,(bool,np.bool_)):
            same=bool(a)==bool(b)
        else:
            try:same=(pd.isna(a) and pd.isna(b)) or np.isclose(float(a),float(b),rtol=0,atol=1e-12,equal_nan=True)
            except Exception:same=str(a)==str(b)
        if not same:
            diffs+=1;print(f"DIFF {k}: historical={a} | causal={b}")
    if diffs==0:print("ALL COMPUTED FILTER FEATURES MATCH.")

print("\nD) LIVE.EVALUATE AT 04:45")
op=all1[all1.time_ny==ENTRY]
sigs=live.evaluate(causal_closed.tail(6500),live_open=op.iloc[0][live.NEED].to_dict()) if not op.empty else []
for x in sigs:
    if x["session"]=="LONDON" and x["direction"]=="SHORT":
        print(x)
if not any(pd.Timestamp(x["candidate_time_et"])==T and pd.Timestamp(x["entry_time_et"])==ENTRY for x in sigs):
    print("04:42 -> 04:45 NOT EMITTED")

print("\nREAD-ONLY: no strategy thresholds, reports, or market data changed.")


# ------------------------------------------------------------------
# E. POST-FILTER DROP TRACE
# Reproduce evaluate() gates after V27 and print exactly where target dies.
# ------------------------------------------------------------------
print("\n"+"="*88);print("E) POST-FILTER DROP TRACE — WHY 04:42 DOES NOT APPEND");print("="*88)
one=causal_closed.copy().sort_values("time_ny").reset_index(drop=True)
cand=live.build_candidates(one)
x=cand[(cand.time_ny==T)&(cand.session=="LONDON")&(cand.direction=="SHORT")]
if x.empty:
    print("DROP: target candidate is absent from build_candidates(causal_closed)")
else:
    cc=x.iloc[0]
    idx=pd.Series(one.index,index=one.time_ny).to_dict()
    i=idx.get(cc.time_ny)
    print("candidate present:",cc.time_ny)
    print("i =",i,"len(one) =",len(one),"i+3 =",None if i is None else i+3)
    if i is None:
        print("DROP: candidate timestamp has no matching 1m row")
    else:
        print("evaluate pre-gate i+3>=len(one):",i+3>=len(one))
        if i+3>=len(one):
            print(">>> DROP FOUND: evaluate() exits BEFORE it reaches the live_open fallback.")
            print("Current code has: if i is None or i<20 or i+3>=len(one): continue")
            print("But at a true live entry boundary, i+3 == len(one) is EXPECTED and legal when live_open exists.")
        else:
            j=i+3
            print("j row exists historically:",one.iloc[j].time_ny)
        j=i+3
        print("live_open timestamp:",ENTRY)
        print("Would live_open branch be legal?",j==len(one))
        print("next_same_extreme_time:",cc.next_same_extreme_time)
        if j==len(one):
            signal=ENTRY
            print("supersession would reject?",bool(pd.notna(cc.next_same_extreme_time) and signal>=cc.next_same_extreme_time))
            print("ticker matches?",bool(op.iloc[0].ticker==cc.ticker) if not op.empty else "NO OPEN ROW")
            entry=float(op.iloc[0].open) if not op.empty else np.nan
            stop=float(cc.extreme)+.25
            risk=stop-entry
            print("entry",entry,"stop",stop,"risk",risk,"risk>0",risk>0)
            if risk>0:
                print(">>> If the premature i+3>=len(one) gate is removed/adjusted, this candidate reaches append conditions.")

print("\nDIAGNOSTIC ONLY — live strategy file was NOT changed.")
