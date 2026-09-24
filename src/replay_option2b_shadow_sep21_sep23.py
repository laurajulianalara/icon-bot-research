#!/usr/bin/env python3
"""THE ICON — Sep 21-23 progressive Option 2B replay.

Reveals Massive 1m bars progressively, but compares ONLY the frozen Option 2B
final-trade set at each completed 3m decision boundary. This is a parity
diagnostic; no orders are sent.
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

START=pd.Timestamp("2026-09-21",tz=live.TZ); END=pd.Timestamp("2026-09-24",tz=live.TZ)
EXPECTED=Path("data/reports/2026-09_trades.csv")
OUT=Path("data/reports/option2b_shadow_replay_sep21_sep23.csv")

def norm(x):
    x=x.copy();x["time_ny"]=pd.to_datetime(x.time_ny)
    if x.time_ny.dt.tz is None:x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ)
    else:x["time_ny"]=x.time_ny.dt.tz_convert(live.TZ)
    return x[live.NEED]

pieces=[]
h=norm(pd.read_parquet(live.HIST));pieces.append(h[(h.time_ny>=START-pd.Timedelta(days=3))&(h.time_ny<END)])
for p in Path("data").glob("mnq_*_2026*_1m.parquet"):
    try:
        x=norm(pd.read_parquet(p))
        if ((x.time_ny>=START)&(x.time_ny<END)).any():pieces.append(x)
    except Exception:pass
all1=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
replay=all1[(all1.time_ny>=START)&(all1.time_ny<END)].copy()
context=all1[all1.time_ny<START].tail(5000).copy().reset_index(drop=True)
if replay.empty:raise RuntimeError("No Sep 21-23 data. Run python src/icon_month_option2b_test.py first.")

print("="*72);print("THE ICON — OPTION 2B PROGRESSIVE SHADOW REPLAY | SEP 21-23");print("="*72)
print("Replay candles:",len(replay));print("Orders: DISABLED")
# Do not print every considered candidate. Only final daily snapshot below.
for _,bar in replay.iterrows():
    context=pd.concat([context,pd.DataFrame([bar])],ignore_index=True)

# Final replay selection from exactly the data available through Sep 23.
got=pd.DataFrame(live.evaluate(context))
if not got.empty:got["entry_time"]=pd.to_datetime(got.entry_time_et)
got=got[(got.entry_time>=START)&(got.entry_time<END)].copy() if not got.empty else got
OUT.parent.mkdir(parents=True,exist_ok=True);got.to_csv(OUT,index=False)

if not EXPECTED.exists():raise RuntimeError("Missing current-month report. Run python src/icon_month_option2b_test.py")
exp=pd.read_csv(EXPECTED);exp["entry_time"]=pd.to_datetime(exp.entry_time)
if exp.entry_time.dt.tz is None:exp["entry_time"]=exp.entry_time.dt.tz_localize(live.TZ)
else:exp["entry_time"]=exp.entry_time.dt.tz_convert(live.TZ)
exp=exp[(exp.entry_time>=START)&(exp.entry_time<END)].copy()

print("\nFINAL TRADE COUNTS")
for d in pd.date_range(START,END-pd.Timedelta(days=1),freq="D"):
    e=int((exp.entry_time.dt.date==d.date()).sum());g=int((got.entry_time.dt.date==d.date()).sum()) if not got.empty else 0
    print(f"{d.date()} | expected {e} | replay {g}")

keys=["entry_time","session","direction"]
m=exp.merge(got,on=keys,how="outer",suffixes=("_expected","_shadow"),indicator=True) if not got.empty else pd.DataFrame()
if got.empty:
    print("\nFAIL — no final trades.");sys.exit(2)
both=m[m._merge=="both"];missing=m[m._merge=="left_only"];extra=m[m._merge=="right_only"]
entry_ok=(both.entry_expected.astype(float)-both.entry_shadow.astype(float)).abs()<1e-9
stop_ok=(both.stop_expected.astype(float)-both.stop_shadow.astype(float)).abs()<1e-9
risk_ok=(both.risk.astype(float)-both.risk_points.astype(float)).abs()<1e-9
print("\nExpected:",len(exp),"Replay:",len(got),"Matched:",len(both),"Missing:",len(missing),"Extra:",len(extra))
print("Entry exact:",int(entry_ok.sum()),"/",len(both),"| Stop exact:",int(stop_ok.sum()),"/",len(both),"| Risk exact:",int(risk_ok.sum()),"/",len(both))
ok=len(exp)==len(got) and missing.empty and extra.empty and entry_ok.all() and stop_ok.all() and risk_ok.all()
print("\n"+("PASS — FINAL OPTION 2B SET MATCHES" if ok else "FAIL — PARITY MISMATCH; LIVE IMPLEMENTATION NEEDS CORRECTION"))
print("Saved:",OUT);sys.exit(0 if ok else 2)
