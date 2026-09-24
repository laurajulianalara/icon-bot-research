#!/usr/bin/env python3
"""Sep24 entry-time feature comparison: 6 canonical vs 5 causal extras.
Uses ONLY information available through each original entry minute.
Diagnostic only; no strategy changes/orders.
"""
from pathlib import Path
import pandas as pd,numpy as np,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live
DAY=pd.Timestamp("2026-09-24",tz=live.TZ);END=DAY+pd.Timedelta(days=1)
SIG=Path("data/reports/2026-09-24_true_bar_by_bar.csv")
def norm(x):
 x=x.copy();x["time_ny"]=pd.to_datetime(x.time_ny);x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ) if x.time_ny.dt.tz is None else x.time_ny.dt.tz_convert(live.TZ);return x[live.NEED]
pieces=[norm(pd.read_parquet(live.HIST))]
for p in Path("data").glob("mnq_*_1m.parquet"):
 try:
  x=norm(pd.read_parquet(p))
  if ((x.time_ny>=DAY)&(x.time_ny<END)).any():pieces.append(x)
 except:pass
one=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx={t:i for i,t in enumerate(one.time_ny)}
tr=pd.read_csv(SIG);tr["entry_time"]=pd.to_datetime(tr.entry_time_et)
rep=pd.read_csv("data/reports/2026-09_trades.csv");rep["entry_time"]=pd.to_datetime(rep.entry_time)
rep["entry_time"]=rep.entry_time.dt.tz_localize(live.TZ) if rep.entry_time.dt.tz is None else rep.entry_time.dt.tz_convert(live.TZ)
canon=set(zip(rep.entry_time,rep.session,rep.direction));rows=[]
for _,t in tr.sort_values("entry_time").iterrows():
 et=t.entry_time;i=idx[et];ct=et-pd.Timedelta(minutes=3);ci=idx.get(ct)
 if ci is None:continue
 # completed candidate 3m candle uses ct,ct+1,ct+2 only
 cb=one.iloc[ci:ci+3];o=float(cb.iloc[0].open);h=float(cb.high.max());l=float(cb.low.min());cl=float(cb.iloc[-1].close);rng=h-l
 wick=(min(o,cl)-l)/rng if t.direction=="LONG" and rng>0 else ((h-max(o,cl))/rng if rng>0 else 0)
 a=float(one.iloc[ci].atr1);sg=1 if t.direction=="LONG" else -1
 m1=one.iloc[ci+1];m2=one.iloc[ci+2];ext=float(t.stop)+.25 if t.direction=="LONG" else float(t.stop)-.25
 m1move=(float(m1.close)-float(one.iloc[ci].close))/a*sg;m2move=(float(m2.close)-float(one.iloc[ci].close))/a*sg
 cp1=(m1.close-m1.low)/(m1.high-m1.low) if m1.high>m1.low else .5;cp2=(m2.close-m2.low)/(m2.high-m2.low) if m2.high>m2.low else .5
 cp1=float(cp1 if t.direction=="LONG" else 1-cp1);cp2=float(cp2 if t.direction=="LONG" else 1-cp2)
 first2=one.iloc[ci+1:ci+3]
 reclaim=(float(first2.iloc[-1].close)-ext)/a if t.direction=="LONG" else (ext-float(first2.iloc[-1].close))/a
 rejection=(1-min(max(cp2,0),1))*(1-min(max(wick,0),1));impulse=-m2move;rw=reclaim*wick
 # entry minute: only its OPEN is known at decision instant; report prior closed minute too.
 prev=one.iloc[i-1]; eb=one.iloc[i]
 prev_move=(float(prev.close)-float(m2.close))/a*sg
 rows.append({"entry_time":et,"type":"GOOD" if (et,t.session,t.direction) in canon else "BAD_EXTRA","session":t.session,"direction":t.direction,"entry":float(t.entry),"stop":float(t.stop),"risk_pts":float(t.risk_points),"cand_range":rng,"cand_body":abs(cl-o),"wick_pct":wick,"atr1":a,"m1_move_atr":m1move,"m1_close_pos":cp1,"m2_move_atr":m2move,"m2_close_pos":cp2,"reclaim_atr":reclaim,"rejection_quality":rejection,"reclaim_x_wick":rw,"reversal_impulse":impulse,"prev1m_dir_move_atr":prev_move,"entry_gap_from_prev_close_atr":((float(eb.open)-float(prev.close))/a)*sg})
r=pd.DataFrame(rows)
pd.set_option("display.max_columns",None);pd.set_option("display.width",240)
print("="*150);print("SEP 24 — ENTRY-TIME GOOD vs BAD FEATURE DIAGNOSTIC");print("ONLY data available at original entry time; no future entry-candle high/low/close.");print("="*150)
print(r.round(4).to_string(index=False))
features=[x for x in r.columns if x not in ["entry_time","type","session","direction","entry","stop"]]
print("\nGROUP AVERAGES")
print(r.groupby("type")[features].mean(numeric_only=True).round(4).to_string())
print("\nSEPARATION CHECK (simple one-feature thresholds; diagnostic, NOT a proposed filter)")
for f in features:
 g=r[r.type=="GOOD"][f].dropna();b=r[r.type=="BAD_EXTRA"][f].dropna()
 if len(g) and len(b):
  if g.min()>b.max():print(f"{f}: PERFECT today | GOOD > BAD | good_min={g.min():.4f} bad_max={b.max():.4f}")
  elif g.max()<b.min():print(f"{f}: PERFECT today | GOOD < BAD | good_max={g.max():.4f} bad_min={b.min():.4f}")
out=Path("data/reports/2026-09-24_good_vs_bad_entry_features.csv");r.to_csv(out,index=False);print("\nSaved:",out)
