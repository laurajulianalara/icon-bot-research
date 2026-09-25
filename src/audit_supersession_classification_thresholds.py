#!/usr/bin/env python3
"""Classify T+3 supersession timing and test practical early-reject thresholds. READ ONLY."""
from pathlib import Path
import pandas as pd, numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/"data";TZ="America/New_York"
ONE=D/"audit_sep01_24_1m.parquet";CAND=D/"audit_sep01_24_candidates.parquet";REP=D/"reports/2026-09_trades.csv"
def norm(s):
 x=pd.to_datetime(s,errors="coerce");return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
one=pd.read_parquet(ONE);one["time_ny"]=norm(one.time_ny);one=one.sort_values("time_ny").reset_index(drop=True);ix=pd.Series(one.index,index=one.time_ny).to_dict()
c=pd.read_parquet(CAND);c["time_ny"]=norm(c.time_ny);c=c.sort_values("time_ny").reset_index(drop=True);c["next_extreme"]=c.groupby(["date","session","direction"],sort=False).time_ny.shift(-1)
r=pd.read_csv(REP);r["candidate_time"]=norm(r.candidate_time);bench=set(zip(r.candidate_time,r.direction.astype(str).str.upper()))
rows=[]
for _,z in c.iterrows():
 i=ix.get(z.time_ny);d=str(z.direction).upper()
 if i is None or i+3>=len(one):continue
 j=i+3;sig=one.iloc[j].time_ny;nx=z.next_extreme
 sup=pd.notna(nx) and nx<=sig
 if not sup and (z.time_ny,d) not in bench:continue
 b=one.iloc[j];ext=float(z.extreme);op=float(b.open)
 br=(float(b.low)<ext) if d=="LONG" else (float(b.high)>ext)
 rows.append(dict(candidate=z.time_ny,direction=d,benchmark=(z.time_ny,d) in bench,sup=sup,next_extreme=nx,
                  signal=sig,breaks=br,dist=abs(op-ext),open=op,high=float(b.high),low=float(b.low)))
x=pd.DataFrame(rows);s=x[x.sup];g=x[x.benchmark]
same=s[s.next_extreme==s.signal];earlier=s[s.next_extreme<s.signal];un=s[~s.breaks]
print("="*116);print("THE ICON — SUPERSESSION CLASSIFICATION + EARLY-REJECT THRESHOLD AUDIT");print("="*116)
print(f"Supersession cases: {len(s)} | benchmark controls: {len(g)}")
print("\nWHERE HISTORICAL SUPERSESSION OCCURRED")
print(f"  next extreme exactly at T+3 signal: {len(same)}")
print(f"  next extreme BEFORE T+3 signal:     {len(earlier)}")
print(f"  total:                              {len(same)+len(earlier)}")
print("\nT+3 BREAK CHECK")
print(f"  superseded breaking candidate extreme during T+3: {int(s.breaks.sum())}/{len(s)}")
print(f"  superseded NOT breaking it during T+3:             {len(un)}/{len(s)}")
print(f"  benchmark breaking it during T+3:                  {int(g.breaks.sum())}/{len(g)}")
if len(un):
 print("\n159/REMAINDER CLASSIFICATION")
 print("  next extreme earlier than T+3:",int((un.next_extreme<un.signal).sum()))
 print("  next extreme exactly T+3:     ",int((un.next_extreme==un.signal).sum()))
 print("  Interpretation: earlier cases were already superseded before entry minute; they should be rejectable causally BEFORE entry.")
print("\nDISTANCE-GATED T+3 REJECTION (1m OHLC upper-bound test)")
print("Rule: reject only when T+3 actually breaks the candidate extreme AND open->extreme distance <= threshold.")
print(f"{'THRESH':>7} {'BAD REJECTED':>14} {'BAD LEFT':>10} {'GOOD REJECTED':>15} {'GOOD KEPT':>10}")
for th in [1,2,3,4,5,6,8,10,15,20,50]:
 br=s.breaks & (s.dist<=th);gr=g.breaks & (g.dist<=th)
 print(f"{th:>6}p {int(br.sum()):>14}/{len(s):<3} {len(s)-int(br.sum()):>10} {int(gr.sum()):>15}/{len(g):<2} {len(g)-int(gr.sum()):>10}")
print("\nNOTE: 1m OHLC proves whether the break happened within T+3, not the second it happened.")
print("READ-ONLY. No production strategy, thresholds, benchmark, or source data changed.")
