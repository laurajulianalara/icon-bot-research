#!/usr/bin/env python3
"""Audit why 6 exact Option2B-selected trades are absent from 2026-09_trades.csv.
READ ONLY. Focuses on the month-report historical V15 membership path.
"""
from pathlib import Path
import bisect, json
import numpy as np
import pandas as pd
TZ="America/New_York"; TH=.145921011058
T=Path("data/reports/2026-09_six_exact_canonical_trace.csv")
V=Path("data/v11_reversal_state_forensics.csv")
H=Path("data/reports/2026-09_trades.csv")
for p in [T,V,H,Path("data/icon_v15_pine_reference.json")]:
 if not p.exists(): raise RuntimeError(f"Missing {p}")
def et(s):
 x=pd.to_datetime(s); return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
def k(t,d): return (str(pd.Timestamp(t).tz_convert(TZ)),str(d))
t=pd.read_csv(T); t["candidate_time"]=et(t.candidate_time); t["entry_time"]=et(t.entry_time_from_causal)
ref=pd.read_csv(V); ref["candidate_time"]=pd.to_datetime(ref.candidate_time,utc=True); ref["candidate_time_et"]=ref.candidate_time.dt.tz_convert(TZ)
# Reproduce EXACT month-report scoring/membership construction.
ref["reclaim_x_wick"]=ref.early_reclaim_atr*ref.wick_percent
ref["close_x_reclaim"]=ref.m2_close_pos*ref.early_reclaim_atr
ref["sweep_minus_reclaim"]=ref.sweep_atr-ref.early_reclaim_atr
ref["impulse_minus_reclaim"]=ref.reversal_impulse-ref.early_reclaim_atr
ref["quality_balance"]=ref.rejection_quality*ref.impulse_to_reclaim/(1+ref.reclaim_to_sweep)
parts=[]
for col,hi,w in [("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]:
 r=ref[col].rank(pct=True); parts += [(r if hi else 1-r)]*w
ref["month_score"]=pd.concat(parts,axis=1).mean(axis=1)
month_threshold=float(ref.month_score.quantile(.07))
hist_ref=ref[ref.month_score>=month_threshold].copy(); hist_ref["date_et"]=hist_ref.candidate_time_et.dt.date
hist_ref=hist_ref.sort_values("candidate_time_et").reset_index(drop=True); hist_ref["trade_num_day"]=hist_ref.groupby("date_et").cumcount()+1
hist_allowed=hist_ref[hist_ref.trade_num_day<=6].copy()
allowed=set(zip(hist_allowed.candidate_time_et.astype(str),hist_allowed.direction.astype(str)))
h=pd.read_csv(H); h["entry_time"]=et(h.entry_time)
rows=[]
for _,x in t.iterrows():
 rr=ref[(ref.candidate_time_et.astype(str)==str(x.candidate_time))&(ref.direction.astype(str)==str(x.direction))]
 if len(rr)!=1: raise RuntimeError(f"Expected one V11 row for {x.candidate_time} {x.direction}, got {len(rr)}")
 r=rr.iloc[0]; key=(str(x.candidate_time),str(x.direction))
 dayall=hist_ref[hist_ref.date_et==x.candidate_time.date()].sort_values("candidate_time_et")
 before=int((dayall.candidate_time_et<=x.candidate_time).sum())
 in_report=((h.entry_time==x.entry_time)&(h.direction.astype(str)==str(x.direction))).any()
 rows.append({"entry_time":x.entry_time,"candidate_time":x.candidate_time,"session":x.session,"direction":x.direction,
 "month_report_score":float(r.month_score),"month_threshold":month_threshold,"passes_month_score":bool(r.month_score>=month_threshold),
 "v15_survivor_ordinal_that_day":before if r.month_score>=month_threshold else np.nan,
 "in_month_v15_allowed_first6":key in allowed,"in_2026_09_trades":bool(in_report)})
o=pd.DataFrame(rows)
print("="*120);print("THE ICON — WHY THE 6 ARE MISSING FROM SEPTEMBER REPORT");print("="*120)
print("Month-report V15 threshold:",month_threshold)
print(o.to_string(index=False))
print("\nSUMMARY")
print(o[["passes_month_score","in_month_v15_allowed_first6","in_2026_09_trades"]].value_counts().to_string())
print("\nNOTE: icon_month_option2b_test.py builds v15_allowed by taking the FIRST SIX V15 survivors/day BEFORE V27/canonical validity. That is Option 2A-style cap placement, despite the later final-trade Option2B cap.")
save=Path("data/reports/2026-09_six_missing_report_audit.csv");o.to_csv(save,index=False)
print("Saved:",save);print("READ ONLY — no strategy/data files changed.")
