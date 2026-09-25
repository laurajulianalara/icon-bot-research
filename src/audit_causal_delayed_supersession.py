#!/usr/bin/env python3
"""Test causal delayed-finalization replacements for historical supersession. READ ONLY.

For each frozen September benchmark trade and raw candidate that passes the frozen V7
numeric rule, ask what happens if live waits N completed 1m bars after the normal T+3
entry boundary before finalizing supersession. Reports benchmark preservation,
premature-candidate rejection, delay, and price drift. This is a diagnostic only.
"""
from pathlib import Path
import sys, numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]
TZ="America/New_York"
ONE=ROOT/"data/mnq_continuous_1m.parquet"
CAND=ROOT/"data/reversal_candidates.parquet"
# The permanent reporter writes its frozen current-month trade list here.
REPORT=ROOT/"data/reports/2026-09_trades.csv"
DELAYS=[0,1,2,3]

def norm(s):
 x=pd.to_datetime(s,errors="coerce")
 return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

one=pd.read_parquet(ONE).copy(); one["time_ny"]=norm(one.time_ny)
one=one.sort_values("time_ny").drop_duplicates("time_ny").reset_index(drop=True)
prev=one.close.shift()
one["atr1"]=pd.concat([one.high-one.low,(one.high-prev).abs(),(one.low-prev).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

raw=pd.read_parquet(CAND).copy(); raw["time_ny"]=norm(raw.time_ny)
raw=raw[(raw.time_ny>=pd.Timestamp("2026-09-01",tz=TZ))&(raw.time_ny<pd.Timestamp("2026-10-01",tz=TZ))].copy()
raw=raw.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
raw["next_same_extreme_time"]=raw.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)

# Frozen benchmark from the permanent reporter's September trade export.
if not REPORT.exists():
 raise SystemExit(f"Missing frozen September trade export: {REPORT}\nRun: python src/icon_month_live_report.py")
rep=pd.read_csv(REPORT)
tc=next((c for c in ["candidate_time","candidate_time_et","time_ny","candidate_time_ny"] if c in rep.columns),None)
dc=next((c for c in ["direction","side"] if c in rep.columns),None)
if tc is None or dc is None: raise SystemExit("Cannot identify benchmark candidate-time/direction columns in 2026-09_trades.csv")
rep["_ct"]=norm(rep[tc]); rep["_dir"]=rep[dc].astype(str).str.upper()
rep=rep[(rep._ct>=pd.Timestamp("2026-09-01",tz=TZ))&(rep._ct<pd.Timestamp("2026-10-01",tz=TZ))]
bench=set(zip(rep._ct,rep._dir))
print("="*112);print("THE ICON — CAUSAL DELAYED FINALIZATION / SUPERSESSION TEST");print("="*112)
print("Frozen September benchmark keys:",len(bench))

rows=[]
for _,c in raw.iterrows():
 t=c.time_ny; d=str(c.direction).upper(); i=idx.get(t)
 if i is None or i<20 or i+3>=len(one): continue
 a=float(one.iloc[i].atr1)
 if not np.isfinite(a) or a<=0: continue
 sg=1 if d=="LONG" else -1
 vals={}
 for k in [1,2]:
  b=one.iloc[i+k]
  vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
  cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
  vals[f"m{k}_close_pos"]=float(cp if d=="LONG" else 1-cp)
 if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912): continue
 j=i+3; normal_time=one.iloc[j].time_ny; normal_open=float(one.iloc[j].open)
 stop=float(c.extreme)-.25 if d=="LONG" else float(c.extreme)+.25
 risk=normal_open-stop if d=="LONG" else stop-normal_open
 if str(one.iloc[j].ticker)!=str(c.ticker) or risk<=0: continue
 nx=c.next_same_extreme_time
 r={"candidate":t,"direction":d,"session":c.session,"benchmark":(t,d) in bench,
    "normal_time":normal_time,"normal_open":normal_open,"next_extreme":nx}
 for delay in DELAYS:
  # At T+3+delay, candles strictly before that timestamp are completed/knowable.
  # Therefore a next extreme stamped before finalization is causally known.
  fi=j+delay
  if fi>=len(one): r[f"keep_{delay}"]=False; r[f"drift_{delay}"]=np.nan; continue
  final_time=one.iloc[fi].time_ny
  superseded_known=pd.notna(nx) and nx < final_time
  r[f"keep_{delay}"]=not superseded_known
  r[f"drift_{delay}"]=float(one.iloc[fi].open)-normal_open
 rows.append(r)
d=pd.DataFrame(rows)

d["historical_supersession_reject"]=d.next_extreme.notna()&(d.next_extreme<=d.normal_time)
sup=d[d.historical_supersession_reject].copy()
print("V7-eligible September candidates inspected:",len(d))
print("Candidates historical supersession rejects at/by normal entry:",len(sup))
print("\nRESULTS")
for delay in DELAYS:
 kept_b=sum(bool(r[f"keep_{delay}"]) for _,r in d[d.benchmark].iterrows())
 total_b=len(d[d.benchmark])
 rejected_sup=sum(not bool(r[f"keep_{delay}"]) for _,r in sup.iterrows())
 total_sup=len(sup)
 dr=d.loc[d.benchmark & d[f"keep_{delay}"],f"drift_{delay}"].dropna().abs()
 print(f"\nWAIT {delay} MINUTE(S) AFTER NORMAL T+3:")
 print(f"  Benchmark preserved: {kept_b}/{total_b}")
 print(f"  Historical-supersession candidates rejected causally: {rejected_sup}/{total_sup}")
 print(f"  Benchmark abs entry-open drift: median={dr.median() if len(dr) else np.nan:.2f} pts | max={dr.max() if len(dr) else np.nan:.2f} pts")
known={(pd.Timestamp("2026-09-01 02:27",tz=TZ),"LONG"),(pd.Timestamp("2026-09-01 03:36",tz=TZ),"LONG"),
(pd.Timestamp("2026-09-01 03:57",tz=TZ),"LONG"),(pd.Timestamp("2026-09-02 02:39",tz=TZ),"SHORT"),
(pd.Timestamp("2026-09-02 09:39",tz=TZ),"SHORT")}
z=d[d.apply(lambda r:(r.candidate,r.direction) in known,axis=1)]
print("\nKNOWN 5 CONFIRMED EXTRAS")
cols=["candidate","direction","next_extreme"]+[f"keep_{x}" for x in DELAYS]
print(z[cols].to_string(index=False))
print("\nIMPORTANT: keep_0 models the current instant-open decision; WAIT 1 means finalize at the next minute boundary,")
print("after the original entry minute has completed. No future candle data is used by the delayed decision.")
print("READ-ONLY. No production code, thresholds, data, or frozen benchmark changed.")
