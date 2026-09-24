#!/usr/bin/env python3
"""Today-only Option 2B live-selector side-by-side. NO ORDERS."""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY=pd.Timestamp.now(tz=live.TZ).normalize()
END=DAY+pd.Timedelta(days=1)
EXPECTED=Path("data/reports/"+DAY.strftime("%Y-%m")+"_trades.csv")

def norm(x):
    x=x.copy(); x["time_ny"]=pd.to_datetime(x.time_ny)
    if x.time_ny.dt.tz is None:x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ)
    else:x["time_ny"]=x.time_ny.dt.tz_convert(live.TZ)
    return x[live.NEED]

pieces=[]
h=norm(pd.read_parquet(live.HIST)); pieces.append(h[(h.time_ny>=DAY-pd.Timedelta(days=3))&(h.time_ny<END)])
for p in Path("data").glob("mnq_*_1m.parquet"):
    try:
        x=norm(pd.read_parquet(p))
        if ((x.time_ny>=DAY)&(x.time_ny<END)).any(): pieces.append(x)
    except Exception: pass
all1=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
context=all1[all1.time_ny<END].tail(6000).copy()
got=pd.DataFrame(live.evaluate(context))
if not got.empty:
    got["entry_time"]=pd.to_datetime(got.entry_time_et)
    got=got[(got.entry_time>=DAY)&(got.entry_time<END)].copy()

if not EXPECTED.exists(): raise RuntimeError("Run python src/icon_month_live_report.py first.")
exp=pd.read_csv(EXPECTED); exp["entry_time"]=pd.to_datetime(exp.entry_time)
if exp.entry_time.dt.tz is None: exp["entry_time"]=exp.entry_time.dt.tz_localize(live.TZ)
else: exp["entry_time"]=exp.entry_time.dt.tz_convert(live.TZ)
exp=exp[(exp.entry_time>=DAY)&(exp.entry_time<END)].copy()

print("="*82); print("THE ICON — TODAY OPTION 2B LIVE-SELECTOR SIDE-BY-SIDE"); print("="*82)
print("Date:",DAY.date(),"| Market data through:",all1.time_ny.max(),"| Orders: DISABLED")
keys=["entry_time","session","direction"]
m=exp.merge(got,on=keys,how="outer",suffixes=("_report","_live"),indicator=True)
both=m[m._merge=="both"].copy(); missing=m[m._merge=="left_only"]; extra=m[m._merge=="right_only"]
if len(both):
    both["entry_exact"]=(both.entry_report.astype(float)-both.entry_live.astype(float)).abs()<1e-9
    both["stop_exact"]=(both.stop_report.astype(float)-both.stop_live.astype(float)).abs()<1e-9
else:
    both["entry_exact"]=[]; both["stop_exact"]=[]

print("\nREPORT:",len(exp)," LIVE SELECTOR:",len(got)," MATCHED:",len(both)," MISSING:",len(missing)," EXTRA:",len(extra))
print("\nMATCHED TRADES")
cols=["entry_time","session","direction","entry_report","entry_live","stop_report","stop_live","entry_exact","stop_exact"]
print(both[cols].to_string(index=False) if len(both) else "None")
if len(missing): print("\nMISSING FROM LIVE SELECTOR\n",missing[keys+["entry_report","stop_report"]].to_string(index=False))
if len(extra): print("\nEXTRA FROM LIVE SELECTOR\n",extra[keys+["entry_live","stop_live"]].to_string(index=False))

# Outcomes are post-entry report statistics; compare selection/entry/stop above.
rrcols=[f"{r}R" for r in range(1,7)]
print("\nTODAY REPORT OUTCOMES")
print(exp[["entry_time","session","direction","entry","stop","risk_points"]+rrcols].to_string(index=False))

ok=len(exp)==len(got) and missing.empty and extra.empty and both.entry_exact.all() and both.stop_exact.all()
print("\n"+("PASS — TODAY'S FINAL LIVE SELECTOR SET MATCHES EXACTLY" if ok else "FAIL — TODAY'S SELECTOR PARITY NEEDS REVIEW"))
print("\nNOTE: This is today-only final-set parity using today's Massive data; it does not claim the shadow process was continuously online at each entry.")
sys.exit(0 if ok else 2)
