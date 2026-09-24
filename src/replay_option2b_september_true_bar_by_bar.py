#!/usr/bin/env python3
"""THE ICON — September 2026 TRUE bar-by-bar Option 2B causal replay.
Reveals one 1m bar at a time and permanently records signals at their actual entry minute.
No orders. No strategy changes.
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

START=pd.Timestamp("2026-09-01",tz=live.TZ)
EXPECTED=Path("data/reports/2026-09_trades.csv")
OUT=Path("data/reports/2026-09_true_bar_by_bar.csv")

def norm(x):
 x=x.copy();x["time_ny"]=pd.to_datetime(x.time_ny)
 x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ) if x.time_ny.dt.tz is None else x.time_ny.dt.tz_convert(live.TZ)
 return x[live.NEED]

if not EXPECTED.exists():raise RuntimeError("Run python src/icon_month_live_report.py first.")
exp=pd.read_csv(EXPECTED);exp["entry_time"]=pd.to_datetime(exp.entry_time)
exp["entry_time"]=exp.entry_time.dt.tz_localize(live.TZ) if exp.entry_time.dt.tz is None else exp.entry_time.dt.tz_convert(live.TZ)
exp=exp[exp.entry_time>=START].copy()
END=pd.Timestamp(exp.entry_time.max().date(),tz=live.TZ)+pd.Timedelta(days=1)

pieces=[];h=norm(pd.read_parquet(live.HIST));pieces.append(h[(h.time_ny>=START-pd.Timedelta(days=3))&(h.time_ny<END)])
for p in Path("data").glob("mnq_*_1m.parquet"):
 try:
  x=norm(pd.read_parquet(p))
  if ((x.time_ny>=START)&(x.time_ny<END)).any():pieces.append(x)
 except:pass
all1=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
replay=all1[(all1.time_ny>=START)&(all1.time_ny<END)].copy()
context=all1[all1.time_ny<START].tail(5000).copy().reset_index(drop=True)

# Evaluate only during strategy sessions, and trim context to keep this month-long causal replay practical.
def in_session(t):
 hhmm=t.hour*100+t.minute
 return hhmm>=2000 or hhmm<5 or 200<=hhmm<500 or 930<=hhmm<1230 or 1330<=hhmm<1700

print("="*92);print("THE ICON — SEPTEMBER TRUE BAR-BY-BAR CAUSAL REPLAY");print("="*92)
print("Window:",START.date(),"through",(END-pd.Timedelta(days=1)).date(),"| Orders: DISABLED")
print("This may take several minutes; progress prints once per date.")

emitted=[];ids=set();last_date=None
for _,bar in replay.iterrows():
 context=pd.concat([context,pd.DataFrame([bar])],ignore_index=True)
 if len(context)>6500:context=context.tail(6500).reset_index(drop=True)
 now=bar.time_ny
 if now.date()!=last_date:
  print("Replaying",now.date(),flush=True);last_date=now.date()
 if not in_session(now):continue
 for x in live.evaluate(context):
  if x["signal_id"] in ids:continue
  if pd.Timestamp(x["entry_time_et"])==now:
   emitted.append(x);ids.add(x["signal_id"])

got=pd.DataFrame(emitted)
if not got.empty:got["entry_time"]=pd.to_datetime(got.entry_time_et)
OUT.parent.mkdir(parents=True,exist_ok=True);got.to_csv(OUT,index=False)
keys=["entry_time","session","direction"]
m=exp.merge(got,on=keys,how="outer",suffixes=("_hist","_causal"),indicator=True)
both=m[m._merge=="both"].copy();missing=m[m._merge=="left_only"].copy();extra=m[m._merge=="right_only"].copy()
print("\n"+"="*92);print("SEPTEMBER CAUSAL PARITY RESULT");print("="*92)
print("Historical:",len(exp),"| Causal emitted:",len(got),"| Matched:",len(both),"| Historical-only:",len(missing),"| Causal-only extras:",len(extra))
print("\nDAILY COUNTS")
dates=sorted(set(exp.entry_time.dt.date)|set(got.entry_time.dt.date))
for d in dates:
 e=int((exp.entry_time.dt.date==d).sum());g=int((got.entry_time.dt.date==d).sum())
 print(f"{d} | historical {e:2d} | causal {g:2d} | delta {g-e:+d}")
if len(extra):
 print("\nCAUSAL-ONLY EXTRAS")
 print(extra[keys+["entry_causal","stop_causal"]].to_string(index=False))
if len(missing):
 print("\nHISTORICAL-ONLY")
 print(missing[keys+["entry_hist","stop_hist"]].to_string(index=False))
print("\nSaved:",OUT)
