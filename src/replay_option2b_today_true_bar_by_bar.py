#!/usr/bin/env python3
"""THE ICON — TODAY TRUE BAR-BY-BAR OPTION 2B CAUSAL REPLAY

Reveals today's MNQ 1m candles one at a time. Once the live selector emits a
trade at its entry minute, that trade is permanently retained. No orders.
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY=pd.Timestamp.now(tz=live.TZ).normalize()
END=DAY+pd.Timedelta(days=1)
EXPECTED=Path("data/reports/"+DAY.strftime("%Y-%m")+"_trades.csv")
OUT=Path("data/reports/"+DAY.strftime("%Y-%m-%d")+"_true_bar_by_bar.csv")

def norm(x):
    x=x.copy(); x["time_ny"]=pd.to_datetime(x.time_ny)
    if x.time_ny.dt.tz is None:x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ)
    else:x["time_ny"]=x.time_ny.dt.tz_convert(live.TZ)
    return x[live.NEED]

pieces=[]
h=norm(pd.read_parquet(live.HIST))
pieces.append(h[(h.time_ny>=DAY-pd.Timedelta(days=3))&(h.time_ny<END)])
for p in Path("data").glob("mnq_*_1m.parquet"):
    try:
        x=norm(pd.read_parquet(p))
        if ((x.time_ny>=DAY)&(x.time_ny<END)).any():pieces.append(x)
    except Exception:pass

all1=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
replay=all1[(all1.time_ny>=DAY)&(all1.time_ny<END)].copy()
context=all1[all1.time_ny<DAY].tail(5000).copy().reset_index(drop=True)
if replay.empty:raise RuntimeError("No data for today.")

# True causal emission: after each newly revealed 1m bar, evaluate only with
# context available at that instant. A trade is accepted only when its entry
# minute has just arrived; once accepted it can never be removed.
emitted=[]; ids=set()
for _,bar in replay.iterrows():
    context=pd.concat([context,pd.DataFrame([bar])],ignore_index=True)
    now=bar.time_ny
    for x in live.evaluate(context):
        if x["signal_id"] in ids:continue
        if pd.Timestamp(x["entry_time_et"])==now:
            emitted.append(x);ids.add(x["signal_id"])

got=pd.DataFrame(emitted)
if not got.empty:got["entry_time"]=pd.to_datetime(got.entry_time_et)
OUT.parent.mkdir(parents=True,exist_ok=True);got.to_csv(OUT,index=False)

if not EXPECTED.exists():raise RuntimeError("Run python src/icon_month_live_report.py first.")
exp=pd.read_csv(EXPECTED);exp["entry_time"]=pd.to_datetime(exp.entry_time)
if exp.entry_time.dt.tz is None:exp["entry_time"]=exp.entry_time.dt.tz_localize(live.TZ)
else:exp["entry_time"]=exp.entry_time.dt.tz_convert(live.TZ)
exp=exp[(exp.entry_time>=DAY)&(exp.entry_time<END)].copy()

print("="*86);print("THE ICON — TODAY TRUE BAR-BY-BAR CAUSAL REPLAY");print("="*86)
print("Date:",DAY.date(),"| 1m bars revealed:",len(replay),"| Orders: DISABLED")
print("Future bars available at decision time: NO")
keys=["entry_time","session","direction"]
if got.empty:
    print("\nREPORT:",len(exp),"| BAR-BY-BAR EMITTED: 0")
    print("FAIL — no causal emissions");sys.exit(2)

m=exp.merge(got,on=keys,how="outer",suffixes=("_report","_causal"),indicator=True)
both=m[m._merge=="both"].copy();missing=m[m._merge=="left_only"];extra=m[m._merge=="right_only"]
both["entry_exact"]=(both.entry_report.astype(float)-both.entry_causal.astype(float)).abs()<1e-9
both["stop_exact"]=(both.stop_report.astype(float)-both.stop_causal.astype(float)).abs()<1e-9

print("\nREPORT:",len(exp),"| BAR-BY-BAR EMITTED:",len(got),"| MATCHED:",len(both),"| MISSING:",len(missing),"| EXTRA:",len(extra))
print("\nCAUSAL MATCHED TRADES")
cols=["entry_time","session","direction","entry_report","entry_causal","stop_report","stop_causal","entry_exact","stop_exact"]
print(both[cols].to_string(index=False) if len(both) else "None")
if len(missing):print("\nMISSING\n"+missing[keys+["entry_report","stop_report"]].to_string(index=False))
if len(extra):print("\nEXTRA\n"+extra[keys+["entry_causal","stop_causal"]].to_string(index=False))

ok=len(exp)==len(got) and missing.empty and extra.empty and both.entry_exact.all() and both.stop_exact.all()
print("\n"+("="*86))
print("PASS — TODAY TRUE BAR-BY-BAR CAUSAL PARITY" if ok else "FAIL — TODAY BAR-BY-BAR CAUSAL PARITY MISMATCH")
print("="*86)
print("Saved:",OUT)
sys.exit(0 if ok else 2)
