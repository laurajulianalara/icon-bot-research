import pandas as pd
import numpy as np
from itertools import product

IN="data/v8_volatility_forensics.csv"; OUT="data/v9_bad_setup_filter_search.csv"
q=pd.read_csv(IN);q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True)
q=q.sort_values("candidate_time").reset_index(drop=True);q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70

def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max())
 cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 return len(z),len(z)/365,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx

# Reject only when MULTIPLE bad characteristics occur together.
# Thresholds span the winner/loss distribution overlap found in V9.
rows=[]
for rec,wick,m2,sweep,need in product([.45,.50,.55,.60],[.25,.30,.35,.40],[-.75,-.60,-.45,-.30],[.25,.30,.35,.40],[2,3,4]):
 bad=pd.DataFrame({
  "reclaim":q.early_reclaim_atr>=rec,
  "wick":q.wick_percent>=wick,
  "m2":q.m2_move_atr>=m2,
  "sweep":q.sweep_atr<=sweep,
 }).sum(axis=1)
 z=q[bad<need].copy()
 m=met(z)
 if 3.5<=m[1]<=4.2 and len(z)>=1200:
  a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
  rows.append([rec,wick,m2,sweep,need,*m,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())])

r=pd.DataFrame(rows,columns=["reclaim_bad","wick_bad","m2_move_bad","sweep_bad","bad_signals_needed","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r=r.sort_values(["max_dd_r","max_loss_streak","robust_wr","trades"],ascending=[True,True,False,False])
r.to_csv(OUT,index=False)
print("=== BAD-SETUP COMBINATION FILTER SEARCH ===")
print("Baseline: 1477 | 4.05/day | 57.55% | DD 8R | streak 8")
print("Candidates:",len(r))
print(r.head(50).round(2).to_string(index=False))
print("\n>=55% train/test + <=5R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=5)).sum()))
print(">=55% train/test + <=4R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=4)).sum()))
print("\nSaved:",OUT)
