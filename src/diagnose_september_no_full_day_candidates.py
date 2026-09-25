#!/usr/bin/env python3
"""THE ICON — Diagnose September NO_FULL_DAY_CANDIDATE extras.

READ ONLY. No strategy changes.

For each causal-only extra previously classified NO_FULL_DAY_CANDIDATE, compare:
- the candidate as it existed at live/event time
- the completed 3m bucket in full-day data
- session membership
- completed-bar running session high/low immediately before that bucket
- whether the completed bucket still qualifies as a new session extreme

This isolates why a transient causal candidate is absent from the completed
full-day candidate set.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

PROOF=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
CAUSAL=Path("data/reports/2026-09_true_bar_by_bar.csv")
for p in [PROOF,CAUSAL,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

proof=pd.read_csv(PROOF)
proof["entry_time"]=et(proof.entry_time)
proof["candidate_time"]=et(proof.candidate_time)
bad=proof[proof.original_simulate_result=="NO_FULL_DAY_CANDIDATE"].copy().sort_values("entry_time")

one=pd.read_parquet(live.HIST)[live.NEED].copy(); one["time_ny"]=et(one.time_ny)
start=pd.Timestamp("2026-09-17",tz=live.TZ); end=pd.Timestamp("2026-09-25",tz=live.TZ)
one=one[(one.time_ny>=start)&(one.time_ny<end)].sort_values("time_ny").reset_index(drop=True)

# Build completed 3m bars exactly like live.build_candidates.
z=one.set_index("time_ny")
three=z.resample("3min",label="left",closed="left").agg(
    open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),
    ticker=("ticker","last"),n=("close","count"))
three=three[(three.n==3)&three.open.notna()].reset_index()
three["session"]=three.time_ny.apply(live.session_name)
three=three[three.session.notna()].copy()
three["date"]=three.time_ny.dt.date

# For every completed bucket, record running session extrema BEFORE it.
pre={}
for (day,sess),g in three.groupby(["date","session"],sort=False):
    rh=None; rl=None
    for _,r in g.sort_values("time_ny").iterrows():
        pre[(tkey(r.time_ny),sess)]=(rh,rl)
        rh=float(r.high) if rh is None else max(rh,float(r.high))
        rl=float(r.low) if rl is None else min(rl,float(r.low))

tmap={(tkey(r.time_ny),r.session):r for _,r in three.iterrows()}

# Reconstruct what was visible exactly at candidate timestamp: the bucket has
# only its first 1m bar finalized at that instant. Compare that partial state
# with the eventual completed 3m H/L.
one_map={tkey(r.time_ny):r for _,r in one.iterrows()}
rows=[]
for _,x in bad.iterrows():
    key=(tkey(x.candidate_time),x.session)
    bar=tmap.get(key)
    first=one_map.get(tkey(x.candidate_time))
    rh,rl=pre.get(key,(None,None))
    reason="UNRESOLVED"
    live_partial_extreme=np.nan; completed_extreme=np.nan
    partial_qual=False; complete_qual=False
    if bar is None:
        reason="NO_COMPLETED_3M_BUCKET_OR_SESSION"
    else:
        if x.direction=="LONG":
            live_partial_extreme=float(first.low) if first is not None else np.nan
            completed_extreme=float(bar.low)
            partial_qual=(rl is not None and np.isfinite(live_partial_extreme) and live_partial_extreme<rl)
            complete_qual=(rl is not None and completed_extreme<rl)
        else:
            live_partial_extreme=float(first.high) if first is not None else np.nan
            completed_extreme=float(bar.high)
            partial_qual=(rh is not None and np.isfinite(live_partial_extreme) and live_partial_extreme>rh)
            complete_qual=(rh is not None and completed_extreme>rh)

        # If the completed bar IS a new extreme, it should be in build_candidates;
        # absence then points to a different provenance/state issue.
        if partial_qual and not complete_qual:
            reason="PARTIAL_BUCKET_LOOKED_EXTREME_BUT_COMPLETED_BUCKET_DID_NOT"
        elif complete_qual:
            reason="COMPLETED_BUCKET_IS_EXTREME__CANDIDATE_KEY_OR_STATE_MISMATCH"
        elif not partial_qual:
            reason="FIRST_MINUTE_NOT_EXTREME__LIVE_CONTEXT_RUNNING_STATE_DIFFERS"

    rows.append({
      "date":x.entry_time.date(),"entry_time":x.entry_time,"candidate_time":x.candidate_time,
      "session":x.session,"direction":x.direction,
      "prior_running_high":rh,"prior_running_low":rl,
      "first_1m_extreme":live_partial_extreme,"completed_3m_extreme":completed_extreme,
      "partial_qualifies_vs_full_day_prior":partial_qual,
      "completed_qualifies":complete_qual,"diagnosis":reason})

out=pd.DataFrame(rows)
print("="*124)
print("THE ICON — SEPTEMBER NO_FULL_DAY_CANDIDATE DIAGNOSTIC")
print("="*124)
print(f"NO_FULL_DAY_CANDIDATE extras tested: {len(out)}")
print("\nDIAGNOSIS")
print(out.diagnosis.value_counts().to_string())
print("\nBY DAY")
print(pd.crosstab(out.date,out.diagnosis).to_string())
print("\nDETAIL")
print(out.to_string(index=False))
save=Path("data/reports/2026-09_no_full_day_candidate_diagnosis.csv")
out.to_csv(save,index=False)
print("\nSaved:",save)
print("READ ONLY — no Option 2B strategy/live code or thresholds changed.")
