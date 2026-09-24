#!/usr/bin/env python3
from pathlib import Path
import pandas as pd,sys
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
one=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True);idx={t:i for i,t in enumerate(one.time_ny)}
tr=pd.read_csv(SIG);tr["entry_time"]=pd.to_datetime(tr.entry_time_et)
rep=pd.read_csv("data/reports/2026-09_trades.csv");rep["entry_time"]=pd.to_datetime(rep.entry_time)
rep["entry_time"]=rep.entry_time.dt.tz_localize(live.TZ) if rep.entry_time.dt.tz is None else rep.entry_time.dt.tz_convert(live.TZ)
canon=set(zip(rep.entry_time,rep.session,rep.direction));rows=[]
for _,t in tr.sort_values("entry_time").iterrows():
 et=t.entry_time;j=idx.get(et)
 if j is None:continue
 entry=float(t.entry);stop=float(t.stop);risk=float(t.risk_points);d=t.direction;ticker=t.ticker;out={}
 for rr in range(1,7):
  target=entry+rr*risk if d=="LONG" else entry-rr*risk;result="OPEN"
  for q in range(j,min(j+241,len(one))):
   b=one.iloc[q]
   if b.ticker!=ticker:break
   sh=float(b.low)<=stop if d=="LONG" else float(b.high)>=stop
   th=float(b.high)>=target if d=="LONG" else float(b.low)<=target
   if sh:result="LOSS";break
   if th:result="WIN";break
  out[f"{rr}R"]=result
 typ="CANONICAL" if (et,t.session,d) in canon else "CAUSAL EXTRA"
 rows.append({"entry_time":et,"session":t.session,"direction":d,"type":typ,"entry":entry,"stop":stop,**out})
res=pd.DataFrame(rows)
print("="*112);print("SEP 24 — TRUE CAUSAL TRADES WITH 1R-6R OUTCOMES");print("Stop-first | max 241 one-minute bars | diagnostic only");print("="*112);print(res.to_string(index=False));print("\n"+"="*112)
for typ,g in res.groupby("type"):
 print(f"{typ}: {len(g)} trades")
 for rr in range(1,7):
  closed=g[g[f"{rr}R"].isin(["WIN","LOSS"])];w=(closed[f"{rr}R"]=="WIN").sum();l=(closed[f"{rr}R"]=="LOSS").sum()
  print(f"  {rr}R: {w}W / {l}L / {len(g)-len(closed)} OPEN | WR {100*w/len(closed):.1f}%" if len(closed) else f"  {rr}R: OPEN")
print("\nALL CAUSAL TRADES:",len(res))
for rr in range(1,7):
 closed=res[res[f"{rr}R"].isin(["WIN","LOSS"])];w=(closed[f"{rr}R"]=="WIN").sum();l=(closed[f"{rr}R"]=="LOSS").sum();pnl=w*300*rr-l*300
 print(f"  {rr}R: {w}W / {l}L / {len(res)-len(closed)} OPEN | WR {100*w/len(closed):.1f}% | P&L @ $300 risk "+format(pnl,",.0f") if len(closed) else f"  {rr}R: OPEN")
out=Path("data/reports/2026-09-24_true_causal_outcomes.csv");res.to_csv(out,index=False);print("\nSaved:",out)
