#!/usr/bin/env python3
"""Sep 24: 1R-6R outcomes for the six setups that survive 3m confirmation.
Uses actual confirmed execution open and keeps the original setup stop.
Diagnostic only; no orders and no Option 2B changes.
"""
from pathlib import Path
import pandas as pd,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live
DAY=pd.Timestamp("2026-09-24",tz=live.TZ);END=DAY+pd.Timedelta(days=1)
CONF=Path("data/reports/2026-09-24_3m_confirmation_test.csv")
if not CONF.exists():raise RuntimeError("Run python src/test_sep24_3m_confirmation.py first.")
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
idx={t:i for i,t in enumerate(one.time_ny)}
c=pd.read_csv(CONF);c["confirmed_execution_time"]=pd.to_datetime(c.confirmed_execution_time)
s=c[c.survives_3m_confirmation.astype(str).str.lower().isin(["true","1"])].copy();rows=[]
for _,t in s.iterrows():
 et=t.confirmed_execution_time;j=idx.get(et)
 if j is None:continue
 entry=float(t.confirmed_market_open);stop=float(t.stop);d=t.direction
 risk=entry-stop if d=="LONG" else stop-entry
 out={}
 if risk<=0:
  for rr in range(1,7):out[f"{rr}R"]="INVALID"
 else:
  ticker=one.iloc[j].ticker
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
 rows.append({"original_entry_time":t.original_entry_time,"confirmed_entry_time":et,"session":t.session,"direction":d,"original_entry":float(t.original_entry),"confirmed_entry":entry,"stop":stop,"confirmed_risk_points":risk,**out})
r=pd.DataFrame(rows)
print("="*130);print("SEP 24 — 3M-CONFIRMED EXECUTION OUTCOMES 1R-6R");print("Actual confirmed market-open entry | original setup stop | stop-first | 241-minute max");print("="*130);print(r.to_string(index=False));print("\nSUMMARY")
for rr in range(1,7):
 valid=r[r[f"{rr}R"].isin(["WIN","LOSS"])];w=(valid[f"{rr}R"]=="WIN").sum();l=(valid[f"{rr}R"]=="LOSS").sum();op=len(r)-len(valid);pnl=w*300*rr-l*300
 print(f"{rr}R: {w}W / {l}L / {op} OPEN | WR {100*w/len(valid):.1f}% | P&L @ $300 risk "+format(pnl,",.0f") if len(valid) else f"{rr}R: no closed outcomes")
out=Path("data/reports/2026-09-24_3m_confirmed_outcomes.csv");r.to_csv(out,index=False);print("\nSaved:",out)
