#!/usr/bin/env python3
"""Full Sep 1-24 causal delayed-supersession audit using temporary rebuilt inputs. READ ONLY."""
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];TZ="America/New_York";D=ROOT/"data"
ONE=D/"audit_sep01_24_1m.parquet";CAND=D/"audit_sep01_24_candidates.parquet";REPORT=D/"reports/2026-09_trades.csv";DELAYS=[0,1,2,3]
def norm(s):
 x=pd.to_datetime(s,errors="coerce");return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)
one=pd.read_parquet(ONE);one["time_ny"]=norm(one.time_ny);one=one.sort_values("time_ny").reset_index(drop=True)
pc=one.close.shift();one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean();idx=pd.Series(one.index,index=one.time_ny).to_dict()
raw=pd.read_parquet(CAND);raw["time_ny"]=norm(raw.time_ny);raw=raw.sort_values("time_ny").reset_index(drop=True);raw["next_same_extreme_time"]=raw.groupby(["date","session","direction"],sort=False).time_ny.shift(-1)
rep=pd.read_csv(REPORT);rep["_ct"]=norm(rep.candidate_time);rep["_dir"]=rep.direction.astype(str).str.upper();bench=set(zip(rep._ct,rep._dir))
rows=[]
for _,c in raw.iterrows():
 t=c.time_ny;d=str(c.direction).upper();i=idx.get(t)
 if i is None or i<20 or i+3>=len(one):continue
 a=float(one.iloc[i].atr1)
 if not np.isfinite(a) or a<=0:continue
 sg=1 if d=="LONG" else -1;v={}
 for k in [1,2]:
  b=one.iloc[i+k];v[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg;cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5;v[f"m{k}_close_pos"]=float(cp if d=="LONG" else 1-cp)
 if not(v["m1_move_atr"]<=.300 and v["m1_close_pos"]>=.140 and v["m2_close_pos"]<=.912):continue
 j=i+3;nt=one.iloc[j].time_ny;no=float(one.iloc[j].open);stop=float(c.extreme)-.25 if d=="LONG" else float(c.extreme)+.25;risk=no-stop if d=="LONG" else stop-no
 if str(one.iloc[j].ticker)!=str(c.ticker) or risk<=0:continue
 nx=c.next_same_extreme_time;r={"candidate":t,"direction":d,"benchmark":(t,d) in bench,"normal_time":nt,"normal_open":no,"next_extreme":nx}
 for delay in DELAYS:
  fi=j+delay
  if fi>=len(one):r[f"keep_{delay}"]=False;r[f"drift_{delay}"]=np.nan;continue
  ft=one.iloc[fi].time_ny;r[f"keep_{delay}"]=not(pd.notna(nx) and nx<ft);r[f"drift_{delay}"]=float(one.iloc[fi].open)-no
 rows.append(r)
x=pd.DataFrame(rows);x["hist_sup_reject"]=x.next_extreme.notna()&(x.next_extreme<=x.normal_time);sup=x[x.hist_sup_reject]
represented=set(zip(x.loc[x.benchmark,"candidate"],x.loc[x.benchmark,"direction"]));missing=bench-represented
print("="*108);print("FULL SEP 1-24 — CAUSAL DELAYED SUPERSESSION AUDIT");print("="*108)
print("Frozen benchmark:",len(bench));print("Benchmark represented:",len(represented));print("Benchmark not represented:",len(missing));print("V7-eligible candidates:",len(x));print("Historical supersession rejects:",len(sup))
if missing:
 print("\nUNREPRESENTED BENCHMARK KEYS");[print(t,d) for t,d in sorted(missing)]
for delay in DELAYS:
 bx=x[x.benchmark];kept=int(bx[f"keep_{delay}"].sum());rej=int((~sup[f"keep_{delay}"]).sum());dr=bx.loc[bx[f"keep_{delay}"],f"drift_{delay}"].abs().dropna()
 print(f"\nWAIT {delay} MINUTE(S):");print(f"  Benchmark preserved: {kept}/{len(bx)}");print(f"  Historical-supersession candidates rejected: {rej}/{len(sup)}");print(f"  Benchmark abs entry-open drift: median={dr.median() if len(dr) else np.nan:.2f} pts | max={dr.max() if len(dr) else np.nan:.2f} pts")
print("\nREAD-ONLY. Frozen/source data and production code unchanged.")
