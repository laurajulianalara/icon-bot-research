import pandas as pd
import numpy as np

IN="data/v7_base_trade_quality.parquet"; OUT="data/v7_finalist_stress_test.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)

# Lock the best broad sweet-spot rule BEFORE this stress test.
P=dict(reclaim=.90,cp=.80,wick=.60,mv=.15,db=4)
q=d[(d.early_reclaim_atr<=P["reclaim"])&(d.m2_close_pos<=P["cp"])&(d.wick_percent<=P["wick"])&(d.m2_move_atr<=P["mv"])&(d.m2_dir_bars5<=P["db"])].copy()
q["win"]=(q.outcome=="WIN").astype(int)
q["r"]=np.where(q.win==1,4.0,-1.0)
q["month"]=q.candidate_time.dt.to_period("M").astype(str)
q["date"]=q.candidate_time.dt.date

# 10 chronological folds: no more threshold tuning.
folds=np.array_split(np.arange(len(q)),10)
fr=[]
for n,ix in enumerate(folds,1):
 z=q.iloc[ix];fr.append((n,len(z),100*z.win.mean(),z.r.sum()))
f=pd.DataFrame(fr,columns=["fold","trades","wr","net_r"])

mo=q.groupby("month").agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()),net_r=("r","sum")).reset_index()
se=q.groupby("session").agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()),net_r=("r","sum")).reset_index()

# Chronological equity / DD / losing streak.
eq=q.r.cumsum(); peak=eq.cummax(); maxdd=float((peak-eq).max())
loss=(q.win==0).astype(int);grp=(q.win==1).cumsum();maxls=int(loss.groupby(grp).sum().max())
daily=q.groupby("date").r.sum(); daily_wr=100*(daily>0).mean()
# Peak-to-trough within each calendar day from trade sequence.
dds=[]
for _,z in q.groupby("date"):
 e=z.r.cumsum();dds.append(float((e.cummax()-e).max()))
worst_daily=max(dds) if dds else 0

summary=pd.DataFrame([{
 "trades":len(q),"trades_per_day":len(q)/365,"wr":100*q.win.mean(),"net_r":q.r.sum(),
 "expectancy_r":q.r.mean(),"max_dd_r":maxdd,"worst_daily_dd_r":worst_daily,
 "max_losing_streak":maxls,"profitable_days_pct":daily_wr,
 "worst_fold_wr":f.wr.min(),"best_fold_wr":f.wr.max(),
 "profitable_months":int((mo.net_r>0).sum()),"months":len(mo)
}])
summary.to_csv(OUT,index=False)
print("=== LOCKED FINALIST STRESS TEST ===")
print(summary.round(2).to_string(index=False))
print("\n=== 10 CHRONOLOGICAL FOLDS ===")
print(f.round(2).to_string(index=False))
print("\n=== SESSION STABILITY ===")
print(se.round(2).to_string(index=False))
print("\n=== MONTHLY STABILITY ===")
print(mo.round(2).to_string(index=False))
print("\nSaved:",OUT)
