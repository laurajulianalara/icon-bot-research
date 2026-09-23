import pandas as pd, numpy as np
from itertools import product

print("=== 1M ATR / RECLAIM / WICK PARAMETER STUDY ===")
P="data/blind_plus2_filter_gap_audit.parquet"
d=pd.read_parquet(P).copy()
# Require the causal fields rebuilt in the full blind population.
need=["reclaim_atr","wick_percent","atr20"]
missing=[c for c in need if c not in d.columns]
if missing: raise RuntimeError(f"Missing causal features: {missing}")
# Find RR outcome columns already present; do not invent/recompute if available.
rrcols={}
for rr in range(1,7):
 for c in [f"rr{rr}_win",f"win_{rr}r",f"outcome_{rr}r",f"rr_{rr}_win",f"hit_{rr}r"]:
  if c in d.columns: rrcols[rr]=c;break
if len(rrcols)<6:
 print("Available columns:",", ".join(d.columns))
 raise RuntimeError("RR 1R-6R labels are not in this audit table. Need to merge existing causal RR labels before parameter search.")

for rr,c in rrcols.items():
 if d[c].dtype=="object": d[c]=d[c].astype(str).str.upper().map({"WIN":1,"LOSS":0,"TRUE":1,"FALSE":0})
 d[c]=pd.to_numeric(d[c],errors="coerce")

d["reclaim_x_wick"]=d["reclaim_atr"]*d["wick_percent"]
# Chronological 70/30: choose thresholds on earlier data, verify only on later untouched data.
timecol=next((c for c in ["candidate_time","time_ny","t"] if c in d.columns),None)
if timecol:
 d[timecol]=pd.to_datetime(d[timecol],utc=True);d=d.sort_values(timecol).reset_index(drop=True)
cut=int(len(d)*.70); train=d.iloc[:cut].copy(); test=d.iloc[cut:].copy()
print("Rows:",len(d),"| search:",len(train),"| untouched:",len(test))

# Quantile grids make thresholds data-aware without hindsight from test.
rq=np.unique(train.reclaim_atr.quantile(np.arange(.10,.91,.05)).round(6))
wq=np.unique(train.wick_percent.quantile(np.arange(.10,.91,.05)).round(6))
xq=np.unique(train.reclaim_x_wick.quantile(np.arange(.10,.91,.05)).round(6))
# Search simple live-usable rules. Require useful sample size.
rules=[]
def score(mask,df,name):
 n=int(mask.sum())
 if n<300:return
 z=df.loc[mask]
 vals={rr:100*z[c].mean() for rr,c in rrcols.items()}
 rules.append((vals[4],vals[6],n,name,vals))
for r in rq:
 score(train.reclaim_atr<=r,train,f"reclaim<={r}")
for w in wq:
 score(train.wick_percent<=w,train,f"wick<={w}")
for x in xq:
 score(train.reclaim_x_wick<=x,train,f"reclaim_x_wick<={x}")
for r,w in product(rq[::2],wq[::2]):
 score((train.reclaim_atr<=r)&(train.wick_percent<=w),train,f"reclaim<={r} AND wick<={w}")
for r,x in product(rq[::2],xq[::2]):
 score((train.reclaim_atr<=r)&(train.reclaim_x_wick<=x),train,f"reclaim<={r} AND rxw<={x}")
rules=sorted(rules,key=lambda x:(x[0],x[1],np.log1p(x[2])),reverse=True)
print("\nTOP SEARCH RULES BY 4R (min 300 trades)")
for a in rules[:15]:
 print(f"{a[3]:55s} n={a[2]:5d} | 1R={a[4][1]:5.2f} 2R={a[4][2]:5.2f} 3R={a[4][3]:5.2f} 4R={a[4][4]:5.2f} 5R={a[4][5]:5.2f} 6R={a[4][6]:5.2f}")

print("\nUNTOUCHED 30% — TOP 10 RULES")
for a in rules[:10]:
 name=a[3]
 # evaluate exact textual rule safely by carrying thresholds from parser
 if " AND wick<=" in name:
  p=name.replace("reclaim<=","").split(" AND wick<=");mask=(test.reclaim_atr<=float(p[0]))&(test.wick_percent<=float(p[1]))
 elif " AND rxw<=" in name:
  p=name.replace("reclaim<=","").split(" AND rxw<=");mask=(test.reclaim_atr<=float(p[0]))&(test.reclaim_x_wick<=float(p[1]))
 elif name.startswith("reclaim_x_wick<="):mask=test.reclaim_x_wick<=float(name.split("<=")[1])
 elif name.startswith("reclaim<="):mask=test.reclaim_atr<=float(name.split("<=")[1])
 else:mask=test.wick_percent<=float(name.split("<=")[1])
 z=test.loc[mask]; vals={rr:100*z[c].mean() for rr,c in rrcols.items()}
 print(f"{name:55s} n={len(z):5d} | 1R={vals[1]:5.2f} 2R={vals[2]:5.2f} 3R={vals[3]:5.2f} 4R={vals[4]:5.2f} 5R={vals[5]:5.2f} 6R={vals[6]:5.2f}")
