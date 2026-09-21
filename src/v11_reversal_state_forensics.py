import pandas as pd, numpy as np
q=pd.read_csv("data/v10_daily_cluster_context.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int)
# Build causal market-state features from already available pre-entry fields.
eps=1e-9
q["rejection_quality"]=(1-q.m2_close_pos.clip(0,1))*(1-q.wick_percent.clip(0,1))
q["reversal_impulse"]=(-q.m2_move_atr)
q["reclaim_to_sweep"]=q.early_reclaim_atr/(q.sweep_atr.abs()+.05)
q["impulse_to_reclaim"]=q.reversal_impulse/(q.early_reclaim_atr.abs()+.05)
q["compression_score"]=q.range_ratio/(q.vol_ratio_20_60.abs()+eps)
run=(q.win==1).cumsum();sz=q.assign(loss=1-q.win).groupby(run).win.transform("size")
# correct streak-loss label via loss-run counts
lossrun=(q.win==1).cumsum();ls=q.assign(loss=1-q.win).groupby(lossrun).loss.transform("sum")
q["class"]=np.where(q.win==1,"WIN",np.where(ls>=3,"STREAK_LOSS","NORMAL_LOSS"))
features=["rejection_quality","reversal_impulse","reclaim_to_sweep","impulse_to_reclaim","compression_score",
"early_reclaim_atr","wick_percent","m2_close_pos","m2_move_atr","sweep_atr","range_ratio","vol_ratio_20_60","vol_ratio_20_240"]
print("=== REVERSAL QUALITY / MARKET-STATE FORENSICS ===")
rows=[]
for f in features:
 g=q.groupby("class")[f].agg(["count","mean","median"])
 w=q.loc[q["class"]=="WIN",f].dropna();s=q.loc[q["class"]=="STREAK_LOSS",f].dropna()
 effect=(s.mean()-w.mean())/(q[f].std()+eps)
 rows.append([f,w.mean(),s.mean(),effect])
print(pd.DataFrame(rows,columns=["feature","winner_mean","streak_loss_mean","effect"]).sort_values("effect",key=abs,ascending=False).round(3).to_string(index=False))
print("\n=== WR BY QUINTILE FOR NEW COMPOSITE FEATURES ===")
for f in features[:5]:
 try:q["bin"]=pd.qcut(q[f],5,duplicates="drop")
 except:continue
 z=q.groupby("bin",observed=True).agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()))
 print("\n"+f);print(z.round(2).to_string())
q.drop(columns=["bin"],errors="ignore").to_csv("data/v11_reversal_state_forensics.csv",index=False)
print("\nSaved: data/v11_reversal_state_forensics.csv")
