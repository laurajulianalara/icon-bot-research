#!/usr/bin/env python3
"""THE ICON — FAST targeted September 75-trade causal audit.

Tests ONLY the frozen 75 benchmark trades. For each benchmark trade, evaluates
the exact entry boundary with history cut off there. No full September
minute-by-minute replay. No future next-extreme information is supplied.
Existing strategy/data files are never modified.
"""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

EXPECTED=Path("data/reports/2026-09_trades.csv")
OUT=Path("data/reports/2026-09_75_causal_finalization_audit.csv")
if not EXPECTED.exists(): raise RuntimeError(f"Missing {EXPECTED}")

def et_series(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

exp=pd.read_csv(EXPECTED)
exp["entry_time"]=et_series(exp["entry_time"])
exp=exp[(exp.entry_time>=pd.Timestamp("2026-09-01",tz=live.TZ))&
        (exp.entry_time<pd.Timestamp("2026-10-01",tz=live.TZ))].copy()
if len(exp)!=75:
    raise RuntimeError(f"Benchmark guard failed: expected exactly 75 September trades, found {len(exp)}")

# Load source once, not once per minute.
frames=[]
hist=pd.read_parquet(live.HIST)[live.NEED].copy()
hist["time_ny"]=et_series(hist["time_ny"])
frames.append(hist)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(live.NEED).issubset(q.columns): continue
        q=q[live.NEED].copy(); q["time_ny"]=et_series(q["time_ny"]); frames.append(q)
    except Exception:
        pass
one=(pd.concat(frames,ignore_index=True)
       .drop_duplicates(["time_ny","ticker"],keep="last")
       .sort_values("time_ny").reset_index(drop=True))
one=one[(one.time_ny>=pd.Timestamp("2026-08-28",tz=live.TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=live.TZ))].copy()

rows=[]
for n,r in exp.reset_index(drop=True).iterrows():
    t=pd.Timestamp(r.entry_time)
    # At entry boundary t, bars strictly before t are closed. The t bar's OPEN
    # is live-knowable; its future H/L/C are deliberately not supplied.
    closed=one[one.time_ny<t].tail(6500).copy()
    op=one[one.time_ny==t]
    if op.empty:
        rows.append({**r.to_dict(),"causally_reproduced":False,"reason":"MISSING_ENTRY_OPEN","causal_matches":0})
        continue
    live_open=op.iloc[0][live.NEED].to_dict()
    sigs=live.evaluate(closed,live_open=live_open)
    matches=[x for x in sigs if pd.Timestamp(x["entry_time_et"])==t
             and x["session"]==r["session"] and x["direction"]==r["direction"]]
    rows.append({**r.to_dict(),"causally_reproduced":bool(matches),
                 "reason":"MATCH" if matches else "NOT_EMITTED_AT_ENTRY_BOUNDARY",
                 "causal_matches":len(matches),
                 "causal_candidate_time":matches[0]["candidate_time_et"] if matches else None,
                 "causal_entry":matches[0]["entry"] if matches else None,
                 "causal_stop":matches[0]["stop"] if matches else None,
                 "causal_v15":matches[0]["v15_score"] if matches else None})
    print(f"[{n+1:02d}/75] {t} {r['session']} {r['direction']} -> {'MATCH' if matches else 'MISS'}")

out=pd.DataFrame(rows)
OUT.parent.mkdir(parents=True,exist_ok=True)
out.to_csv(OUT,index=False)
ok=int(out.causally_reproduced.sum())
print("\n"+"="*80)
print("FAST SEPTEMBER 75-TRADE CAUSAL AUDIT")
print("="*80)
print("Frozen benchmark: 75")
print("Reproduced using only information available at entry:",ok)
print("Not reproduced:",75-ok)
print("Result:",f"{ok}/75")
if ok<75:
    print("\nMISSES")
    print(out.loc[~out.causally_reproduced,["entry_time","session","direction","reason"]].to_string(index=False))
print("\nSaved:",OUT)
print("No strategy thresholds or existing data were changed.")
