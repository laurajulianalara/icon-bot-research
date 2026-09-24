#!/usr/bin/env python3
"""Sep 24 diagnostic: require the entry-time 3m candle to COMPLETE before confirmation.
No strategy changes and no orders. Tests whether each of the 11 causal signals survives
once the 3m bucket beginning at the original entry time is fully known.
"""
from pathlib import Path
import pandas as pd,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY=pd.Timestamp("2026-09-24",tz=live.TZ); END=DAY+pd.Timedelta(days=1)
SIG=Path("data/reports/2026-09-24_true_bar_by_bar.csv")
if not SIG.exists(): raise RuntimeError("Run replay_option2b_today_true_bar_by_bar.py first.")

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
tr=pd.read_csv(SIG);tr["entry_time"]=pd.to_datetime(tr.entry_time_et)
rep=pd.read_csv("data/reports/2026-09_trades.csv");rep["entry_time"]=pd.to_datetime(rep.entry_time)
rep["entry_time"]=rep.entry_time.dt.tz_localize(live.TZ) if rep.entry_time.dt.tz is None else rep.entry_time.dt.tz_convert(live.TZ)
canon=set(zip(rep.entry_time,rep.session,rep.direction))

rows=[]
for _,t in tr.sort_values("entry_time").iterrows():
 et=t.entry_time; confirm=et+pd.Timedelta(minutes=2)
 ctx=one[one.time_ny<=confirm].copy().reset_index(drop=True)
 sel=live.evaluate(ctx)
 # Original signal survives confirmation only if the same original entry remains in selector.
 match=[x for x in sel if pd.Timestamp(x["entry_time_et"])==et and x["session"]==t.session and x["direction"]==t.direction and abs(float(x["entry"])-float(t.entry))<1e-9 and abs(float(x["stop"])-float(t.stop))<1e-9]
 survives=bool(match)
 # Executable confirmation price: next minute open after completed entry-time 3m bucket.
 exec_time=et+pd.Timedelta(minutes=3)
 q=one[(one.time_ny==exec_time)&(one.ticker==t.ticker)]
 exec_price=float(q.iloc[0].open) if len(q) else float("nan")
 typ="CANONICAL" if (et,t.session,t.direction) in canon else "CAUSAL EXTRA"
 rows.append({"original_entry_time":et,"session":t.session,"direction":t.direction,"type":typ,"original_entry":float(t.entry),"stop":float(t.stop),"confirm_time":confirm,"survives_3m_confirmation":survives,"confirmed_execution_time":exec_time,"confirmed_market_open":exec_price})

res=pd.DataFrame(rows)
print("="*130);print("SEP 24 — 3-MINUTE CONFIRMATION TEST");print("Diagnostic only: original entry-time 3m bucket must finish before setup is accepted.");print("="*130)
print(res.to_string(index=False))
print("\nSUMMARY")
for typ,g in res.groupby("type"):
 print(typ,":",int(g.survives_3m_confirmation.sum()),"/",len(g),"survive")
print("TOTAL:",int(res.survives_3m_confirmation.sum()),"/",len(res),"survive")
print("\nNOTE: confirmed_market_open is shown only to expose the executable price after confirmation; outcomes are NOT recalculated yet.")
out=Path("data/reports/2026-09-24_3m_confirmation_test.csv");res.to_csv(out,index=False);print("Saved:",out)
