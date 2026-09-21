import pandas as pd
import numpy as np
from itertools import product

IN="data/v10_daily_cluster_context.csv"; OUT="data/v10_context_quality_filter_search.csv"
q=pd.read_csv(IN);q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70

def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max())
 cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 return len(z),len(z)/365,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx

# Context-aware quality: don't cap trading. Tighten only once the day has accumulated losses
# or becomes unusually trade-heavy, using causal bad-setup evidence.
rows=[]
for loss_trigger,trade_trigger,rec,wick,m2 in product([3,4],[7,8,9],[.50,.55,.60],[.30,.35,.40],[-.60,-.45,-.30]):
 context=(q.day_prior_losses>=loss_trigger)|(q.day_trade_num>=trade_trigger)
 bad=(q.early_reclaim_atr>=rec).astype(int)+(q.wick_percent>=wick).astype(int)+(q.m2_move_atr>=m2).astype(int)+(q.sweep_atr<=.35).astype(int)
 # only reject in stressed context and only if 2+ bad setup signals agree
 keep=~(context & (bad>=2));z=q[keep].copy();m=met(z)
 if 3.5<=m[1]<=4.1:
  a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
  rows.append([loss_trigger,trade_trigger,rec,wick,m2,*m,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())])
r=pd.DataFrame(rows,columns=["prior_losses_trigger","trade_num_trigger","reclaim_bad","wick_bad","m2_move_bad","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r=r.sort_values(["max_dd_r","max_loss_streak","robust_wr","trades"],ascending=[True,True,False,False])
r.to_csv(OUT,index=False)
print("=== CONTEXT + QUALITY FILTER SEARCH ===")
print("Baseline: 1477 | 4.05/day | 57.55% | DD 8R | streak 8")
print(r.head(50).round(2).to_string(index=False))
print("\n>=55% train/test + <=5R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=5)).sum()))
print(">=55% train/test + <=4R DD:",int(((r.robust_wr>=55)&(r.max_dd_r<=4)).sum()))
print("\nSaved:",OUT)
