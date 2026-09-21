import pandas as pd, numpy as np
from itertools import product
q=pd.read_csv("data/v11_reversal_state_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win: cur=0 if w else cur+1;mx=max(mx,cur)
 return len(z),len(z)/365,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx
rows=[]
# Use the strongest newly discovered causal quality measures. Require combinations,
# rather than blindly demanding one hard threshold.
for rq,ir,rs,need in product([.25,.30,.35,.40,.45,.50],[.5,.8,1.0,1.2,1.5,2.0],[.8,1.2,1.6,2.0,2.5,3.0],[1,2,3]):
 bad=(q.rejection_quality<rq).astype(int)+(q.impulse_to_reclaim<ir).astype(int)+(q.reclaim_to_sweep>rs).astype(int)
 z=q[bad<need].copy();m=met(z)
 if 3.4<=m[1]<=4.1 and len(z)>=1200:
  a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
  rows.append([rq,ir,rs,need,*m,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())])
r=pd.DataFrame(rows,columns=["rejection_min","impulse_reclaim_min","reclaim_sweep_max","bad_signals_needed","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r=r.sort_values(["max_dd_r","max_loss_streak","robust_wr","trades"],ascending=[True,True,False,False])
r.to_csv("data/v11_reversal_quality_filter_search.csv",index=False)
print("=== REVERSAL QUALITY FILTER SEARCH ===")
print("Baseline: 1477 | 4.05/day | 57.55% | DD 8R | streak 8")
print("Candidates:",len(r));print(r.head(50).round(2).to_string(index=False))
print("\n55%+ both + <=5R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=5)).sum()))
print("55%+ both + <=4R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=4)).sum()))
print("\nSaved: data/v11_reversal_quality_filter_search.csv")
