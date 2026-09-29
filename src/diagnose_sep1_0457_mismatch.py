#!/usr/bin/env python3
"""THE ICON — microscope diagnostic for Sep 1 04:57 LONDON LONG.

READ-ONLY. No strategy/filter/threshold/data/report/execution changes.
Compares the full-data reporter view with the exact causal view available
at the 05:00 entry boundary and prints the first reason the live engine
cannot emit the benchmark trade.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ; NEED=live.NEED
TARGET=pd.Timestamp("2026-09-01 04:57",tz=TZ)
ENTRY=pd.Timestamp("2026-09-01 05:00",tz=TZ)
DAY=pd.Timestamp("2026-09-01",tz=TZ)
V11=Path("data/v11_reversal_state_forensics.csv")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

frames=[]
h=pd.read_parquet(live.HIST)[NEED].copy(); h["time_ny"]=et(h.time_ny); frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(NEED).issubset(q.columns): continue
        q=q[NEED].copy(); q["time_ny"]=et(q.time_ny); frames.append(q)
    except Exception: pass
one=(pd.concat(frames,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))
one=one[(one.time_ny>=DAY-pd.Timedelta(days=3))&(one.time_ny<DAY+pd.Timedelta(days=1))].reset_index(drop=True)

def prep(x):
    x=x.copy().sort_values("time_ny").reset_index(drop=True)
    pc=x.close.shift(1)
    x["atr1"]=pd.concat([x.high-x.low,(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
    return x

def find_candidate(x):
    c=live.build_candidates(x)
    if c.empty: return None
    z=c[(c.time_ny==TARGET)&(c.direction=="LONG")]
    return None if z.empty else z.iloc[0]

def trace(label,x,c):
    print("\n"+"="*90); print(label); print("="*90)
    if c is None:
        print("CANDIDATE: MISSING")
        return {"stage":"CANDIDATE_MISSING"}
    print("CANDIDATE: PRESENT")
    print("extreme:",float(c.extreme),"candidate_atr:",float(c.atr),"sweep_distance:",float(c.sweep_distance),
          "wick_percent:",float(c.wick_percent),"next_same_extreme_time:",c.next_same_extreme_time)
    idx=pd.Series(x.index,index=x.time_ny).to_dict(); i=idx.get(TARGET)
    if i is None: print("FAIL: target 1m row missing"); return {"stage":"TARGET_ROW_MISSING"}
    a=float(x.iloc[i].atr1)
    print("1m ATR at candidate:",a)
    if i<20 or not np.isfinite(a) or a<=0: print("FAIL: ATR/context"); return {"stage":"ATR"}
    vals={}; sg=1
    for k in [1,2]:
        b=x.iloc[i+k]; pre=x.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(x.iloc[i].close))/a
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp)
        vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)>0)).sum())
    print("V7/V8 values:",vals)
    v7=vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912
    print("V7:",v7)
    first2=x.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a
    v8=reclaim<=.90 and vals["m2_close_pos"]<=.80 and float(c.wick_percent)<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4
    print("reclaim:",reclaim,"V8:",v8)
    rq=(1-min(max(vals["m2_close_pos"],0),1))*(1-min(max(float(c.wick_percent),0),1))
    ri=-vals["m2_move_atr"]; ca=float(c.atr)
    sa=float(c.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
    rts=reclaim/(abs(sa)+.05); itr=ri/(abs(reclaim)+.05); rxw=reclaim*float(c.wick_percent)
    f={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,"reversal_impulse":ri,
       "reclaim_x_wick":rxw,"close_x_reclaim":vals["m2_close_pos"]*reclaim,"sweep_minus_reclaim":sa-reclaim,
       "impulse_minus_reclaim":ri-reclaim,"quality_balance":rq*itr/(1+rts)}
    sc=live.score(f)
    print("live forward V15 score:",sc,"threshold:",live.V15_THRESHOLD,"score_pass:",bool(np.isfinite(sc) and sc>=live.V15_THRESHOLD))
    v27=not(reclaim>=live.RTH and rxw>=live.WTH)
    print("V27:",v27,"reclaim_x_wick:",rxw,"RTH:",live.RTH,"WTH:",live.WTH)
    if not v7:return {"stage":"V7"}
    if not v8:return {"stage":"V8"}
    if not np.isfinite(sc) or sc<live.V15_THRESHOLD:return {"stage":"LIVE_FORWARD_V15","score":sc}
    if not v27:return {"stage":"V27"}
    return {"stage":"SURVIVES_FILTERS","score":sc}

full=prep(one)
report_c=find_candidate(full)

# Exact causal state at 05:00: bars through 04:59 are closed; 05:00 is live_open.
pos=full.index[full.time_ny==ENTRY]
if not len(pos): raise SystemExit("Missing 05:00 entry row")
p=int(pos[-1])
closed=prep(full.loc[:p-1,NEED].copy())
op=full.loc[p,NEED].to_dict()
causal_c=find_candidate(closed)

print("="*90)
print("THE ICON — SEP 1 04:57 -> 05:00 MISMATCH MICROSCOPE")
print("="*90)
print("READ-ONLY. No strategy/filter/threshold/data/report/execution changes.")
print("Target: 2026-09-01 04:57 LONDON LONG | expected entry boundary: 05:00 ET")
print("Closed causal data ends:",closed.time_ny.max())
print("live_open:",op["time_ny"],"open:",op["open"])

r1=trace("FULL-DATA / REPORTER VIEW",full,report_c)
r2=trace("CAUSAL VIEW AT 05:00",closed,causal_c)

# Frozen historical V15 membership check.
ref=pd.read_csv(V11); ref["candidate_time"]=pd.to_datetime(ref["candidate_time"],utc=True)
ref["candidate_time_et"]=ref["candidate_time"].dt.tz_convert(TZ)
ref["reclaim_x_wick"]=ref.early_reclaim_atr*ref.wick_percent
ref["close_x_reclaim"]=ref.m2_close_pos*ref.early_reclaim_atr
ref["sweep_minus_reclaim"]=ref.sweep_atr-ref.early_reclaim_atr
ref["impulse_minus_reclaim"]=ref.reversal_impulse-ref.early_reclaim_atr
ref["quality_balance"]=ref.rejection_quality*ref.impulse_to_reclaim/(1+ref.reclaim_to_sweep)
parts=[]
for col,hi,w in live.SPEC:
    rr=ref[col].rank(pct=True); parts += [(rr if hi else 1-rr)]*w
ref["score"]=pd.concat(parts,axis=1).mean(axis=1)
thr=ref.score.quantile(.07); hr=ref[ref.score>=thr].copy()
hr["date_et"]=hr.candidate_time_et.dt.date; hr=hr.sort_values("candidate_time_et").reset_index(drop=True)
hr["trade_num_day"]=hr.groupby("date_et").cumcount()+1; hr=hr[hr.trade_num_day<=6]
allowed=set(zip(hr.candidate_time_et.astype(str),hr.direction.astype(str)))
print("\nFROZEN HISTORICAL V15 MEMBERSHIP:",(str(TARGET),"LONG") in allowed)

raw=live.evaluate(closed,live_open=op)
target=[x for x in raw if pd.Timestamp(x["candidate_time_et"])==TARGET and x["direction"]=="LONG"]
print("RAW live.evaluate EMITS TARGET:",bool(target))
if target: print("RAW EMISSION:",target[0])

print("\n"+"="*90)
print("DIAGNOSIS")
print("="*90)
if causal_c is None and report_c is not None:
    print("FIRST DIVERGENCE: candidate construction. Full-data sees 04:57 LONG; causal 05:00 view does not.")
    print("Likely focus: session-end 3m candle completeness / candidate availability at the entry boundary.")
elif r2["stage"]=="LIVE_FORWARD_V15" and (str(TARGET),"LONG") in allowed:
    print("FIRST DIVERGENCE: frozen historical V15 says ALLOWED, but raw live forward V15 scoring rejects it.")
    print("This is the same historical-membership-vs-forward-score class already identified.")
elif not target:
    print("Candidate exists causally and trace reached:",r2["stage"],"but live.evaluate still did not emit it.")
    print("Inspect entry-boundary, supersession, ticker, or risk checks next.")
else:
    print("Raw live engine emits the target. Any remaining miss is outside evaluate(), such as parity membership/cap handling.")
print("\nDiagnostic complete. No files changed.")
