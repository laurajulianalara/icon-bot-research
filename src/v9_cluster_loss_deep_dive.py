import pandas as pd
import numpy as np

IN="data/v8_volatility_forensics.csv"; OUT="data/v9_cluster_loss_deep_dive.csv"
q=pd.read_csv(IN);q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True)
q=q.sort_values("candidate_time").reset_index(drop=True);q["win"]=(q.outcome=="WIN").astype(int)
# Consecutive-loss runs; flag losses in runs >=3.
run=(q.win==1).cumsum();q["loss_run_size"]=q.assign(loss=1-q.win).groupby(run).loss.transform("sum")
q["class"]=np.where(q.win==1,"WIN",np.where(q.loss_run_size>=3,"STREAK_LOSS","NORMAL_LOSS"))

features=["early_reclaim_atr","wick_percent","m2_close_pos","m2_move_atr","m2_dir_bars5","sweep_atr",
          "atr20","vol_ratio_20_60","vol_ratio_20_240","range_ratio"]
print("=== DEEP LOSS FORENSICS ===")
print(q["class"].value_counts().to_string())
print("\nFEATURE DISTRIBUTIONS (not just averages)")
rows=[]
for f in features:
    print(f"\n--- {f} ---")
    t=q.groupby("class")[f].agg(["count","mean","median",lambda x:x.quantile(.25),lambda x:x.quantile(.75)])
    t.columns=["n","mean","median","p25","p75"];print(t.round(3).to_string())
    for cls in ["WIN","NORMAL_LOSS","STREAK_LOSS"]:
        s=q.loc[q["class"]==cls,f].dropna()
        rows.append([f,cls,len(s),s.mean(),s.median(),s.quantile(.1),s.quantile(.25),s.quantile(.75),s.quantile(.9)])

# Pair/triple signatures using thresholds learned from winner medians/quartiles; report coverage + loss concentration.
w=q[q["class"]=="WIN"]
conds={
"high_reclaim":q.early_reclaim_atr>w.early_reclaim_atr.median(),
"large_wick":q.wick_percent>w.wick_percent.median(),
"weak_m2_move":q.m2_move_atr>w.m2_move_atr.median(),
"weak_sweep":q.sweep_atr<w.sweep_atr.median(),
"low_range":q.range_ratio<w.range_ratio.median(),
"weak_m2_close":q.m2_close_pos>w.m2_close_pos.median(),
}
print("\n=== COMBINATION SIGNATURES ===")
from itertools import combinations
comb=[]
for k in [2,3,4]:
 for names in combinations(conds,k):
  m=np.logical_and.reduce([conds[n] for n in names]);z=q[m]
  if len(z)<50:continue
  comb.append([" + ".join(names),len(z),100*len(z)/len(q),100*z.win.mean(),100*(z["class"]=="STREAK_LOSS").mean()])
c=pd.DataFrame(comb,columns=["signature","trades","coverage_pct","wr","streak_loss_pct"]).sort_values(["streak_loss_pct","trades"],ascending=[False,False])
print(c.head(40).round(2).to_string(index=False))

# Time/session context of all streak losses.
q["ny"]=q.candidate_time.dt.tz_convert("America/New_York");q["hour"]=q.ny.dt.hour
print("\n=== STREAK LOSS CONTEXT ===")
print("\nBy session:");print(pd.crosstab(q.session,q["class"],normalize="columns").mul(100).round(2).to_string())
print("\nBy hour ET (counts):");print(pd.crosstab(q.hour,q["class"]).to_string())

pd.DataFrame(rows,columns=["feature","class","n","mean","median","p10","p25","p75","p90"]).to_csv(OUT,index=False)
c.to_csv("data/v9_cluster_loss_signatures.csv",index=False)
print("\nSaved:",OUT,"and data/v9_cluster_loss_signatures.csv")
