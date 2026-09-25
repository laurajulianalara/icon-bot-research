#!/usr/bin/env python3
"""
THE ICON — FAST TARGETED PRODUCTION-EQUIVALENCE DIAGNOSTIC

READ ONLY.
Instead of replaying all September minute-by-minute, this replays only short
windows around representative benchmark and known-problem boundaries, while
preserving the current shadow-live event semantics:
  pending minute -> previous minute closes -> current minute is live_open
  -> evaluate(closed, live_open=current)
  -> only signals stamped exactly at current live_open can emit.

No production log/state/report/market data is written.
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

def nt(s):
    x=pd.to_datetime(s,errors="coerce")
    if getattr(x.dt,"tz",None) is None:return x.dt.tz_localize(TZ)
    return x.dt.tz_convert(TZ)

one=pd.read_parquet(HIST)[NEED].copy()
one["time_ny"]=nt(one["time_ny"])
one=one.dropna(subset=["time_ny"]).sort_values("time_ny").drop_duplicates(["time_ny","ticker"],keep="last").reset_index(drop=True)

b=pd.read_csv(BENCH)
def col(*names):
    for n in names:
        if n in b.columns:return n
    raise SystemExit(f"Missing benchmark column {names}; columns={list(b.columns)}")
ec=col("entry_time_et","entry_time","signal_time","signal_time_et")
cc=col("candidate_time_et","candidate_time")
sc=col("session"); dc=col("direction")
be=pd.to_datetime(b[ec],errors="coerce"); bc=pd.to_datetime(b[cc],errors="coerce")
if getattr(be.dt,"tz",None) is None:be=be.dt.tz_localize(TZ)
else:be=be.dt.tz_convert(TZ)
if getattr(bc.dt,"tz",None) is None:bc=bc.dt.tz_localize(TZ)
else:bc=bc.dt.tz_convert(TZ)
bench=set(zip(be,b[sc].astype(str),b[dc].astype(str),bc))

# Representative known-problem boundaries from the corrected-live audit plus
# the Sep-21 benchmark timing case. Each target gets an isolated warm-start
# window, so this is diagnostic rather than a full-month daily-cap audit.
targets=[
("KNOWN_BENCH", "2026-09-21 04:45"),
("EARLIER_BOUNDARY", "2026-09-21 04:42"),
("EXTRA", "2026-09-01 02:30"),
("EXTRA", "2026-09-01 03:39"),
("EXTRA", "2026-09-01 04:00"),
("EXTRA", "2026-09-02 02:42"),
("EXTRA", "2026-09-02 09:42"),
("MISSING", "2026-09-01 05:00"),
("MISSING", "2026-09-01 09:42"),
("MISSING", "2026-09-01 13:36"),
("MISSING", "2026-09-02 13:48"),
("MISSING", "2026-09-03 11:12"),
]
targets=[(lab,pd.Timestamp(t,tz=TZ)) for lab,t in targets]

print("="*92)
print("THE ICON — FAST TARGETED PRODUCTION-EQUIVALENCE DIAGNOSTIC")
print("="*92)
print("Targets:",len(targets))
print("Each target replays only the final few live events after a large closed-history warm start.\n")

results=[]
for z,(label,target) in enumerate(targets,1):
    # Warm history through target-6m gives evaluator full ATR/session context.
    # Then replay target-5 through target exactly using production pending semantics.
    warm_end=target-pd.Timedelta(minutes=6)
    closed=one[one.time_ny<=warm_end].copy().tail(5000).reset_index(drop=True)
    stream=one[(one.time_ny>warm_end)&(one.time_ny<=target)].copy().reset_index(drop=True)
    pending=None; at_target=[]
    for _,rs in stream.iterrows():
        row=rs.to_dict(); row["time_ny"]=pd.Timestamp(row["time_ny"])
        if pending is not None and row["time_ny"]>pending["time_ny"]:
            closed=pd.concat([closed,pd.DataFrame([pending])],ignore_index=True)
            closed=closed.drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
            sigs=live.evaluate(closed,live_open=row)
            if row["time_ny"]==target:
                at_target=[x for x in sigs if pd.Timestamp(x["entry_time_et"])==target]
        pending=row

    expected=[k for k in bench if k[0]==target]
    emitted=[]
    for x in at_target:
        k=(pd.Timestamp(x["entry_time_et"]).tz_convert(TZ),str(x["session"]),str(x["direction"]),pd.Timestamp(x["candidate_time_et"]).tz_convert(TZ))
        emitted.append((k,x))

    exact=[x for k,x in emitted if k in bench]
    unexpected=[x for k,x in emitted if k not in bench]
    expected_missing=[k for k in expected if all(k!=ek for ek,_ in emitted)]

    print(f"[{z:02d}/{len(targets)}] {label} | {target}")
    print("  benchmark_at_boundary:",len(expected),
          "| production_emitted:",len(emitted),
          "| exact_benchmark:",len(exact),
          "| unexpected:",len(unexpected),
          "| expected_missing:",len(expected_missing))
    for k,x in emitted:
        mark="MATCH" if k in bench else "EXTRA"
        print("   ",mark,x["session"],x["direction"],"candidate",x["candidate_time_et"],
              "entry",x["entry"],"stop",x["stop"],"v15",round(x["v15_score"],6))
    if not emitted:print("    EMITTED: none")
    results.append((label,target,len(expected),len(emitted),len(exact),len(unexpected),len(expected_missing)))

print("\n"+"="*92)
print("TARGETED SUMMARY")
print("="*92)
df=pd.DataFrame(results,columns=["label","target","benchmark","emitted","matched","extras","missing"])
print(df.to_string(index=False))
print("\nTotals across targeted boundaries only:")
print("Benchmark:",int(df.benchmark.sum()))
print("Production emitted:",int(df.emitted.sum()))
print("Matched:",int(df.matched.sum()))
print("Extras:",int(df.extras.sum()))
print("Missing:",int(df.missing.sum()))
print("\nREAD-ONLY. No strategy thresholds or production files changed.")
print("If these targeted production results differ from the prior corrected-live audit at the same timestamps, the prior replay harness is not production-equivalent.")
