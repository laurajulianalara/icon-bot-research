#!/usr/bin/env python3
"""THE ICON — Sep 1 exact original simulate() proof.

READ ONLY. No strategy changes.
Runs each Sep 1 causal-only signal through the ORIGINAL V7 simulate() rejection
conditions, with full-day candidate supersession information, and reports the
first rejection reason.

Goal: test whether all 17 extras were absent from the historical V7 base
specifically because original simulate() rejected them as superseded.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY=pd.Timestamp("2026-09-01").date()
CAUSAL=Path("data/reports/2026-09_true_bar_by_bar.csv")
HISTTR=Path("data/reports/2026-09_trades.csv")

for p in [CAUSAL,HISTTR,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

ca=pd.read_csv(CAUSAL)
ca["entry_time"]=et(ca.entry_time_et)
ca["candidate_time"]=et(ca.candidate_time_et)
ca=ca[ca.entry_time.dt.date==DAY].copy().sort_values("entry_time")

ht=pd.read_csv(HISTTR)
ht["entry_time"]=et(ht.entry_time)
ht=ht[ht.entry_time.dt.date==DAY].copy()
hkeys=set(zip(ht.entry_time.astype(str),ht.session.astype(str),ht.direction.astype(str)))
ca["original"]=ca.apply(lambda x:(str(x.entry_time),str(x.session),str(x.direction)) in hkeys,axis=1)
extras=ca[~ca.original].copy()

# Full data around Sep 1, preserving ATR context.
one=pd.read_parquet(live.HIST)[live.NEED].copy()
one["time_ny"]=et(one.time_ny)
start=pd.Timestamp("2026-08-29",tz=live.TZ)
end=pd.Timestamp("2026-09-02",tz=live.TZ)
one=one[(one.time_ny>=start)&(one.time_ny<end)].sort_values("time_ny").reset_index(drop=True)
idx=pd.Series(one.index,index=one.time_ny).to_dict()

# This builder reproduces the candidate ordering + next_same_extreme_time needed
# by original V7 simulate().
cand=live.build_candidates(one)
cmap={(str(r.time_ny),str(r.session),str(r.direction)):r for _,r in cand.iterrows()}

rows=[]
for _,x in extras.iterrows():
    ck=(str(x.candidate_time),str(x.session),str(x.direction))
    c=cmap.get(ck)
    reason="UNKNOWN"
    signal=pd.NaT
    next_ext=pd.NaT
    if c is None:
        reason="NO_FULL_DAY_CANDIDATE"
    else:
        i=idx.get(c.time_ny)
        if i is None:
            reason="NO_1M_INDEX"
        elif i+3>=len(one):
            reason="NO_SIGNAL_BAR"
        else:
            j=i+3
            signal=one.iloc[j].time_ny
            next_ext=c.next_same_extreme_time
            # EXACT ORDER from original V7 simulate():
            if one.iloc[j].ticker != c.ticker:
                reason="TICKER_MISMATCH"
            elif pd.notna(next_ext) and signal>=next_ext:
                reason="SUPERSEDED"
            else:
                entry=float(one.iloc[j].open)
                stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
                risk=entry-stop if c.direction=="LONG" else stop-entry
                if risk<=0:
                    reason="INVALID_RISK"
                else:
                    # Original simulate() then searched up to 241 bars for 4R/SL.
                    target=entry+4*risk if c.direction=="LONG" else entry-4*risk
                    outcome=None
                    for z in range(j,min(j+241,len(one))):
                        b=one.iloc[z]
                        if b.ticker!=c.ticker: break
                        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
                        th=b.high>=target if c.direction=="LONG" else b.low<=target
                        if sh: outcome="LOSS"; break
                        if th: outcome="WIN"; break
                    reason="SIMULATE_ACCEPT_"+str(outcome) if outcome else "NO_4R_OR_SL_WITHIN_WINDOW"
    rows.append({"entry_time":x.entry_time,"candidate_time":x.candidate_time,
                 "session":x.session,"direction":x.direction,
                 "signal_time_from_original":signal,
                 "next_same_extreme_time":next_ext,"original_simulate_result":reason})

out=pd.DataFrame(rows)
print("="*112)
print("THE ICON — SEP 1 ORIGINAL simulate() PROOF")
print("="*112)
print(f"Sep 1 causal-only extras tested: {len(out)}")
print("\nORIGINAL simulate() RESULT")
print(out.original_simulate_result.value_counts().to_string())
print("\nDETAIL")
print(out.to_string(index=False))
n=int((out.original_simulate_result=="SUPERSEDED").sum())
print("\n"+"="*112)
print(f"SUPERSESSION PROOF: {n}/{len(out)} extras rejected by original simulate() specifically because signal >= next_same_extreme_time.")
if len(out)==17 and n==17:
    print("PASS — 17/17 SEP 1 EXTRAS ARE REJECTED BY THE ORIGINAL V7 simulate() SUPERSESSION CHECK.")
else:
    print("NOT 17/17 — inspect the non-SUPERSEDED reasons above before changing live code.")
print("READ ONLY — no Option 2B code, thresholds, or data files changed.")
