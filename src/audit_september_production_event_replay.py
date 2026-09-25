#!/usr/bin/env python3
"""
THE ICON — SEPTEMBER PRODUCTION-EQUIVALENT EVENT REPLAY

READ ONLY. Replays September 2026 minute bars through the same event semantics
used by icon_option2b_shadow_live.py:
- current AM minute is pending/live_open
- previous pending minute becomes closed only when the next minute arrives
- evaluate(closed, live_open=current)
- emit only signals whose entry timestamp equals the current live-open minute
- dedupe by signal_id
- cap FINAL emitted trades at 6/day

This does not write the production signal log/state.
"""
import sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import icon_option2b_shadow_live as live

HIST=ROOT/"data/mnq_continuous_1m.parquet"
BENCH=ROOT/"data/reports/2026-09_trades.csv"
TZ="America/New_York"
NEED=["time_ny","ticker","open","high","low","close","volume"]

def norm_time(s):
    x=pd.to_datetime(s,errors="coerce")
    if getattr(x.dt,"tz",None) is None:
        return x.dt.tz_localize(TZ)
    return x.dt.tz_convert(TZ)

def key_from_signal(x):
    return (
        pd.Timestamp(x["entry_time_et"]).tz_convert(TZ),
        str(x["session"]),
        str(x["direction"]),
        pd.Timestamp(x["candidate_time_et"]).tz_convert(TZ),
    )

def benchmark_key_cols(q):
    # tolerate reporter column naming changes
    choices={
        "entry":["entry_time_et","entry_time","signal_time","signal_time_et"],
        "candidate":["candidate_time_et","candidate_time"],
        "session":["session"],
        "direction":["direction"],
    }
    out={}
    for k,names in choices.items():
        for n in names:
            if n in q.columns:
                out[k]=n; break
        if k not in out:
            raise SystemExit(f"Benchmark missing {k}; columns={list(q.columns)}")
    return out

print("="*86)
print("THE ICON — SEPTEMBER PRODUCTION-EQUIVALENT EVENT REPLAY")
print("="*86)

one=pd.read_parquet(HIST)[NEED].copy()
one["time_ny"]=norm_time(one["time_ny"])
one=one.dropna(subset=["time_ny"]).sort_values("time_ny").drop_duplicates(["time_ny","ticker"],keep="last")
sep=one[(one.time_ny>=pd.Timestamp("2026-09-01",tz=TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=TZ))].reset_index(drop=True)
# Give production evaluator enough pre-September ATR/resample history, exactly as
# bootstrap does, while never exposing future September rows.
pre=one[one.time_ny<pd.Timestamp("2026-09-01",tz=TZ)].tail(5000).reset_index(drop=True)
closed=pre.copy()

bench=pd.read_csv(BENCH)
bc=benchmark_key_cols(bench)
be=pd.to_datetime(bench[bc["entry"]],errors="coerce")
bt=pd.to_datetime(bench[bc["candidate"]],errors="coerce")
if getattr(be.dt,"tz",None) is None: be=be.dt.tz_localize(TZ)
else: be=be.dt.tz_convert(TZ)
if getattr(bt.dt,"tz",None) is None: bt=bt.dt.tz_localize(TZ)
else: bt=bt.dt.tz_convert(TZ)
bench_keys=set(zip(be,bench[bc["session"]].astype(str),bench[bc["direction"]].astype(str),bt))

logged=set(); daily={}; emitted=[]
pending=None
focus_times={
    pd.Timestamp("2026-09-21 04:42",tz=TZ),
    pd.Timestamp("2026-09-21 04:45",tz=TZ),
}

for n,row_s in sep.iterrows():
    row=row_s.to_dict()
    row["time_ny"]=pd.Timestamp(row["time_ny"])
    if pending is not None and row["time_ny"]>pending["time_ny"]:
        closed=pd.concat([closed,pd.DataFrame([pending])],ignore_index=True)
        closed=closed.drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
        candidates=live.evaluate(closed,live_open=row)
        at_boundary=[]
        for x in candidates:
            if x["signal_id"] in logged:
                continue
            if pd.Timestamp(x["entry_time_et"]) != row["time_ny"]:
                continue
            day=x["date_et"]
            if daily.get(day,0)>=6:
                continue
            logged.add(x["signal_id"])
            daily[day]=daily.get(day,0)+1
            emitted.append(x)
            at_boundary.append(x)
        if row["time_ny"] in focus_times:
            print("\nFOCUS",row["time_ny"])
            print("closed_through:",closed.iloc[-1].time_ny,"live_open:",row["time_ny"])
            if not at_boundary: print("EMITTED: none")
            for x in at_boundary:
                print("EMITTED:",x["signal_id"],"entry",x["entry"],"stop",x["stop"],"v15",round(x["v15_score"],6))
    pending=row
    if (n+1)%5000==0:
        print(f"Processed {n+1}/{len(sep)} live minute events...")

emit_keys={key_from_signal(x) for x in emitted}
matched=bench_keys & emit_keys
missing=bench_keys-emit_keys
extras=emit_keys-bench_keys

print("\n"+"="*86)
print("RESULT — ACTUAL SHADOW-LIVE EVENT SEMANTICS")
print("="*86)
print("Historical benchmark:",len(bench_keys))
print("Production-event emitted:",len(emit_keys))
print("MATCHED:",len(matched))
print("MISSING:",len(missing))
print("EXTRAS:",len(extras))
print("Duplicate IDs suppressed:",len(emitted)-len(emit_keys))
print("\nFIRST 20 MISSING")
for k in sorted(missing)[:20]: print(k)
print("\nFIRST 20 EXTRAS")
bykey={key_from_signal(x):x for x in emitted}
for k in sorted(extras)[:20]:
    x=bykey[k]
    print(k,"entry",x["entry"],"stop",x["stop"],"v15",round(x["v15_score"],6))

print("\nREAD-ONLY: production log/state, strategy thresholds, reports, and market data were not changed.")
print("This test mirrors the current shadow-live pending/closed/live_open/emission semantics.")
