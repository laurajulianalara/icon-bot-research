import pandas as pd, numpy as np
from itertools import product
q=pd.read_csv("data/v12_surviving_loss_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 return len(z),len(z)/365,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx
rows=[]
# Test the strongest interaction features discovered in V12.
for rxw,cxr,smr,imr,qb,need in product(
 [.10,.13,.16,.20],[.16,.20,.24,.28],[ -.20,-.10,0,.10],[0,.10,.20,.30],[.10,.20,.30,.40],[1,2,3]):
 bad=(q.reclaim_x_wick>rxw).astype(int)+(q.close_x_reclaim>cxr).astype(int)+(q.sweep_minus_reclaim<smr).astype(int)+(q.impulse_minus_reclaim<imr).astype(int)+(q.quality_balance<qb).astype(int)
 z=q[bad<need].copy();m=met(z)
 if 3.2<=m[1]<=3.8 and len(z)>=1150:
  a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
  rows.append([rxw,cxr,smr,imr,qb,need,*m,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())])
r=pd.DataFrame(rows,columns=["reclaim_wick_max","close_reclaim_max","sweep_minus_reclaim_min","impulse_minus_reclaim_min","quality_balance_min","bad_signals_needed","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r=r.sort_values(["max_dd_r","max_loss_streak","robust_wr","trades"],ascending=[True,True,False,False])
r.to_csv("data/v12_interaction_filter_search.csv",index=False)
print("=== V12 INTERACTION FILTER SEARCH ===")
print("Input after V11 representative filter: 1257 trades | ~59.6% WR")
print("Candidates:",len(r));print(r.head(60).round(2).to_string(index=False))
print("\n55%+ both + <=5R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=5)).sum()))
print("55%+ both + <=4R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=4)).sum()))
print("\nSaved: data/v12_interaction_filter_search.csv")
