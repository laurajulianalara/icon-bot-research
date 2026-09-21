import pandas as pd
import numpy as np

IN="data/v7_base_trade_quality.parquet"; OUT="data/v7_daily_guardrails.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)
q=d[(d.early_reclaim_atr<=.90)&(d.m2_close_pos<=.80)&(d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)].copy()
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.0,-1.0);q["date"]=q.candidate_time.dt.date

def run(max_trades=None,stop_losses=None,stop_dd=None):
 kept=[]
 for day,z in q.groupby("date",sort=True):
  losses=0;eq=0.;peak=0.
  for ix,row in z.sort_values("candidate_time").iterrows():
   if max_trades is not None and len([x for x in kept if x[0]==day])>=max_trades: break
   if stop_losses is not None and losses>=stop_losses: break
   if stop_dd is not None and peak-eq>=stop_dd: break
   kept.append((day,ix,row.r))
   eq+=row.r;peak=max(peak,eq)
   if row.r<0:losses+=1
 k=q.loc[[x[1] for x in kept]].copy() if kept else q.iloc[0:0].copy()
 if len(k)==0:return None
 k["r"]=np.where(k.win==1,4.,-1.);eq=k.r.cumsum();dd=(eq.cummax()-eq).max()
 daily=k.groupby(k.candidate_time.dt.date).r.sum()
 return len(k),len(k)/365,100*k.win.mean(),k.r.sum(),k.r.mean(),float(dd),float(daily.min()),100*(daily>0).mean()

rows=[]
for mt in [4,5,6,None]:
 for sl in [2,3,4,None]:
  for sd in [3,4,5,None]:
   s=run(mt,sl,sd)
   if s:rows.append((mt or 99,sl or 99,sd or 99,*s))
r=pd.DataFrame(rows,columns=["max_trades_day","stop_after_losses","stop_at_dd_r","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","worst_day_r","profitable_days_pct"])
r["max_trades_day"]=r.max_trades_day.replace(99,"NONE");r["stop_after_losses"]=r.stop_after_losses.replace(99,"NONE");r["stop_at_dd_r"]=r.stop_at_dd_r.replace(99,"NONE")
r=r.sort_values(["max_dd_r","net_r"],ascending=[True,False]);r.to_csv(OUT,index=False)
print("=== DAILY RISK GUARDRAIL TEST ===")
print("Baseline: 1477 trades | 57.55% WR | 2773R | max DD 8R")
print("\nBest combinations balancing DD and retained profit:")
print(r[(r.trades_per_day>=3)&(r.wr>=55)].head(35).round(2).to_string(index=False))
print("\nSaved:",OUT)
