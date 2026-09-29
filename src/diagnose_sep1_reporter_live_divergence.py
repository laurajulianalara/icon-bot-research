#!/usr/bin/env python3
"""THE ICON — Sep 1 reporter-vs-live decision diagnostic.

READ-ONLY diagnostic. It does not modify strategy logic, thresholds, market
data, reports, or execution. It traces the same Sep 1 candidates through the
frozen reporter decision path and the causal/live decision path so the first
implementation divergence is obvious.
"""
from pathlib import Path
import bisect, json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ
DAY=pd.Timestamp("2026-09-01",tz=TZ)
END=DAY+pd.Timedelta(days=1)
NEED=live.NEED
V11=Path("data/v11_reversal_state_forensics.csv")
REPORT=Path("data/reports/2026-09_trades.csv")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

# Same cached source assembly used by the parity audit.
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
one=one[(one.time_ny>=DAY-pd.Timedelta(days=3))&(one.time_ny<END)].copy().reset_index(drop=True)

# Build the reporter's frozen V15 historical membership exactly.
if not V11.exists(): raise SystemExit("Missing "+str(V11))
ref=pd.read_csv(V11)
ref["candidate_time"]=pd.to_datetime(ref["candidate_time"],utc=True)
ref["candidate_time_et"]=ref["candidate_time"].dt.tz_convert(TZ)
ref["reclaim_x_wick"]=ref.early_reclaim_atr*ref.wick_percent
ref["close_x_reclaim"]=ref.m2_close_pos*ref.early_reclaim_atr
ref["sweep_minus_reclaim"]=ref.sweep_atr-ref.early_reclaim_atr
ref["impulse_minus_reclaim"]=ref.reversal_impulse-ref.early_reclaim_atr
ref["quality_balance"]=ref.rejection_quality*ref.impulse_to_reclaim/(1+ref.reclaim_to_sweep)
parts=[]
for col,hi,w in live.SPEC:
    r=ref[col].rank(pct=True); comp=r if hi else 1-r; parts += [comp]*w
ref["score"]=pd.concat(parts,axis=1).mean(axis=1)
threshold=ref.score.quantile(.07)
hist_ref=ref[ref.score>=threshold].copy()
hist_ref["date_et"]=hist_ref.candidate_time_et.dt.date
hist_ref=hist_ref.sort_values("candidate_time_et").reset_index(drop=True)
hist_ref["trade_num_day"]=hist_ref.groupby("date_et").cumcount()+1
hist_ref=hist_ref[hist_ref.trade_num_day<=6]
allowed=set(zip(hist_ref.candidate_time_et.astype(str),hist_ref.direction.astype(str)))
max_ref_date=ref.candidate_time_et.dt.date.max()

# Full-data candidate list is the reporter view.
pc=one.close.shift(1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
cand=live.build_candidates(one)
cand=cand[(cand.time_ny>=DAY)&(cand.time_ny<END)].copy()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

rows=[]
for _,c in cand.iterrows():
    i=idx.get(c.time_ny)
    base={"candidate":c.time_ny,"session":c.session,"dir":c.direction}
    if i is None or i<20 or i+3>=len(one):
        rows.append({**base,"reporter":"NO_CONTEXT"}); continue
    a=float(one.iloc[i].atr1); sg=1 if c.direction=="LONG" else -1; vals={}
    if not np.isfinite(a) or a<=0:
        rows.append({**base,"reporter":"ATR_FAIL"}); continue
    for k in [1,2]:
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
    if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912):
        rows.append({**base,"reporter":"V7_FAIL"}); continue
    first2=one.iloc[i+1:i+3]
    reclaim=((float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG"
             else (float(c.extreme)-float(first2.iloc[-1].close))/a)
    if not(reclaim<=.90 and vals["m2_close_pos"]<=.80 and float(c.wick_percent)<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4):
        rows.append({**base,"reporter":"V8_FAIL"}); continue
    key=(str(c.time_ny),str(c.direction))
    historical=c.time_ny.date()<=max_ref_date
    if historical and key not in allowed:
        rows.append({**base,"reporter":"V15_MEMBERSHIP_FAIL"}); continue
    if not historical:
        rows.append({**base,"reporter":"FORWARD_NOT_EXPECTED"}); continue
    rw=reclaim*float(c.wick_percent)
    if reclaim>=live.RTH and rw>=live.WTH:
        rows.append({**base,"reporter":"V27_FAIL"}); continue
    signal=one.iloc[i+3].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time:
        rows.append({**base,"reporter":"SUPERSEDED"}); continue
    if one.iloc[i+3].ticker!=c.ticker:
        rows.append({**base,"reporter":"TICKER_FAIL"}); continue
    rows.append({**base,"reporter":"FINAL_PRECAP","entry_time":signal,
                 "entry":float(one.iloc[i+3].open),
                 "stop":float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25})

trace=pd.DataFrame(rows)

# What causal/live would actually emit on Sep 1, boundary by boundary.
sep=one[(one.time_ny>=DAY)&(one.time_ny<END)]
bounds=[t for t in sep.time_ny if t.minute%3==0 and live.session_name(t) is not None]
live_rows=[]; count=0
for t in bounds:
    pos=one.index[one.time_ny==t]
    if not len(pos): continue
    p=int(pos[-1]); closed=one.loc[:p-1,NEED].tail(6500).copy(); op=one.loc[p,NEED].to_dict()
    for x in live.evaluate(closed,live_open=op):
        if pd.Timestamp(x["entry_time_et"])!=t: continue
        if count>=6: continue
        count+=1; live_rows.append(x)

lv=pd.DataFrame(live_rows)
live_keys=set()
if not lv.empty:
    live_keys=set(zip(pd.to_datetime(lv.candidate_time_et).astype(str),lv.direction.astype(str)))

trace["live_emitted"]=[(str(r.candidate),str(r.dir)) in live_keys for _,r in trace.iterrows()]

# Frozen report finals for Sep 1.
bench=set()
if REPORT.exists():
    b=pd.read_csv(REPORT); b["candidate_time"]=et(b.candidate_time)
    b=b[(b.candidate_time>=DAY)&(b.candidate_time<END)]
    bench=set(zip(b.candidate_time.astype(str),b.direction.astype(str)))
trace["benchmark_final"]=[(str(r.candidate),str(r.dir)) in bench for _,r in trace.iterrows()]

interesting=trace[(trace.live_emitted)|(trace.benchmark_final)|(trace.reporter=="FINAL_PRECAP")].copy()
print("="*112)
print("THE ICON — SEP 1 REPORTER vs CAUSAL/LIVE DIAGNOSTIC")
print("="*112)
print("READ-ONLY. No strategy/filter/threshold/data/execution changes.")
print("Reporter frozen V15 allowed set:",len(allowed),"| historical reference through:",max_ref_date)
print("\nKEY: benchmark_final = in frozen 73-trade report; live_emitted = causal engine actually emitted")
print("\n"+interesting[["candidate","session","dir","reporter","benchmark_final","live_emitted"]].to_string(index=False))

print("\n"+"="*112)
print("FIRST DIVERGENCES")
print("="*112)
d=interesting[interesting.benchmark_final!=interesting.live_emitted]
if d.empty:
    print("None on Sep 1.")
else:
    print(d[["candidate","session","dir","reporter","benchmark_final","live_emitted"]].to_string(index=False))

print("\nLIVE SEP 1 EMISSIONS")
if lv.empty: print("None")
else: print(lv[["candidate_time_et","entry_time_et","session","direction","entry","stop","v15_score"]].to_string(index=False))
print("\nDiagnostic complete. No files changed.")
