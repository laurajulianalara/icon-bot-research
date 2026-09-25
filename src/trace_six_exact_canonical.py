#!/usr/bin/env python3
"""THE ICON — exact final-canonical trace for the 6 September simulate-accepted extras.
READ ONLY. Reconstructs the CURRENT-period Option2B selector exactly as
v2b_full_two_year_test.py does, then records the first gate where each target
fails. No strategy/data files are modified.
"""
from pathlib import Path
import sys,bisect,json
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TARGET=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
ONE=Path("data/mnq_continuous_1m.parquet")
CAND=Path("data/reversal_candidates.parquet")
FEAT=Path("data/v11_reversal_state_forensics.csv")
for p in [TARGET,ONE,CAND,FEAT,Path("data/icon_v15_pine_reference.json")]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

TZ="America/New_York"; TH=.145921011058; RTH=.576132; WTH=.183258
WEIGHTS=[("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),
("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),
("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]
with open("data/icon_v15_pine_reference.json") as f: REF={k:sorted(float(x) for x in v) for k,v in json.load(f).items()}

def et_series(s):
    x=pd.to_datetime(s); return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
def tkey(x):
    x=pd.Timestamp(x); x=x.tz_localize(TZ) if x.tzinfo is None else x.tz_convert(TZ)
    return int(x.tz_convert("UTC").value)
def rank(v,a):
    if not np.isfinite(v): return np.nan
    lo=bisect.bisect_left(a,float(v)); hi=bisect.bisect_right(a,float(v))
    return (lo+(hi-lo+1)/2)/len(a) if hi>lo else min(1,max(0,(lo+1)/len(a)))
def prep(q):
    q=q.copy()
    q["rejection_quality"]=(1-q.m2_close_pos.clip(0,1))*(1-q.wick_percent.clip(0,1))
    q["reversal_impulse"]=-q.m2_move_atr
    q["reclaim_to_sweep"]=q.early_reclaim_atr/(q.sweep_atr.abs()+.05)
    q["impulse_to_reclaim"]=q.reversal_impulse/(q.early_reclaim_atr.abs()+.05)
    q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
    q["close_x_reclaim"]=q.m2_close_pos*q.early_reclaim_atr
    q["sweep_minus_reclaim"]=q.sweep_atr-q.early_reclaim_atr
    q["impulse_minus_reclaim"]=q.reversal_impulse-q.early_reclaim_atr
    q["quality_balance"]=q.rejection_quality*q.impulse_to_reclaim/(1+q.reclaim_to_sweep)
    parts=[]
    for col,hi,w in WEIGHTS:
        r=q[col].map(lambda v:rank(v,REF[col])); parts += [(r if hi else 1-r)]*w
    q["score"]=pd.concat(parts,axis=1).mean(axis=1); return q

p=pd.read_csv(TARGET); p["entry_time"]=et_series(p.entry_time); p["candidate_time"]=et_series(p.candidate_time)
targets=p[p.original_simulate_result.isin(["SIMULATE_ACCEPT_WIN","SIMULATE_ACCEPT_LOSS"])].copy()
T={(tkey(r.candidate_time),str(r.direction)) for _,r in targets.iterrows()}

one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); q=pd.read_csv(FEAT)
one["time_ny"]=pd.to_datetime(one.time_ny); cand["time_ny"]=pd.to_datetime(cand.time_ny)
if one.time_ny.dt.tz is None: one["time_ny"]=one.time_ny.dt.tz_localize(TZ)
else: one["time_ny"]=one.time_ny.dt.tz_convert(TZ)
if cand.time_ny.dt.tz is None: cand["time_ny"]=cand.time_ny.dt.tz_localize(TZ)
else: cand["time_ny"]=cand.time_ny.dt.tz_convert(TZ)
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True); q["candidate_time_et"]=q.candidate_time.dt.tz_convert(TZ)
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
q=prep(q)
idx=pd.Series(one.index,index=one.time_ny).to_dict()
cm={(tkey(r.time_ny),str(r.direction)):r for _,r in cand.iterrows()}
qm={(tkey(r.candidate_time_et),str(r.direction)):r for _,r in q.iterrows()}

rows=[]
for _,x in targets.sort_values("entry_time").iterrows():
    k=(tkey(x.candidate_time),str(x.direction)); qr=qm.get(k); c=cm.get(k)
    reason="PASS_ALL_CANONICAL_GATES"; score=np.nan; signal=pd.NaT; nxt=pd.NaT; risk=np.nan
    if qr is None: reason="NO_V11_KEY_MATCH"
    else:
        score=float(qr.score)
        if score<TH: reason="V15_REJECT"
        elif float(qr.early_reclaim_atr)>=RTH and float(qr.reclaim_x_wick)>=WTH: reason="V27_REJECT"
        elif c is None: reason="NO_CANONICAL_CANDIDATE_MATCH"
        else:
            i=idx.get(c.time_ny)
            if i is None: reason="NO_1M_INDEX"
            elif i+3>=len(one): reason="NO_SIGNAL_BAR"
            else:
                j=i+3; signal=one.iloc[j].time_ny; nxt=c.next_same_extreme_time
                if one.iloc[j].ticker!=c.ticker: reason="TICKER_MISMATCH"
                elif pd.notna(nxt) and signal>=nxt: reason="CANONICAL_SUPERSEDED"
                else:
                    entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
                    risk=entry-stop if c.direction=="LONG" else stop-entry
                    if risk<=0: reason="INVALID_RISK"
    rows.append({"entry_time_from_causal":x.entry_time,"candidate_time":x.candidate_time,"session":x.session,
      "direction":x.direction,"simulate":x.original_simulate_result,"v11_key_match":qr is not None,
      "canonical_candidate_match":c is not None,"score":score,"canonical_signal_time":signal,
      "next_same_extreme_time":nxt,"risk":risk,"first_final_gate_result":reason})

out=pd.DataFrame(rows)
print("="*130); print("THE ICON — SIX-TRADE EXACT FINAL CANONICAL TRACE"); print("="*130)
print(out.to_string(index=False))
print("\nRESULT"); print(out.first_final_gate_result.value_counts().to_string())

# If all pass canonical gates, replay the exact Option2B chronological daily cap
# and explicitly report whether each target is selected.
qq=q[(q.score>=TH)&~((q.early_reclaim_atr>=RTH)&(q.reclaim_x_wick>=WTH))].sort_values("candidate_time_et")
daily={}; selected=set(); cap_reject=set()
for _,r in qq.iterrows():
    k=(tkey(r.candidate_time_et),str(r.direction)); c=cm.get(k)
    if c is None: continue
    i=idx.get(c.time_ny)
    if i is None or i+3>=len(one): continue
    j=i+3; signal=one.iloc[j].time_ny
    if one.iloc[j].ticker!=c.ticker: continue
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time: continue
    entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0: continue
    day=signal.tz_convert(TZ).date()
    if daily.get(day,0)>=6:
        if k in T: cap_reject.add(k)
        continue
    daily[day]=daily.get(day,0)+1
    if k in T: selected.add(k)

out["exact_option2b_selected"]=[(tkey(r.candidate_time),str(r.direction)) in selected for _,r in out.iterrows()]
out["exact_option2b_cap_rejected"]=[(tkey(r.candidate_time),str(r.direction)) in cap_reject for _,r in out.iterrows()]
print("\nEXACT OPTION2B FINAL SELECTION")
print(out[["entry_time_from_causal","candidate_time","session","direction","first_final_gate_result","exact_option2b_selected","exact_option2b_cap_rejected"]].to_string(index=False))
save=Path("data/reports/2026-09_six_exact_canonical_trace.csv"); out.to_csv(save,index=False)
print("\nSaved:",save); print("READ ONLY — no strategy/data files changed.")
