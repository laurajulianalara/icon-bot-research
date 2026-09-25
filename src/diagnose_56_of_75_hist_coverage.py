#!/usr/bin/env python3
"""THE ICON — diagnose why only 56/75 corrected September trades match HIST candidates.
FAST / READ ONLY. Uses existing files only. No API calls, no strategy changes.
"""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

GOOD=Path("data/reports/2026-09_trades.csv")
HIST=Path(live.HIST)
for p in [GOOD,HIST]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s,errors="coerce")
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

good=pd.read_csv(GOOD)
ec="entry_time_et" if "entry_time_et" in good.columns else "entry_time"
cc="candidate_time_et" if "candidate_time_et" in good.columns else "candidate_time"
good["entry_time"]=et(good[ec]); good["candidate_time"]=et(good[cc])

one=pd.read_parquet(HIST)[live.NEED].copy(); one["time_ny"]=et(one.time_ny)
cand=live.build_candidates(one)
ck={(str(r.time_ny),str(r.session),str(r.direction)) for _,r in cand.iterrows()}
bars=set(one.time_ny.astype(str))
hist_min=one.time_ny.min(); hist_max=one.time_ny.max()

rows=[]
for _,r in good.iterrows():
    ckey=(str(r.candidate_time),str(r.session),str(r.direction))
    cand_bar=str(r.candidate_time) in bars
    entry_bar=str(r.entry_time) in bars
    candidate_match=ckey in ck
    if candidate_match and entry_bar: reason="MATCH"
    elif r.candidate_time>hist_max or r.entry_time>hist_max: reason="AFTER_HIST_CUTOFF"
    elif not cand_bar: reason="CANDIDATE_1M_BAR_MISSING"
    elif not entry_bar: reason="ENTRY_1M_BAR_MISSING"
    else: reason="BAR_EXISTS_BUT_NOT_CANDIDATE_IN_HIST"
    rows.append({"entry_time":r.entry_time,"candidate_time":r.candidate_time,"session":r.session,
                 "direction":r.direction,"candidate_bar_in_hist":cand_bar,"entry_bar_in_hist":entry_bar,
                 "candidate_match_in_hist":candidate_match,"reason":reason})

q=pd.DataFrame(rows)
print("="*100)
print("THE ICON — WHY ONLY 56/75 VALID SEPTEMBER TRADES MATCH HIST")
print("="*100)
print("HIST coverage:",hist_min,"->",hist_max)
print("Corrected September trades:",len(q))
print("Full matches:",int((q.reason=="MATCH").sum()))
print("\nREASONS")
print(q.reason.value_counts().to_string())
print("\nNON-MATCHED TRADES")
print(q[q.reason!="MATCH"].to_string(index=False))
print("\nNON-MATCHES BY DATE")
print(pd.crosstab(q.loc[q.reason!="MATCH","entry_time"].dt.date,q.loc[q.reason!="MATCH","reason"]).to_string())
out=Path("data/reports/2026-09_valid_trade_hist_coverage_diagnosis.csv")
q.to_csv(out,index=False)
print("\nSaved:",out)
print("READ ONLY — no data, strategy, thresholds, or live engine changed.")
