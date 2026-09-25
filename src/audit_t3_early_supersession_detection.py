#!/usr/bin/env python3
"""Test whether developing T+3 price action can identify at-entry supersession earlier. READ ONLY.

IMPORTANT DATA LIMITATION:
The audit source is 1-minute OHLC, not tick/second data. Therefore +15/+30/+45 second states
cannot be reconstructed honestly. This test uses the earliest intraminute information the dataset
actually supports: T+3 OPEN, then completed T+3 1m bar. It also measures whether T+3 bar range
touches the next-extreme threshold and how much entry drift occurs by T+4.
"""
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/"data";TZ="America/New_York"
ONE=D/"audit_sep01_24_1m.parquet";CAND=D/"audit_sep01_24_candidates.parquet";REP=D/"reports/2026-09_trades.csv"
def norm(s):
 x=pd.to_datetime(s,errors="coerce");return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
one=pd.read_parquet(ONE);one["time_ny"]=norm(one.time_ny);one=one.sort_values("time_ny").reset_index(drop=True);idx=pd.Series(one.index,index=one.time_ny).to_dict()
c=pd.read_parquet(CAND);c["time_ny"]=norm(c.time_ny);c=c.sort_values("time_ny").reset_index(drop=True);c["next_extreme"]=c.groupby(["date","session","direction"],sort=False).time_ny.shift(-1)
rep=pd.read_csv(REP);rep["candidate_time"]=norm(rep.candidate_time);bench=set(zip(rep.candidate_time,rep.direction.astype(str).str.upper()))
rows=[]
for _,r in c.iterrows():
 i=idx.get(r.time_ny);d=str(r.direction).upper()
 if i is None or i+4>=len(one):continue
 j=i+3;nx=r.next_extreme
 hist_sup=pd.notna(nx) and nx<=one.iloc[j].time_ny
 # Focus on the exact at-entry supersession mechanism plus benchmark controls.
 if not hist_sup and (r.time_ny,d) not in bench:continue
 b=one.iloc[j];op=float(b.open);hi=float(b.high);lo=float(b.low)
 # A same-direction new session extreme during T+3 is exactly what makes next_extreme == T+3.
 # Candidate's own extreme is the prior threshold that the developing entry minute would have to break.
 ext=float(r.extreme)
 touched = lo<ext if d=="LONG" else hi>ext
 # Distance from T+3 open to the candidate extreme; smaller means earlier detection may be feasible in live ticks.
 dist = op-ext if d=="LONG" else ext-op
 rows.append(dict(candidate=r.time_ny,direction=d,benchmark=(r.time_ny,d) in bench,hist_sup=hist_sup,
                  entry_time=b.time_ny,entry_open=op,entry_high=hi,entry_low=lo,candidate_extreme=ext,
                  t3_breaks_candidate_extreme=touched,distance_open_to_extreme=dist,
                  t4_open=float(one.iloc[j+1].open),t4_abs_drift=abs(float(one.iloc[j+1].open)-op)))
x=pd.DataFrame(rows)
sup=x[x.hist_sup];good=x[x.benchmark]
print("="*112);print("THE ICON — DEVELOPING T+3 SUPERSESSION EARLY-DETECTION AUDIT");print("="*112)
print("DATA RESOLUTION: 1-minute OHLC. Exact +15s/+30s/+45s timing is NOT present in this dataset.")
print("Historical at-entry supersession cases inspected:",len(sup))
print("Benchmark controls inspected:",len(good))
print("\nT+3 COMPLETED-BAR DETECTION")
print("Supersession cases whose T+3 bar breaks candidate extreme:",int(sup.t3_breaks_candidate_extreme.sum()),"/",len(sup))
print("Benchmark trades whose T+3 bar ALSO breaks candidate extreme:",int(good.t3_breaks_candidate_extreme.sum()),"/",len(good))
print("\nOPEN -> EXTREME DISTANCE (how far price had to travel before supersession became knowable)")
for label,q in [("SUPERSEDED",sup),("BENCHMARK",good)]:
 a=q.distance_open_to_extreme.abs()
 print(f"{label:<10} median={a.median():.2f} pts | p25={a.quantile(.25):.2f} | p75={a.quantile(.75):.2f} | max={a.max():.2f}")
print("\nSUPERSEDED CASES BY REQUIRED MOVE FROM T+3 OPEN")
for n in [1,2,3,4,5,6,8,10,15,20]:
 k=int((sup.distance_open_to_extreme.abs()<=n).sum());print(f"  <= {n:>2} pts: {k}/{len(sup)} ({100*k/len(sup):.1f}%)")
print("\nINTERPRETATION")
print("If supersession becomes knowable as soon as live price breaks the candidate extreme, tick/second data could")
print("measure the exact detection second and executable price. 1m OHLC can prove whether it happened inside T+3,")
print("but cannot honestly tell whether it happened at +05s, +15s, +30s, or +55s.")
print("\nREAD-ONLY. No strategy/data/threshold changes.")
