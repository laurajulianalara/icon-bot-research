#!/usr/bin/env python3
"""Compare multiple causal execution methods after 1-minute supersession confirmation. READ ONLY.

All methods wait until T+4, so the T+3 minute is completed and the supersession decision is causal.
No method uses data after its actual fill to decide whether/where to enter.
"""
from pathlib import Path
import pandas as pd, numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/"data";TZ="America/New_York"
ONE=D/"audit_sep01_24_1m.parquet";REP=D/"reports/2026-09_trades.csv";RRS=[3,4]
def norm(s):
 x=pd.to_datetime(s,errors="coerce");return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
one=pd.read_parquet(ONE);one["time_ny"]=norm(one.time_ny);one=one.sort_values("time_ny").reset_index(drop=True);idx=pd.Series(one.index,index=one.time_ny).to_dict()
tr=pd.read_csv(REP);tr["candidate_time"]=norm(tr.candidate_time);tr["entry_time"]=norm(tr.entry_time)

# method -> (max wait minutes after confirmation, max adverse entry slippage in points vs original)
METHODS={
 "MKT_T4":(0,None),
 "RETEST_1M":(1,0.0),
 "RETEST_3M":(3,0.0),
 "RETEST_5M":(5,0.0),
 "CAP2_3M":(3,2.0),
 "CAP4_3M":(3,4.0),
 "CAP6_3M":(3,6.0),
 "CAP4_5M":(5,4.0),
 "CAP6_5M":(5,6.0),
}
def fill_for(j,d,orig,stop,maxwait,cap):
 # Confirmation is available at open of j+1 (T+4).
 start=j+1
 if start>=len(one):return None
 if maxwait==0:return start,float(one.iloc[start].open)
 # A limit/retest order is placed only AFTER confirmation at T+4.
 # cap=0 => original entry. cap>0 => permit up to cap pts worse than original.
 limit=orig if cap==0 else (orig+cap if d=="LONG" else orig-cap)
 # If T+4 opens at a price already at/better than limit, fill at open (marketable limit).
 op=float(one.iloc[start].open)
 if (d=="LONG" and op<=limit) or (d=="SHORT" and op>=limit):return start,op
 end=min(start+maxwait,len(one)-1)
 for q in range(start,end+1):
  b=one.iloc[q]
  if d=="LONG" and float(b.low)<=limit:return q,limit
  if d=="SHORT" and float(b.high)>=limit:return q,limit
 return None
def outcome(fi,d,entry,stop,rr,ticker):
 risk=entry-stop if d=="LONG" else stop-entry
 if risk<=0:return "INVALID"
 target=entry+rr*risk if d=="LONG" else entry-rr*risk
 for q in range(fi,min(fi+241,len(one))):
  b=one.iloc[q]
  if str(b.ticker)!=ticker:break
  sh=float(b.low)<=stop if d=="LONG" else float(b.high)>=stop
  th=float(b.high)>=target if d=="LONG" else float(b.low)<=target
  if sh:return "LOSS" # conservative same-bar ordering
  if th:return "WIN"
 return "OPEN"

rows=[]
for _,t in tr.iterrows():
 j=idx.get(t.entry_time)
 if j is None:continue
 d=str(t.direction).upper();orig=float(t.entry);stop=float(t.stop);ticker=str(one.iloc[j].ticker)
 for name,(wait,cap) in METHODS.items():
  f=fill_for(j,d,orig,stop,wait,cap)
  r={"method":name,"candidate":t.candidate_time,"direction":d}
  if f is None:
   r.update(filled=False,entry=np.nan,risk=np.nan,drift=np.nan,wait=np.nan)
   for rr in RRS:r[f"{rr}R"]="NO_FILL"
  else:
   fi,e=f;risk=e-stop if d=="LONG" else stop-e
   r.update(filled=True,entry=e,risk=risk,drift=e-orig,wait=fi-j)
   for rr in RRS:r[f"{rr}R"]=outcome(fi,d,e,stop,rr,ticker)
  rows.append(r)
x=pd.DataFrame(rows)
print("="*118);print("THE ICON — MULTI-METHOD CAUSAL EXECUTION TEST | 75 FROZEN SEPTEMBER TRADES");print("="*118)
print("All methods make the keep/reject decision only after the T+3 entry minute is completed.")
print("Retest/capped-limit orders are placed at T+4; therefore they do NOT assume a retroactive historical fill.\n")
print(f"{'METHOD':<12} {'FILLS':>7} {'NOFILL':>7} {'INV':>5} {'MED|DRIFT|':>11} {'MED RISK':>9} {'3R W/L/O':>13} {'3R WR':>8} {'4R W/L/O':>13} {'4R WR':>8}")
print("-"*118)
for name in METHODS:
 q=x[x.method==name];fills=int(q.filled.sum());nf=len(q)-fills;inv=int(((q["3R"]=="INVALID")|(q["4R"]=="INVALID")).sum())
 drift=q.loc[q.filled,"drift"].abs().median();risk=q.loc[q.filled & (q.risk>0),"risk"].median()
 vals=[]
 for rr in RRS:
  s=q[f"{rr}R"];w=int((s=="WIN").sum());l=int((s=="LOSS").sum());o=int((s=="OPEN").sum());den=w+l;wr=100*w/den if den else np.nan
  vals += [f"{w}/{l}/{o}",wr]
 print(f"{name:<12} {fills:>7} {nf:>7} {inv:>5} {drift:>11.2f} {risk:>9.2f} {vals[0]:>13} {vals[1]:>7.2f}% {vals[2]:>13} {vals[3]:>7.2f}%")
print("\nREFERENCE ORIGINAL HISTORICAL: 3R 57/18 = 76.00% | 4R 49/26 = 65.33%")
print("\nMETHOD DEFINITIONS")
for name,(w,c) in METHODS.items():
 if w==0:desc="enter market at T+4 after confirmation"
 elif c==0:desc=f"after confirmation, seek original entry for up to {w} minute(s)"
 else:desc=f"after confirmation, allow max {c:.0f} pts adverse vs original entry for up to {w} minute(s)"
 print(f"  {name:<12} {desc}")
print("\nIMPORTANT: NO_FILL is reported separately and is NOT counted as a win or loss.")
print("READ-ONLY. No production code, frozen benchmark, thresholds, or source data changed.")
