import pandas as pd
import numpy as np

IN="data/v7_base_trade_quality.parquet"; OUT="data/v8_dynamic_streak_avoidance.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)
b=d[(d.early_reclaim_atr<=.90)&(d.m2_close_pos<=.80)&(d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)].copy()
b["win"]=(b.outcome=="WIN").astype(int);b["r"]=np.where(b.win==1,4.,-1.)

# Test context that can explain clusters without permanently deleting normal trades:
# recent prior losses, same-session repeats, time spacing, and only tightening quality after losses.
def metrics(q):
 q=q.sort_values("candidate_time");eq=q.r.cumsum();dd=float((eq.cummax()-eq).max())
 cur=mx=0
 for w in q.win:
  cur=0 if w else cur+1;mx=max(mx,cur)
 return len(q),len(q)/365,100*q.win.mean(),q.r.sum(),q.r.mean(),dd,mx

rows=[]
# Dynamic rule: after N consecutive losses, require stronger reclaim/wick quality for next trade(s).
for trigger in [1,2,3]:
 for rec in [.60,.65,.70,.75,.80]:
  for wick in [.40,.45,.50,.55]:
   kept=[];streak=0
   for _,x in b.iterrows():
    take=True
    if streak>=trigger:
     take=(x.early_reclaim_atr<=rec and x.wick_percent<=wick)
    if take:
     kept.append(x)
     streak=0 if x.win else streak+1
   q=pd.DataFrame(kept)
   if len(q):
    m=metrics(q)
    if 3.5<=m[1]<=4.5:rows.append(("dynamic_quality",trigger,rec,wick,*m))

# Also test whether simply rejecting repeated candidates too close in time breaks clusters.
for mins in [3,5,10,15,20,30]:
 kept=[];last=None
 for _,x in b.iterrows():
  if last is None or (x.candidate_time-last).total_seconds()/60>=mins:
   kept.append(x);last=x.candidate_time
 q=pd.DataFrame(kept);m=metrics(q)
 if 3.5<=m[1]<=4.5:rows.append((f"spacing_{mins}m",0,np.nan,np.nan,*m))

r=pd.DataFrame(rows,columns=["rule","loss_trigger","reclaim_after_loss","wick_after_loss","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","max_losing_streak"])
r=r.sort_values(["max_dd_r","net_r"],ascending=[True,False]);r.to_csv(OUT,index=False)
print("=== DYNAMIC LOSS-CLUSTER AVOIDANCE ===")
print("Baseline: 1477 | 4.05/day | 57.55% | 2773R | DD 8R | streak 8")
print(r.head(40).round(2).to_string(index=False))
print("\n<=5R DD while keeping >=3.5/day:",int((r.max_dd_r<=5).sum()))
print("<=4R DD while keeping >=3.5/day:",int((r.max_dd_r<=4).sum()))
print("\nSaved:",OUT)
