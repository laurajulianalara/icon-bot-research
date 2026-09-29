#!/usr/bin/env python3
"""THE ICON — September 2026 strict causal rerun.

READ-ONLY. Replays the production Option 2B evaluator chronologically using
only closed 1m bars plus the just-opened entry bar. The six/day cap is applied
exactly as shadow-live main() applies it. The legacy report is comparison only.

No strategy/filter/threshold/session/data/execution changes.
"""
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ; NEED=live.NEED
LEGACY=Path("data/reports/2026-09_trades.csv")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

frames=[]
h=pd.read_parquet(live.HIST)[NEED].copy(); h["time_ny"]=et(h.time_ny); frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(NEED).issubset(q.columns): continue
        q=q[NEED].copy(); q["time_ny"]=et(q.time_ny); frames.append(q)
    except Exception: pass
one=(pd.concat(frames,ignore_index=True)
     .drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))
one=one[(one.time_ny>=pd.Timestamp("2026-08-28",tz=TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=TZ))].copy()

sep=one[(one.time_ny>=pd.Timestamp("2026-09-01",tz=TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=TZ))].copy()

# IMPORTANT: an entry boundary may itself be outside a session (e.g. a 04:57
# London candidate enters at 05:00). Therefore evaluate every September
# 3-minute boundary present in the data; evaluate() itself controls eligibility.
boundaries=sorted(set(t for t in sep.time_ny if t.minute%3==0))

emitted={}; daily={}
future_violations=[]
for n,t in enumerate(boundaries,1):
    pos=one.index[one.time_ny==t]
    if len(pos)==0: continue
    p=int(pos[-1])
    closed=one.loc[:p-1,NEED].tail(6500).copy()
    op=one.loc[p,NEED].to_dict()

    # Mechanical audit invariant: closed input must end strictly before the
    # decision/entry boundary. live_open may expose timestamp/ticker/open only.
    if len(closed) and not (closed.time_ny.max() < t):
        future_violations.append((t,"closed_input_not_before_boundary",closed.time_ny.max()))

    for x in live.evaluate(closed,live_open=op):
        xt=pd.Timestamp(x["entry_time_et"])
        if xt!=t: continue
        ct=pd.Timestamp(x["candidate_time_et"])
        # Candidate + m1 + m2 must be complete before entry T+3.
        if not (ct < xt):
            future_violations.append((t,"candidate_not_before_entry",ct))
        day=str(x["date_et"])
        if daily.get(day,0)>=6: continue
        k=(xt,str(x["session"]),str(x["direction"]),ct)
        if k in emitted: continue
        emitted[k]=x; daily[day]=daily.get(day,0)+1
    if n%1000==0: print(f"Checked {n}/{len(boundaries)} causal boundaries...")

rows=sorted(emitted.values(),key=lambda x:pd.Timestamp(x["entry_time_et"]))
out=pd.DataFrame(rows)

print("\n"+"="*96)
print("THE ICON — SEPTEMBER STRICT CAUSAL RERUN")
print("="*96)
print("September 3-minute decision boundaries checked:",len(boundaries))
print("Causal FINAL trades:",len(out))
print("Future-data invariant violations:",len(future_violations))
print("Max trades on any day:",max(daily.values()) if daily else 0)
print("Days above 6:",sum(v>6 for v in daily.values()))

if future_violations:
    print("\nFUTURE-DATA VIOLATIONS")
    for x in future_violations[:30]: print(x)

if not out.empty:
    show=["candidate_time_et","entry_time_et","session","direction","entry","stop","v15_score"]
    print("\nCAUSAL FINAL TRADES")
    print(out[show].to_string(index=False))
    print("\nTRADES BY DATE")
    print(out.groupby("date_et").size().to_string())

# Legacy report is diagnostic comparison only; it does NOT determine causal selection.
if LEGACY.exists():
    b=pd.read_csv(LEGACY)
    b["entry_time"]=et(b["entry_time"]); b["candidate_time"]=et(b["candidate_time"])
    b=b[(b.entry_time.dt.year==2026)&(b.entry_time.dt.month==9)].copy()
    def kb(r): return (pd.Timestamp(r.entry_time),str(r.session),str(r.direction),pd.Timestamp(r.candidate_time))
    old=set(kb(r) for _,r in b.iterrows())
    new=set(emitted)
    print("\nLEGACY COMPARISON ONLY")
    print("Legacy trades:",len(old))
    print("Causal trades:",len(new))
    print("Same:",len(old&new))
    print("Legacy-only:",len(old-new))
    print("Causal-only:",len(new-old))

print("\nREAD-ONLY. No strategy/filter/threshold/report/data/execution changes were made.")
