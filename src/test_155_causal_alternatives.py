#!/usr/bin/env python3
"""THE ICON — fast causal alternatives study for the 155 supersession cases.

READ ONLY. No slow bar-by-bar replay. No production strategy changes.

Uses the already-saved 155 supersession proof plus the 1m historical file to
measure only information available AT the original entry timestamp. It tests
simple causal gates that do not delay the market entry:
  A) entry open itself has already crossed the candidate extreme;
  B) entry open is at/beyond the prior session extreme;
  C) distance from entry open to candidate extreme in candidate ATR units.

This is a diagnostic. It does not promote any filter automatically.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

PROOF=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
HISTTR=Path("data/reports/2026-09_trades.csv")
for p in [PROOF,HISTTR,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s,errors="coerce")
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

proof=pd.read_csv(PROOF)
proof=proof[proof.original_simulate_result.eq("SUPERSEDED")].copy()
proof["entry_time"]=et(proof.entry_time)
proof["candidate_time"]=et(proof.candidate_time)

one=pd.read_parquet(live.HIST)[live.NEED].copy()
one["time_ny"]=et(one.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True)
cand=live.build_candidates(one)
cmap={(str(r.time_ny),str(r.session),str(r.direction)):r for _,r in cand.iterrows()}
omap={str(r.time_ny):r for _,r in one.iterrows()}

rows=[]
for _,x in proof.iterrows():
    c=cmap.get((str(x.candidate_time),str(x.session),str(x.direction)))
    b=omap.get(str(x.entry_time))
    if c is None or b is None: continue
    # The candidate's prior session extreme is exactly extreme +/- sweep_distance.
    prior_extreme=(float(c.extreme)+float(c.sweep_distance)) if c.direction=="LONG" else (float(c.extreme)-float(c.sweep_distance))
    op=float(b.open); ca=float(c.atr)
    open_cross_candidate=(op<=float(c.extreme)) if c.direction=="LONG" else (op>=float(c.extreme))
    open_cross_prior=(op<=prior_extreme) if c.direction=="LONG" else (op>=prior_extreme)
    # Positive means entry open is on the reclaimed/safe side of candidate extreme.
    safe_dist=(op-float(c.extreme)) if c.direction=="LONG" else (float(c.extreme)-op)
    rows.append({
        "entry_time":x.entry_time,"candidate_time":x.candidate_time,"session":x.session,"direction":x.direction,
        "entry_open":op,"candidate_extreme":float(c.extreme),"prior_extreme":prior_extreme,
        "candidate_atr":ca,"open_cross_candidate":open_cross_candidate,"open_cross_prior_extreme":open_cross_prior,
        "safe_distance_points":safe_dist,
        "safe_distance_atr":safe_dist/ca if np.isfinite(ca) and ca>0 else np.nan,
    })

q=pd.DataFrame(rows)
print("="*100)
print("THE ICON — FAST CAUSAL ALTERNATIVES FOR 155 SUPERSESSION CASES")
print("="*100)
print("Cases available:",len(q))
print("\nCAUSAL AT ENTRY — ZERO DELAY")
print("Entry OPEN already crosses candidate extreme:",int(q.open_cross_candidate.sum()),"/",len(q))
print("Entry OPEN already crosses prior session extreme:",int(q.open_cross_prior_extreme.sum()),"/",len(q))
print("\nSafe-side distance from candidate extreme, in candidate ATR:")
print(q.safe_distance_atr.describe(percentiles=[.05,.10,.25,.50,.75,.90,.95]).to_string())

# Show how many of the 155 would be rejected by fixed zero-delay distance gates.
print("\nDIAGNOSTIC THRESHOLDS — REJECT IF ENTRY OPEN IS TOO CLOSE TO / THROUGH CANDIDATE EXTREME")
for th in [0,.025,.05,.075,.10,.15,.20,.25,.30,.40,.50]:
    n=int((q.safe_distance_atr<=th).sum())
    print(f"<= {th:>5.3f} ATR : rejects {n:3d}/{len(q)} ({100*n/len(q):5.1f}%)")

out=Path("data/reports/2026-09_155_causal_alternatives.csv")
q.to_csv(out,index=False)
print("\nSaved:",out)
print("IMPORTANT: these are candidate causal alternatives only. No live filter was changed.")
