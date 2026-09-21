import pandas as pd
import numpy as np
from itertools import product

IN="data/v7_base_trade_quality.parquet"; OUT="data/v8_streak_filter_search.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)
base=d[(d.early_reclaim_atr<=.90)&(d.m2_close_pos<=.80)&(d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)].copy()
base["win"]=(base.outcome=="WIN").astype(int);base["r"]=np.where(base.win==1,4.,-1.)

# Search only around the three strongest streak signatures. Keep frequency near 4/day.
REC=[.55,.60,.65,.70,.75,.80,.85,.90]
WICK=[.35,.40,.45,.50,.55,.60]
CP=[.50,.55,.60,.65,.70,.75,.80]
BODY=[None,.20,.25,.30,.35] # optional minimum body: streak losses had smaller m2 bodies

def metrics(q):
 q=q.sort_values("candidate_time").copy()
 if len(q)<1:return None
 q["r"]=np.where(q.win==1,4.,-1.)
 eq=q.r.cumsum();dd=float((eq.cummax()-eq).max())
 # max consecutive losses
 cur=mx=0
 for w in q.win:
  cur=0 if w else cur+1;mx=max(mx,cur)
 return len(q),len(q)/365,100*q.win.mean(),q.r.sum(),q.r.mean(),dd,mx

# 70/30 untouched chronological stability check for each candidate filter.
cut=base.candidate_time.min()+(base.candidate_time.max()-base.candidate_time.min())*.70
rows=[]
for rec,wk,cp,body in product(REC,WICK,CP,BODY):
 q=base[(base.early_reclaim_atr<=rec)&(base.wick_percent<=wk)&(base.m2_close_pos<=cp)]
 if body is not None:q=q[q.m2_body_atr>=body]
 m=metrics(q)
 if not m or not 3.5<=m[1]<=4.5:continue
 a=q[q.candidate_time<cut];b=q[q.candidate_time>=cut]
 if len(a)<500 or len(b)<200:continue
 aw=100*a.win.mean();bw=100*b.win.mean()
 rows.append((rec,wk,cp,body if body is not None else -1,*m,aw,bw,min(aw,bw)))

r=pd.DataFrame(rows,columns=["reclaim_max","wick_max","m2_close_max","m2_body_min","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","max_losing_streak","train_wr","test_wr","robust_wr"])
r=r.sort_values(["max_dd_r","robust_wr","trades_per_day"],ascending=[True,False,False]).drop_duplicates(["trades","wr","max_dd_r"])
r.to_csv(OUT,index=False)
print("=== STREAK-REDUCTION FILTER SEARCH ===")
print("Baseline: 1477 trades | 4.05/day | 57.55% WR | max DD 8R | max loss streak 8")
print("Candidates keeping 3.5-4.5/day:",len(r))
print("\nTOP 40 BY LOWER DD + ROBUST WR:")
print(r.head(40).round(2).to_string(index=False))
print("\nCandidates >=55% both train/test and <=5R max DD:",int(((r.train_wr>=55)&(r.test_wr>=55)&(r.max_dd_r<=5)).sum()))
print("Candidates >=55% both train/test and <=4R max DD:",int(((r.train_wr>=55)&(r.test_wr>=55)&(r.max_dd_r<=4)).sum()))
print("\nSaved:",OUT)
