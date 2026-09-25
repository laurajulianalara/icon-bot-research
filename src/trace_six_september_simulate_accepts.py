#!/usr/bin/env python3
"""THE ICON — Trace the 6 September extras accepted by original V7 simulate().

READ ONLY. No strategy changes. Traces each accepted extra through:
original V11 membership -> V8 -> V15 score -> V27 -> canonical validity -> Option2B daily cap.
"""
from pathlib import Path
import sys, bisect, json
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

P=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
V11=Path("data/v11_reversal_state_forensics.csv")
HISTTR=Path("data/reports/2026-09_trades.csv")
for p in [P,V11,HISTTR,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et_series(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)
def et_scalar(x):
    x=pd.Timestamp(x)
    return x.tz_localize(live.TZ) if x.tzinfo is None else x.tz_convert(live.TZ)
def key(t,d): return (int(et_scalar(t).tz_convert("UTC").value),str(d))

proof=pd.read_csv(P); proof["entry_time"]=et_series(proof.entry_time); proof["candidate_time"]=et_series(proof.candidate_time)
six=proof[proof.original_simulate_result.isin(["SIMULATE_ACCEPT_WIN","SIMULATE_ACCEPT_LOSS"])].copy().sort_values("entry_time")
print("Accepted extras to trace:",len(six))
if len(six)!=6: print("WARNING: expected 6; tracing what is present.")

v=pd.read_csv(V11); v["candidate_time_et"]=pd.to_datetime(v.candidate_time,utc=True).dt.tz_convert(live.TZ)
# Original current-period V11 was already the V8-surviving population.
vm={key(r.candidate_time_et,r.direction):r for _,r in v.iterrows()}

with open("data/icon_v15_pine_reference.json") as f: REF={k:sorted(float(x) for x in a) for k,a in json.load(f).items()}
SPEC=[("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]
TH=.145921011058; RTH=.576132; WTH=.183258
def rank(x,a):
    if not np.isfinite(x): return np.nan
    lo=bisect.bisect_left(a,float(x)); hi=bisect.bisect_right(a,float(x))
    return (lo+(hi-lo+1)/2)/len(a) if hi>lo else min(1,max(0,(lo+1)/len(a)))
def score(r):
    rq=(1-np.clip(float(r.m2_close_pos),0,1))*(1-np.clip(float(r.wick_percent),0,1))
    ri=-float(r.m2_move_atr); rec=float(r.early_reclaim_atr); sw=float(r.sweep_atr); wick=float(r.wick_percent); cp=float(r.m2_close_pos)
    f={"rejection_quality":rq,"reversal_impulse":ri,"reclaim_to_sweep":rec/(abs(sw)+.05),
       "impulse_to_reclaim":ri/(abs(rec)+.05),"reclaim_x_wick":rec*wick,"close_x_reclaim":cp*rec,
       "sweep_minus_reclaim":sw-rec,"impulse_minus_reclaim":ri-rec}
    f["quality_balance"]=f["rejection_quality"]*f["impulse_to_reclaim"]/(1+f["reclaim_to_sweep"])
    parts=[]
    for col,hi,w in SPEC:
        z=rank(f[col],REF[col]); parts += [(z if hi else 1-z)]*w
    return float(np.mean(parts)),f

# Historical final Option2B trades reveal actual cap occupancy/order for each day.
ht=pd.read_csv(HISTTR); ht["entry_time"]=et_series(ht.entry_time)
rows=[]
for _,x in six.iterrows():
    vr=vm.get(key(x.candidate_time,x.direction))
    in_v11=vr is not None; sc=np.nan; v15=False; v27=False; rxw=np.nan
    if in_v11:
        sc,f=score(vr); v15=bool(sc>=TH); rxw=f["reclaim_x_wick"]
        v27=bool(not(float(vr.early_reclaim_atr)>=RTH and rxw>=WTH))
    day=x.entry_time.date()
    daytr=ht[ht.entry_time.dt.date==day].sort_values("entry_time")
    cap_full=len(daytr)>=6
    sixth=daytr.iloc[5].entry_time if cap_full else pd.NaT
    before_sixth=bool(cap_full and x.entry_time>sixth)
    if not in_v11: final="REMOVED_BEFORE_V11_AFTER_SIMULATE"
    elif not v15: final="REJECTED_V15_SCORE"
    elif not v27: final="REJECTED_V27"
    elif before_sixth: final="REJECTED_OPTION2B_DAILY_CAP"
    else: final="PASSES_V11_V15_V27__TRACE_CANONICAL/MATCHING"
    rows.append({"date":day,"entry_time":x.entry_time,"candidate_time":x.candidate_time,"session":x.session,
      "direction":x.direction,"simulate":x.original_simulate_result,"in_original_v11":in_v11,
      "v15_score":sc,"v15_pass":v15,"early_reclaim_atr":float(vr.early_reclaim_atr) if in_v11 else np.nan,
      "reclaim_x_wick":rxw,"v27_pass":v27,"historical_trades_that_day":len(daytr),
      "historical_6th_entry":sixth,"entry_after_historical_6th":before_sixth,"diagnosis":final})
out=pd.DataFrame(rows)
print("\nTRACE RESULT")
print(out.to_string(index=False))
print("\nDIAGNOSIS")
print(out.diagnosis.value_counts().to_string())
save=Path("data/reports/2026-09_six_simulate_accept_trace.csv"); out.to_csv(save,index=False)
print("\nSaved:",save)
print("READ ONLY — no Option2B strategy code, thresholds, or frozen data changed.")
