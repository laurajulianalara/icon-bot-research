import pandas as pd, numpy as np
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
# percentile-derived broad bad tails; combinations only, never single-tail deletion
defs={
"reclaim": q.early_reclaim_atr>=q.early_reclaim_atr.quantile(.75),
"close_reclaim": q.close_x_reclaim>=q.close_x_reclaim.quantile(.75),
"reclaim_wick": q.reclaim_x_wick>=q.reclaim_x_wick.quantile(.75),
"score": q.score<=q.score.quantile(.25),
"sweep_reclaim": q.sweep_minus_reclaim<=q.sweep_minus_reclaim.quantile(.25),
"quality": q.quality_balance<=q.quality_balance.quantile(.25),
"reject": q.rejection_quality<=q.rejection_quality.quantile(.25)}
def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 active=z.candidate_time.dt.tz_convert("America/New_York").dt.date.nunique()
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return [len(z),len(z)/active,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())]
from itertools import combinations
rows=[]
keys=list(defs)
for k in range(2,6):
 for combo in combinations(keys,k):
  bad=sum(defs[x].astype(int) for x in combo)
  for need in range(2,k+1):
   z=q[bad<need].copy();m=met(z)
   if m[1]>=3.3:
    removed=q[bad>=need]
    rows.append(["+".join(combo),need,len(removed),int(removed.cluster_loss.sum()),int(removed.win.sum()),*m])
r=pd.DataFrame(rows,columns=["signals","bad_needed","removed","cluster_losses_removed","wins_removed","trades","active_tpd","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r.to_csv("data/v24_cluster_combo_filter.csv",index=False)
print("=== V24 CLUSTER COMBINATION FILTER ===")
x=r[(r.robust_wr>=55)].sort_values(["max_dd_r","cluster_losses_removed","active_tpd"],ascending=[True,False,False])
print(x.head(50).round(2).to_string(index=False))
print("\n>=3.5/day <=5R DD:",len(r[(r.active_tpd>=3.5)&(r.max_dd_r<=5)&(r.robust_wr>=55)]))
print(">=3.3/day <=5R DD:",len(r[(r.active_tpd>=3.3)&(r.max_dd_r<=5)&(r.robust_wr>=55)]))
