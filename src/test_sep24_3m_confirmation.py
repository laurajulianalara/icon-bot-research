#!/usr/bin/env python3
"""FAST Sep 24 3m confirmation diagnostic. No strategy changes; no orders.
Uses the already-proven supersession mechanism directly instead of rerunning Option 2B 11 times.
"""
from pathlib import Path
import pandas as pd,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live
DAY=pd.Timestamp("2026-09-24",tz=live.TZ);END=DAY+pd.Timedelta(days=1)
SIG=Path("data/reports/2026-09-24_true_bar_by_bar.csv")
if not SIG.exists():raise RuntimeError("Run replay_option2b_today_true_bar_by_bar.py first.")
def norm(x):
 x=x.copy();x["time_ny"]=pd.to_datetime(x.time_ny)
 x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ) if x.time_ny.dt.tz is None else x.time_ny.dt.tz_convert(live.TZ)
 return x[live.NEED]
pieces=[norm(pd.read_parquet(live.HIST))]
for p in Path("data").glob("mnq_*_1m.parquet"):
 try:
  x=norm(pd.read_parquet(p))
  if ((x.time_ny>=DAY)&(x.time_ny<END)).any():pieces.append(x)
 except:pass
one=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
today=one[(one.time_ny>=DAY)&(one.time_ny<END)].copy()
# Build completed 3m candles once.
z=today.set_index("time_ny")
three=z.resample("3min",label="left",closed="left").agg(ticker=("ticker","last"),open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),n=("close","count")).reset_index()
three=three[three.n==3].copy()
tr=pd.read_csv(SIG);tr["entry_time"]=pd.to_datetime(tr.entry_time_et)
rep=pd.read_csv("data/reports/2026-09_trades.csv");rep["entry_time"]=pd.to_datetime(rep.entry_time)
rep["entry_time"]=rep.entry_time.dt.tz_localize(live.TZ) if rep.entry_time.dt.tz is None else rep.entry_time.dt.tz_convert(live.TZ)
canon=set(zip(rep.entry_time,rep.session,rep.direction))
rows=[]
for _,t in tr.sort_values("entry_time").iterrows():
 et=t.entry_time; cand_time=et-pd.Timedelta(minutes=3)
 # Entry-time 3m candle is the only newly completed information that caused the 5 extras to disappear.
 b=three[three.time_ny==et]
 if len(b):
  b=b.iloc[0]
  # A new more-extreme same-direction candidate at entry-time supersedes original candidate.
  if t.direction=="LONG": new_extreme=float(b.low)<float(t.stop)+0.25
  else: new_extreme=float(b.high)>float(t.stop)-0.25
 else:new_extreme=False
 survives=not new_extreme
 exec_time=et+pd.Timedelta(minutes=3)
 q=today[(today.time_ny==exec_time)&(today.ticker==t.ticker)]
 exec_price=float(q.iloc[0].open) if len(q) else float("nan")
 typ="CANONICAL" if (et,t.session,t.direction) in canon else "CAUSAL EXTRA"
 rows.append({"original_entry_time":et,"session":t.session,"direction":t.direction,"type":typ,"original_entry":float(t.entry),"stop":float(t.stop),"entry_3m_creates_new_extreme":new_extreme,"survives_3m_confirmation":survives,"confirmed_execution_time":exec_time,"confirmed_market_open":exec_price})
res=pd.DataFrame(rows)
print("="*125);print("SEP 24 — FAST 3-MINUTE CONFIRMATION TEST");print("Uses proven entry-time 3m supersession mechanism; no repeated full-strategy evaluations.");print("="*125);print(res.to_string(index=False))
print("\nSUMMARY")
for typ,g in res.groupby("type"):print(f"{typ}: {int(g.survives_3m_confirmation.sum())}/{len(g)} survive | {int(g.entry_3m_creates_new_extreme.sum())}/{len(g)} rejected")
print(f"TOTAL: {int(res.survives_3m_confirmation.sum())}/{len(res)} survive")
out=Path("data/reports/2026-09-24_3m_confirmation_test.csv");res.to_csv(out,index=False);print("Saved:",out)
