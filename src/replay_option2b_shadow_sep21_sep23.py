#!/usr/bin/env python3
"""THE ICON — Option 2B candle-by-candle shadow replay, Sep 21-23 2026.

Uses the exact selector from icon_option2b_shadow_live.py. Historical Massive
1m bars are revealed one at a time. A signal is recorded only when the
simulated live clock reaches its entry minute. Then signals are compared with
the authoritative Option 2B current-month report.
"""
import os, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

START=pd.Timestamp("2026-09-21 00:00:00",tz=live.TZ)
END=pd.Timestamp("2026-09-24 00:00:00",tz=live.TZ)
EXPECTED_PATH=Path("data/reports/2026-09_trades.csv")
OUT=Path("data/reports/option2b_shadow_replay_sep21_sep23.csv")

def norm(df):
    df=df.copy(); df["time_ny"]=pd.to_datetime(df.time_ny)
    if df.time_ny.dt.tz is None:df["time_ny"]=df.time_ny.dt.tz_localize(live.TZ)
    else:df["time_ny"]=df.time_ny.dt.tz_convert(live.TZ)
    return df[live.NEED]

def load_days():
    pieces=[]
    hist=norm(pd.read_parquet(live.HIST))
    pieces.append(hist[(hist.time_ny>=START-pd.Timedelta(days=3))&(hist.time_ny<END)])
    for p in Path("data").glob("mnq_*_2026*_1m.parquet"):
        try:
            x=norm(pd.read_parquet(p))
            if ((x.time_ny>=START)&(x.time_ny<END)).any():pieces.append(x)
        except Exception:pass
    x=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
    return x

one=load_days()
replay=one[(one.time_ny>=START)&(one.time_ny<END)].copy()
context=one[one.time_ny<START].tail(5000).copy().reset_index(drop=True)
if replay.empty:raise RuntimeError("No Sep 21-23 1m data found. Run icon_month_option2b_test.py first.")

print("="*72);print("THE ICON — OPTION 2B SHADOW REPLAY | SEP 21-23, 2026");print("="*72)
print("Replay candles:",len(replay),"|",replay.time_ny.min(),"->",replay.time_ny.max())
print("Future candles hidden: YES | Orders: DISABLED")

seen=set(); rows=[]
for n,(_,bar) in enumerate(replay.iterrows(),1):
    context=pd.concat([context,pd.DataFrame([bar])],ignore_index=True)
    now=bar.time_ny
    for s in live.evaluate(context):
        # This is the live boundary: only emit when T+3 has just arrived.
        if pd.Timestamp(s["entry_time_et"])==now and s["signal_id"] not in seen:
            seen.add(s["signal_id"]); rows.append(s)
            print(f"SIGNAL {len(rows):02d} | {s['entry_time_et']} | {s['session']} | {s['direction']} | entry {s['entry']} | stop {s['stop']}")
    if n%3000==0:print("Processed",n,"/",len(replay),"1m bars...")

got=pd.DataFrame(rows)
OUT.parent.mkdir(parents=True,exist_ok=True); got.to_csv(OUT,index=False)

if not EXPECTED_PATH.exists():
    raise RuntimeError(f"{EXPECTED_PATH} missing. Run: python src/icon_month_option2b_test.py")

exp=pd.read_csv(EXPECTED_PATH)
exp["entry_time"]=pd.to_datetime(exp.entry_time)
if exp.entry_time.dt.tz is None:exp["entry_time"]=exp.entry_time.dt.tz_localize(live.TZ)
else:exp["entry_time"]=exp.entry_time.dt.tz_convert(live.TZ)
exp=exp[(exp.entry_time>=START)&(exp.entry_time<END)].copy()

print("\n"+"="*72);print("PARITY RESULT");print("="*72)
print("Expected Option 2B:",len(exp));print("Shadow replay:",len(got))

if got.empty:
    print("FAIL — shadow replay emitted no signals.");sys.exit(1)

got["entry_time"]=pd.to_datetime(got.entry_time_et)
keys=["entry_time","session","direction"]
m=exp.merge(got,on=keys,how="outer",suffixes=("_expected","_shadow"),indicator=True)
missing=m[m._merge=="left_only"]; extra=m[m._merge=="right_only"]; both=m[m._merge=="both"].copy()
price_ok=(both.entry_expected.astype(float)-both.entry_shadow.astype(float)).abs()<1e-9
stop_ok=(both.stop_expected.astype(float)-both.stop_shadow.astype(float)).abs()<1e-9
risk_ok=(both.risk.astype(float)-both.risk_points.astype(float)).abs()<1e-9 if "risk" in both else pd.Series([False]*len(both))

for d in pd.date_range(START,END-pd.Timedelta(days=1),freq="D"):
    ds=str(d.date()); e=int((exp.entry_time.dt.date==d.date()).sum()); g=int((got.entry_time.dt.date==d.date()).sum())
    print(f"{ds}: expected {e} | shadow {g}")

print("Matched:",len(both),"| Missing:",len(missing),"| Extra:",len(extra))
print("Entry price exact:",int(price_ok.sum()),"/",len(both))
print("Stop exact:",int(stop_ok.sum()),"/",len(both))
print("Risk exact:",int(risk_ok.sum()),"/",len(both))
ok=len(exp)==len(got) and missing.empty and extra.empty and price_ok.all() and stop_ok.all() and risk_ok.all()
print("\n"+("PASS — SHADOW LIVE ENGINE MATCHES FROZEN OPTION 2B" if ok else "FAIL — PARITY MISMATCH; DO NOT ADVANCE TO EXECUTION"))
print("Saved:",OUT)
sys.exit(0 if ok else 2)
