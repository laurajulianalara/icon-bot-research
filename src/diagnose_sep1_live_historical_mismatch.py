#!/usr/bin/env python3
"""THE ICON — Sep 1 historical-vs-causal implementation diagnostic.

READ-ONLY diagnostic. Does not modify Option 2B.
Uses the already-saved September causal emissions and the frozen historical
current-month report/reference to explain why Sep 1 causal extras were not in
historical Option 2B.

This deliberately checks implementation/parity causes FIRST:
  1) historical V15 membership/reference handling
  2) full-day supersession
  3) canonical ticker/risk validity
  4) Option 2B final six-slot position

It does not invent or tune a new strategy filter.
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
V11=Path("data/v11_reversal_state_forensics.csv")
DATA=Path(live.HIST)

for p in [CAUSAL,HISTTR,V11,DATA]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et_series(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

ca=pd.read_csv(CAUSAL)
ca["entry_time"]=et_series(ca["entry_time_et"])
ca["candidate_time"]=et_series(ca["candidate_time_et"])
ca=ca[ca.entry_time.dt.date==DAY].copy().sort_values("entry_time")

ht=pd.read_csv(HISTTR)
ht["entry_time"]=et_series(ht["entry_time"])
ht=ht[ht.entry_time.dt.date==DAY].copy().sort_values("entry_time")
hkeys=set(zip(ht.entry_time.astype(str),ht.session.astype(str),ht.direction.astype(str)))

ref=pd.read_csv(V11)
ref["candidate_time"]=pd.to_datetime(ref.candidate_time,utc=True)
ref["candidate_time_et"]=ref.candidate_time.dt.tz_convert(live.TZ)
# Rebuild the exact historical V15 membership path used by current-month engine.
ref["reclaim_x_wick"]=ref.early_reclaim_atr*ref.wick_percent
ref["close_x_reclaim"]=ref.m2_close_pos*ref.early_reclaim_atr
ref["sweep_minus_reclaim"]=ref.sweep_atr-ref.early_reclaim_atr
ref["impulse_minus_reclaim"]=ref.reversal_impulse-ref.early_reclaim_atr
ref["quality_balance"]=ref.rejection_quality*ref.impulse_to_reclaim/(1+ref.reclaim_to_sweep)
parts=[]
for col,hi,w in [
 ("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),
 ("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),
 ("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]:
    rank=ref[col].rank(pct=True); comp=rank if hi else 1-rank; parts += [comp]*w
ref["score"]=pd.concat(parts,axis=1).mean(axis=1)
threshold=ref.score.quantile(.07)
eligible=ref[ref.score>=threshold].copy()
eligible["date_et"]=eligible.candidate_time_et.dt.date
eligible=eligible.sort_values("candidate_time_et")
eligible["v15_slot"]=eligible.groupby("date_et").cumcount()+1
eligible6=eligible[eligible.v15_slot<=6].copy()
v15_allowed=set(zip(eligible6.candidate_time_et.astype(str),eligible6.direction.astype(str)))

# Full-day completed data: reconstruct candidates exactly as live builder does,
# then inspect the historical full-day supersession information.
one=pd.read_parquet(DATA)[live.NEED].copy()
one["time_ny"]=et_series(one["time_ny"])
# enough context for ATR; full Sep 1 session data
start=pd.Timestamp("2026-08-29",tz=live.TZ); end=pd.Timestamp("2026-09-02",tz=live.TZ)
one=one[(one.time_ny>=start)&(one.time_ny<end)].sort_values("time_ny").reset_index(drop=True)
cand=live.build_candidates(one)
cm={(str(r.time_ny),str(r.direction)):r for _,r in cand.iterrows()}

rows=[]
for _,x in ca.iterrows():
    key=(str(x.entry_time),str(x.session),str(x.direction))
    original=key in hkeys
    ck=(str(x.candidate_time),str(x.direction))
    c=cm.get(ck)
    v15_hist=ck in v15_allowed
    next_ext=pd.NaT if c is None else c.next_same_extreme_time
    superseded=False
    if c is not None and pd.notna(next_ext):
        superseded=x.entry_time>=next_ext
    # Historical V15 source-row facts for visibility.
    rr=ref[(ref.candidate_time_et.astype(str)==str(x.candidate_time))&
           (ref.direction.astype(str)==str(x.direction))]
    ref_exists=len(rr)>0
    hist_score=float(rr.iloc[0].score) if ref_exists else np.nan
    hist_v15_slot=(int(eligible.loc[rr.index[0]].v15_slot)
                   if ref_exists and rr.index[0] in eligible.index else np.nan)

    if original:
        reason="ORIGINAL HISTORICAL TRADE"
    elif not ref_exists:
        reason="NOT IN HISTORICAL V11/V15 REFERENCE"
    elif not v15_hist:
        if np.isfinite(hist_v15_slot) and hist_v15_slot>6:
            reason="HISTORICAL V15 MEMBERSHIP/CAP REJECT"
        else:
            reason="HISTORICAL V15 REJECT"
    elif c is None:
        reason="NOT IN FULL-DAY CANDIDATE SET"
    elif superseded:
        reason="FULL-DAY SUPERSESSION REJECT"
    else:
        reason="PASSES THESE CHECKS — NEED DEEP V7/V8/V27/CANONICAL TRACE"

    rows.append({
      "entry_time":x.entry_time,"candidate_time":x.candidate_time,
      "session":x.session,"direction":x.direction,"entry":x.entry,"stop":x.stop,
      "original":original,"ref_exists":ref_exists,"hist_score":hist_score,
      "hist_v15_allowed":v15_hist,"hist_v15_slot":hist_v15_slot,
      "next_same_extreme_time":next_ext,"full_day_superseded":superseded,
      "reason":reason})

out=pd.DataFrame(rows)
extras=out[~out.original].copy()
print("="*110)
print("THE ICON — SEP 1 IMPLEMENTATION/PARITY DIAGNOSTIC")
print("="*110)
print(f"Historical trades: {len(ht)} | causal emitted: {len(ca)} | originals matched: {int(out.original.sum())} | extras: {len(extras)}")
print("\nEXTRA REJECTION REASONS")
print(extras.reason.value_counts().to_string())
print("\nALL SEP 1 CAUSAL SIGNALS")
cols=["entry_time","candidate_time","session","direction","original","hist_v15_allowed","hist_v15_slot","full_day_superseded","reason"]
print(out[cols].to_string(index=False))
print("\nINTERPRETATION")
print("- ORIGINAL HISTORICAL TRADE = live replay correctly reproduced it.")
print("- HISTORICAL V15... = live forward scoring admitted something the historical membership path did not.")
print("- FULL-DAY SUPERSESSION = live could emit it before a later-completing 3m extreme made historical reject it.")
print("- PASSES THESE CHECKS = this script intentionally does NOT guess; trace V7/V8/V27/canonical next.")
print("\nREAD ONLY: no strategy files or thresholds were changed.")
