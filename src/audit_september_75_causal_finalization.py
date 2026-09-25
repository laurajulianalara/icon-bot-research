#!/usr/bin/env python3
"""THE ICON — focused timing trace for known Sep 21 04:45 benchmark trade.

Diagnostic only. No strategy/data mutation.
Shows candidate timestamps and evaluate() emissions around the known trade
under several causal cutoffs so we can align historical vs live timestamping.
"""
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TARGET=pd.Timestamp("2026-09-21 04:45:00",tz=live.TZ)
START=TARGET-pd.Timedelta(minutes=30)

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

frames=[]
h=pd.read_parquet(live.HIST)[live.NEED].copy(); h["time_ny"]=et(h.time_ny); frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(live.NEED).issubset(q.columns): continue
        q=q[live.NEED].copy();q["time_ny"]=et(q.time_ny);frames.append(q)
    except Exception: pass
one=(pd.concat(frames,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))
one=one[(one.time_ny>=TARGET-pd.Timedelta(days=4))&(one.time_ny<=TARGET+pd.Timedelta(minutes=2))].copy()

print("="*88)
print("SEP 21 04:45 KNOWN-CORRECT TRADE — TIMING TRACE")
print("="*88)

# Full local candidate view: timestamps only, to identify the historical candidate chain.
c=live.build_candidates(one)
w=c[(c.time_ny>=START)&(c.time_ny<=TARGET)]
print("\nCANDIDATES 04:15–04:45")
if w.empty: print("NONE")
else: print(w[["time_ny","session","direction","extreme","next_same_extreme_time"]].to_string(index=False))

print("\nCAUSAL ENTRY-BOUNDARY CHECKS")
for t in pd.date_range(TARGET-pd.Timedelta(minutes=9),TARGET,freq="1min"):
    closed=one[one.time_ny<t].tail(6500).copy()
    op=one[one.time_ny==t]
    if op.empty:
        print(t,"NO OPEN BAR");continue
    sigs=live.evaluate(closed,live_open=op.iloc[0][live.NEED].to_dict())
    near=[x for x in sigs if x["session"]=="LONDON" and x["direction"]=="SHORT"
          and pd.Timestamp(x["entry_time_et"])>=TARGET-pd.Timedelta(minutes=15)]
    print(f"boundary {t.strftime('%H:%M')} | emitted:",[(x["candidate_time_et"],x["entry_time_et"]) for x in near])

print("\nTARGET benchmark entry:",TARGET)
print("Diagnostic only — no files/data/thresholds changed.")
