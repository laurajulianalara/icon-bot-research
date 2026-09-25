#!/usr/bin/env python3
"""Build a TEMPORARY Sep 1-24 audit dataset from existing local caches + continuous history.
Does NOT overwrite frozen/source parquet files. Then runs the causal delay audit on rebuilt candidates.
"""
from pathlib import Path
import pandas as pd, numpy as np, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; TZ="America/New_York"
OUT1=DATA/"audit_sep01_24_1m.parquet"; OUT2=DATA/"audit_sep01_24_candidates.parquet"
NEED=["time_ny","ticker","open","high","low","close","volume"]
START=pd.Timestamp("2026-09-01",tz=TZ); END=pd.Timestamp("2026-09-25",tz=TZ)
def norm(s):
 x=pd.to_datetime(s,errors="coerce")
 return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
def session(ts):
 m=ts.hour*60+ts.minute
 if 1200<=m<1440:return "ASIA"
 if 120<=m<300:return "LONDON"
 if 570<=m<750:return "NYAM"
 if 810<=m<1020:return "NYPM"
 return None
pieces=[]
hist=DATA/"mnq_continuous_1m.parquet"
if hist.exists():
 x=pd.read_parquet(hist); x["time_ny"]=norm(x.time_ny)
 pieces.append(x[NEED])
for f in sorted(DATA.glob("mnq_sep*_2026*_1m.parquet")):
 try:
  x=pd.read_parquet(f)
  if not set(NEED).issubset(x.columns):continue
  x["time_ny"]=norm(x.time_ny); pieces.append(x[NEED])
 except Exception as e: print("SKIP",f.name,e)
if not pieces: raise SystemExit("No local September market data found.")
one=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny")
one=one[(one.time_ny>=START-pd.Timedelta(hours=2))&(one.time_ny<END)].reset_index(drop=True)
print("="*96);print("BUILD TEMP SEP 1-24 AUDIT INPUTS");print("="*96)
print("1m assembled:",one.time_ny.min(),"->",one.time_ny.max(),"| rows",len(one))
for d in pd.date_range("2026-09-18","2026-09-24"):
 n=int((one.time_ny.dt.date==d.date()).sum()); print(d.date(),"rows",n)
if one.time_ny.max()<pd.Timestamp("2026-09-24 10:36",tz=TZ):
 raise SystemExit("\nLocal caches do not yet cover the Sep 24 benchmark. Run the permanent reporter first:\n  python src/icon_month_live_report.py\nThen rerun this script.")
one.to_parquet(OUT1,index=False)
z=one.set_index("time_ny")
three=z.resample("3min",label="left",closed="left").agg(ticker=("ticker","last"),open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum"),n=("close","count")).reset_index()
three=three[(three.n==3)&three.open.notna()].copy()
pc=three.close.shift(1); three["atr_20"]=pd.concat([three.high-three.low,(three.high-pc).abs(),(three.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
three["upper_wick"]=three.high-three[["open","close"]].max(axis=1);three["lower_wick"]=three[["open","close"]].min(axis=1)-three.low
three["session"]=three.time_ny.apply(session)
cs=[]
g=three[(three.time_ny>=START)&(three.time_ny<END)&three.session.notna()]
for (date,s),gg in g.groupby([g.time_ny.dt.date,"session"],sort=False):
 rh=rl=None
 for _,r in gg.iterrows():
  if rh is None:rh=float(r.high);rl=float(r.low);continue
  rng=float(r.high-r.low)
  if r.low<rl:cs.append(dict(time_ny=r.time_ny,date=date,session=s,session_id=f"{date}|{s}",direction="LONG",ticker=r.ticker,extreme=float(r.low),atr=float(r.atr_20),sweep_distance=float(rl-r.low),wick_percent=float(r.lower_wick/rng) if rng>0 else 0))
  if r.high>rh:cs.append(dict(time_ny=r.time_ny,date=date,session=s,session_id=f"{date}|{s}",direction="SHORT",ticker=r.ticker,extreme=float(r.high),atr=float(r.atr_20),sweep_distance=float(r.high-rh),wick_percent=float(r.upper_wick/rng) if rng>0 else 0))
  rh=max(rh,float(r.high));rl=min(rl,float(r.low))
cand=pd.DataFrame(cs).sort_values("time_ny").reset_index(drop=True);cand.to_parquet(OUT2,index=False)
print("Candidates:",len(cand),"|",cand.time_ny.min(),"->",cand.time_ny.max())
print("Saved TEMP audit inputs:",OUT1.name,",",OUT2.name)
print("\nNow run:\n  python src/audit_causal_delayed_supersession_full_sep.py")
