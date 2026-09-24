#!/usr/bin/env python3
"""Diagnose why today's causal-extra Option 2B trades later disappear.

No strategy changes. No orders. Tracks each causal emission through every
subsequent minute and reports the first minute it is absent from evaluate().
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY=pd.Timestamp.now(tz=live.TZ).normalize(); END=DAY+pd.Timedelta(days=1)
EXPECTED=Path("data/reports/"+DAY.strftime("%Y-%m")+"_trades.csv")
CAUSAL=Path("data/reports/"+DAY.strftime("%Y-%m-%d")+"_true_bar_by_bar.csv")

def norm(x):
    x=x.copy();x["time_ny"]=pd.to_datetime(x.time_ny)
    if x.time_ny.dt.tz is None:x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ)
    else:x["time_ny"]=x.time_ny.dt.tz_convert(live.TZ)
    return x[live.NEED]

if not EXPECTED.exists() or not CAUSAL.exists():
    raise RuntimeError("Run current-month report and today's true bar-by-bar test first.")

exp=pd.read_csv(EXPECTED); exp["entry_time"]=pd.to_datetime(exp.entry_time)
if exp.entry_time.dt.tz is None:exp["entry_time"]=exp.entry_time.dt.tz_localize(live.TZ)
else:exp["entry_time"]=exp.entry_time.dt.tz_convert(live.TZ)
exp=exp[(exp.entry_time>=DAY)&(exp.entry_time<END)]

ca=pd.read_csv(CAUSAL);ca["entry_time"]=pd.to_datetime(ca.entry_time_et)
keys=["entry_time","session","direction"]
extras=ca.merge(exp[keys],on=keys,how="left",indicator=True)
extras=extras[extras._merge=="left_only"].copy()
if extras.empty:
    print("No causal extras to diagnose.");sys.exit(0)

pieces=[];h=norm(pd.read_parquet(live.HIST));pieces.append(h[(h.time_ny>=DAY-pd.Timedelta(days=3))&(h.time_ny<END)])
for p in Path("data").glob("mnq_*_1m.parquet"):
    try:
        x=norm(pd.read_parquet(p))
        if ((x.time_ny>=DAY)&(x.time_ny<END)).any():pieces.append(x)
    except Exception:pass
all1=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
replay=all1[(all1.time_ny>=DAY)&(all1.time_ny<END)].copy()
base=all1[all1.time_ny<DAY].tail(5000).copy().reset_index(drop=True)

print("="*94);print("THE ICON — TODAY CAUSAL EXTRA DISAPPEARANCE DIAGNOSTIC");print("="*94)
print("No strategy changes. Tracking",len(extras),"extra causal trades.\n")

for _,e in extras.sort_values("entry_time").iterrows():
    et=pd.Timestamp(e.entry_time)
    # Rebuild context through entry minute, then advance one bar at a time.
    ctx=base.copy()
    pre=replay[replay.time_ny<=et]
    for _,b in pre.iterrows():ctx=pd.concat([ctx,pd.DataFrame([b])],ignore_index=True)
    target=e.signal_id
    at_entry={x["signal_id"]:x for x in live.evaluate(ctx)}
    present=target in at_entry
    first_absent=None; replacement=None
    for _,b in replay[replay.time_ny>et].iterrows():
        ctx=pd.concat([ctx,pd.DataFrame([b])],ignore_index=True)
        nowset={x["signal_id"]:x for x in live.evaluate(ctx)}
        if target not in nowset:
            first_absent=b.time_ny
            # capture same-day selected set at disappearance for context
            replacement=list(nowset.values())
            break
    print("-"*94)
    print(f"EXTRA: {et} | {e.session} | {e.direction} | Entry {e.entry} | Stop {e.stop}")
    print("Present exactly at entry:",present)
    print("First absent after entry:",first_absent if first_absent is not None else "NEVER (still selected at end)")
    if first_absent is not None:
        later=[x for x in replacement if x["date_et"]==str(DAY.date())]
        print("Selected-set size at disappearance:",len(later))
        # Same session/direction candidates selected around disappearance.
        ss=[x for x in later if x["session"]==e.session and x["direction"]==e.direction]
        if ss:
            print("Same session/direction selected then:")
            for x in ss:print(" ",x["entry_time_et"],"candidate",x["candidate_time_et"],"entry",x["entry"],"stop",x["stop"])
        else:print("Same session/direction selected then: NONE")
    print()

print("="*94)
print("Interpretation: if a trade is present at entry and disappears only later, the next diagnostic target is")
print("the exact rule/state change at that first-absent minute (supersession vs daily cap/set recomputation).")
