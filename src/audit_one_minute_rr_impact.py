#!/usr/bin/env python3
"""Compare frozen historical fills vs 1-minute causal-confirmation fills for the 75 Sep trades. READ ONLY."""
from pathlib import Path
import pandas as pd, numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/"data";TZ="America/New_York"
ONE=D/"audit_sep01_24_1m.parquet";REP=D/"reports/2026-09_trades.csv"
RRS=[1,2,3,4,5,6]
def norm(s):
 x=pd.to_datetime(s,errors="coerce");return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
one=pd.read_parquet(ONE);one["time_ny"]=norm(one.time_ny);one=one.sort_values("time_ny").reset_index(drop=True);idx=pd.Series(one.index,index=one.time_ny).to_dict()
tr=pd.read_csv(REP);tr["candidate_time"]=norm(tr.candidate_time);tr["entry_time"]=norm(tr.entry_time)
def outcome(j,d,entry,stop,rr,ticker):
 risk=entry-stop if d=="LONG" else stop-entry
 if risk<=0:return "INVALID"
 target=entry+rr*risk if d=="LONG" else entry-rr*risk
 for q in range(j,min(j+241,len(one))):
  b=one.iloc[q]
  if str(b.ticker)!=str(ticker):break
  sh=float(b.low)<=stop if d=="LONG" else float(b.high)>=stop
  th=float(b.high)>=target if d=="LONG" else float(b.low)<=target
  if sh:return "LOSS"
  if th:return "WIN"
 return "OPEN"
rows=[]
for _,t in tr.iterrows():
 j=idx.get(t.entry_time)
 if j is None or j+1>=len(one):continue
 d=str(t.direction).upper();ticker=str(one.iloc[j].ticker);orig_entry=float(t.entry);stop=float(t.stop)
 delayed_time=one.iloc[j+1].time_ny;delayed_entry=float(one.iloc[j+1].open)
 orisk=orig_entry-stop if d=="LONG" else stop-orig_entry
 drisk=delayed_entry-stop if d=="LONG" else stop-delayed_entry
 r={"candidate":t.candidate_time,"direction":d,"orig_time":t.entry_time,"delay_time":delayed_time,"orig_entry":orig_entry,"delay_entry":delayed_entry,"stop":stop,"orig_risk":orisk,"delay_risk":drisk,"entry_drift":delayed_entry-orig_entry,"valid_delayed":drisk>0}
 for rr in RRS:
  r[f"orig_{rr}R"]=outcome(j,d,orig_entry,stop,rr,ticker)
  r[f"delay_{rr}R"]=outcome(j+1,d,delayed_entry,stop,rr,ticker) if drisk>0 else "INVALID"
 rows.append(r)
x=pd.DataFrame(rows)
print("="*112);print("THE ICON — 75-TRADE RR / WIN-RATE IMPACT OF 1-MINUTE CAUSAL CONFIRMATION");print("="*112)
print("Trades compared:",len(x));print("Delayed entries still valid risk:",int(x.valid_delayed.sum()),"/",len(x))
print(f"Absolute entry drift: median={x.entry_drift.abs().median():.2f} pts | mean={x.entry_drift.abs().mean():.2f} | max={x.entry_drift.abs().max():.2f}")
print(f"Original risk: median={x.orig_risk.median():.2f} pts | Delayed risk: median={x.loc[x.valid_delayed,'delay_risk'].median():.2f} pts")
print("\nRR COMPARISON (stop-first, same canonical 241-minute window)")
for rr in RRS:
 a=x[f"orig_{rr}R"];b=x[f"delay_{rr}R"]
 def stat(s):
  w=int((s=="WIN").sum());l=int((s=="LOSS").sum());o=int((s=="OPEN").sum());iv=int((s=="INVALID").sum());res=w+l
  return w,l,o,iv,(100*w/res if res else np.nan)
 aw,al,ao,ai,awr=stat(a);bw,bl,bo,bi,bwr=stat(b)
 flips=int(((a=="WIN")&(b=="LOSS")).sum());resc=int(((a=="LOSS")&(b=="WIN")).sum())
 print(f"{rr}R | ORIGINAL W/L/O {aw}/{al}/{ao} WR {awr:.2f}% | DELAY W/L/O/I {bw}/{bl}/{bo}/{bi} WR {bwr:.2f}% | WIN->LOSS {flips} | LOSS->WIN {resc}")
print("\n3R TRADE CHANGES")
q=x[x.orig_3R!=x.delay_3R][["candidate","direction","orig_entry","delay_entry","stop","orig_risk","delay_risk","orig_3R","delay_3R"]]
print(q.to_string(index=False) if len(q) else "NONE")
print("\n4R TRADE CHANGES")
q=x[x.orig_4R!=x.delay_4R][["candidate","direction","orig_entry","delay_entry","stop","orig_risk","delay_risk","orig_4R","delay_4R"]]
print(q.to_string(index=False) if len(q) else "NONE")
print("\nREAD-ONLY. Production strategy, benchmark, thresholds, and source data unchanged.")
