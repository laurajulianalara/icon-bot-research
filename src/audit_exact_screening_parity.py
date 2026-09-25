#!/usr/bin/env python3
"""Exact September historical-vs-live SCREENING parity audit. READ ONLY.

Purpose: isolate screening differences BEFORE supersession and daily-cap effects.
Uses one shared candidate/feature calculation, then applies the two actual V15 decision
modes found in current production files:
  historical reporter: exact frozen V15 membership for dates covered by V11
  shadow-live: frozen percentile score >= 0.145921011058
V7, V8 and V27 are evaluated once because their current formulas are identical.
"""
from pathlib import Path
import sys,bisect,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];D=ROOT/"data";TZ="America/New_York"
ONE=D/"audit_sep01_24_1m.parquet";V11=D/"v11_reversal_state_forensics.csv";REF=D/"icon_v15_pine_reference.json"
TH=.145921011058;RTH=.576132;WTH=.183258
def norm(s):
 x=pd.to_datetime(s,errors="coerce");return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
def sess(t):
 m=t.hour*60+t.minute
 return "ASIA" if 1200<=m<1440 else "LONDON" if 120<=m<300 else "NYAM" if 570<=m<750 else "NYPM" if 810<=m<1020 else None
one=pd.read_parquet(ONE).copy();one["time_ny"]=norm(one.time_ny);one=one.sort_values("time_ny").reset_index(drop=True)
pc=one.close.shift();one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
z=one.set_index("time_ny");three=z.resample("3min",label="left",closed="left").agg(ticker=("ticker","last"),open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum"),n=("close","count")).reset_index()
pc3=three.close.shift();three["atr_20"]=pd.concat([three.high-three.low,(three.high-pc3).abs(),(three.low-pc3).abs()],axis=1).max(axis=1).rolling(20).mean()
three["uw"]=three.high-three[["open","close"]].max(axis=1);three["lw"]=three[["open","close"]].min(axis=1)-three.low;three["session"]=three.time_ny.apply(sess)
three=three[(three.n==3)&three.open.notna()&three.session.notna()&(three.time_ny>=pd.Timestamp("2026-09-01",tz=TZ))&(three.time_ny<pd.Timestamp("2026-10-01",tz=TZ))]
cs=[]
for (d,s),gg in three.groupby([three.time_ny.dt.date,"session"],sort=False):
 rh=rl=None
 for _,r in gg.iterrows():
  if rh is None:rh=float(r.high);rl=float(r.low);continue
  rng=float(r.high-r.low)
  if r.low<rl:cs.append(dict(time_ny=r.time_ny,direction="LONG",session=s,ticker=r.ticker,extreme=float(r.low),atr=float(r.atr_20),sweep_distance=float(rl-r.low),wick=float(r.lw/rng) if rng>0 else 0))
  if r.high>rh:cs.append(dict(time_ny=r.time_ny,direction="SHORT",session=s,ticker=r.ticker,extreme=float(r.high),atr=float(r.atr_20),sweep_distance=float(r.high-rh),wick=float(r.uw/rng) if rng>0 else 0))
  rh=max(rh,float(r.high));rl=min(rl,float(r.low))
cand=pd.DataFrame(cs);idx=pd.Series(one.index,index=one.time_ny).to_dict()

ref=pd.read_csv(V11);ref["candidate_time"]=pd.to_datetime(ref.candidate_time,utc=True);ref["candidate_time_et"]=ref.candidate_time.dt.tz_convert(TZ)
ref["reclaim_x_wick"]=ref.early_reclaim_atr*ref.wick_percent;ref["close_x_reclaim"]=ref.m2_close_pos*ref.early_reclaim_atr
ref["sweep_minus_reclaim"]=ref.sweep_atr-ref.early_reclaim_atr;ref["impulse_minus_reclaim"]=ref.reversal_impulse-ref.early_reclaim_atr
ref["quality_balance"]=ref.rejection_quality*ref.impulse_to_reclaim/(1+ref.reclaim_to_sweep)
SPEC=[("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]
parts=[]
for col,hi,w in SPEC:
 rank=ref[col].rank(pct=True);comp=rank if hi else 1-rank;parts += [comp]*w
ref["score"]=pd.concat(parts,axis=1).mean(axis=1);cut=ref.score.quantile(.07)
hr=ref[ref.score>=cut].copy();hr["date_et"]=hr.candidate_time_et.dt.date;hr=hr.sort_values("candidate_time_et");hr["num"]=hr.groupby("date_et").cumcount()+1;hr=hr[hr.num<=6]
allowed=set(zip(hr.candidate_time_et.astype(str),hr.direction.astype(str)));max_ref=ref.candidate_time_et.dt.date.max()
with open(REF) as f:J={k:sorted(float(x) for x in v) for k,v in json.load(f).items()}
def rank(v,a):
 lo=bisect.bisect_left(a,float(v));hi=bisect.bisect_right(a,float(v));return (lo+(hi-lo+1)/2)/len(a) if hi>lo else min(1,max(0,(lo+1)/len(a)))
def score(F):
 p=[]
 for col,hi,w in SPEC:
  rr=rank(F[col],J[col]);p += [(rr if hi else 1-rr)]*w
 return float(np.mean(p))
rows=[]
for _,c in cand.iterrows():
 i=idx.get(c.time_ny)
 if i is None or i<20 or i+3>=len(one):continue
 a=float(one.iloc[i].atr1)
 if not np.isfinite(a) or a<=0:continue
 sg=1 if c.direction=="LONG" else -1;v={}
 for k in [1,2]:
  b=one.iloc[i+k];pre=one.iloc[max(0,i+k-5):i+k+1]
  v[f"m{k}_move"]=(float(b.close)-float(one.iloc[i].close))/a*sg
  cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5;v[f"m{k}_cp"]=float(cp if c.direction=="LONG" else 1-cp)
  v[f"m{k}_dir"]=int(((((pre.close-pre.open)*sg)>0)).sum())
 v7=v["m1_move"]<=.300 and v["m1_cp"]>=.140 and v["m2_cp"]<=.912
 if not v7:continue
 first=one.iloc[i+1:i+3];reclaim=(float(first.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first.iloc[-1].close))/a
 v8=reclaim<=.90 and v["m2_cp"]<=.80 and float(c.wick)<=.60 and v["m2_move"]<=.15 and v["m2_dir"]<=4
 if not v8:continue
 rq=(1-min(max(v["m2_cp"],0),1))*(1-min(max(float(c.wick),0),1));ri=-v["m2_move"];ca=float(c.atr);sa=float(c.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
 ex=ref[(ref.candidate_time_et.astype(str)==str(c.time_ny))&(ref.direction.astype(str)==str(c.direction))]
 if len(ex) and pd.notna(ex.iloc[0].get("sweep_atr",np.nan)):sa=float(ex.iloc[0].sweep_atr)
 rts=reclaim/(abs(sa)+.05);itr=ri/(abs(reclaim)+.05);rxw=reclaim*float(c.wick)
 F={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,"reversal_impulse":ri,"reclaim_x_wick":rxw,"close_x_reclaim":v["m2_cp"]*reclaim,"sweep_minus_reclaim":sa-reclaim,"impulse_minus_reclaim":ri-reclaim,"quality_balance":rq*itr/(1+rts)}
 ls=score(F);live15=np.isfinite(ls) and ls>=TH
 hist_mode=c.time_ny.date()<=max_ref;hist15=((str(c.time_ny),str(c.direction)) in allowed) if hist_mode else live15
 v27=not(reclaim>=RTH and rxw>=WTH)
 rows.append(dict(candidate=c.time_ny,direction=c.direction,session=c.session,historical_mode=hist_mode,hist_v15=hist15,live_v15=live15,live_score=ls,v27=v27))
x=pd.DataFrame(rows);d=x[x.hist_v15!=x.live_v15]
print("="*100);print("THE ICON — EXACT HISTORICAL vs LIVE SCREENING PARITY AUDIT");print("="*100)
print("Shared completed-3m candidates:",len(cand));print("Reached V15 after identical V7+V8:",len(x));print("V11 reference max date:",max_ref)
print("\nV15 DECISION DISAGREEMENTS:",len(d))
print("  Historical PASS / Live FAIL:",int((d.hist_v15 & ~d.live_v15).sum()))
print("  Historical FAIL / Live PASS:",int((~d.hist_v15 & d.live_v15).sum()))
print("  Of disagreements that also pass V27:",int(d.v27.sum()))
print("\nFINAL PRE-SUPERSESSION SCREEN (V7+V8+V15+V27)")
hp=x[x.hist_v15 & x.v27];lp=x[x.live_v15 & x.v27]
hk=set(zip(hp.candidate.astype(str),hp.direction));lk=set(zip(lp.candidate.astype(str),lp.direction))
print("  Historical survivors:",len(hk));print("  Live survivors:      ",len(lk));print("  Live-only survivors: ",len(lk-hk));print("  Historical-only:     ",len(hk-lk))
if lk-hk:
 print("\nFIRST 25 LIVE-ONLY SCREENING SURVIVORS")
 for k in sorted(lk-hk)[:25]:
  q=lp[(lp.candidate.astype(str)==k[0])&(lp.direction==k[1])].iloc[0];print(k,"score",round(float(q.live_score),6))
print("\nThis audit intentionally stops BEFORE supersession and the 6/day cap, so screening mismatch is isolated from those mechanisms.")
print("READ-ONLY. No production files, thresholds, reports, or source data changed.")
