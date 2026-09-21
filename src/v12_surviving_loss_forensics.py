import pandas as pd, numpy as np
q=pd.read_csv("data/v11_reversal_state_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
# Analyze losers that survive a representative strong quality filter from V11.
bad=(q.rejection_quality<.50).astype(int)+(q.impulse_to_reclaim<.50).astype(int)+(q.reclaim_to_sweep>1.60).astype(int)
z=q[bad<3].copy()
run=(z.win==1).cumsum();ls=z.assign(loss=1-z.win).groupby(run).loss.transform("sum")
z["class"]=np.where(z.win==1,"WIN",np.where(ls>=3,"STREAK_LOSS","NORMAL_LOSS"))

# Causal interaction/state features, all based on pre-entry columns already available.
eps=.05
z["wick_to_impulse"]=z.wick_percent/(z.reversal_impulse.abs()+eps)
z["reclaim_x_wick"]=z.early_reclaim_atr*z.wick_percent
z["close_x_reclaim"]=z.m2_close_pos*z.early_reclaim_atr
z["sweep_minus_reclaim"]=z.sweep_atr-z.early_reclaim_atr
z["impulse_minus_reclaim"]=z.reversal_impulse-z.early_reclaim_atr
z["quality_balance"]=z.rejection_quality*z.impulse_to_reclaim/(1+z.reclaim_to_sweep)
features=["wick_to_impulse","reclaim_x_wick","close_x_reclaim","sweep_minus_reclaim","impulse_minus_reclaim","quality_balance",
"early_reclaim_atr","wick_percent","m2_close_pos","reversal_impulse","sweep_atr","range_ratio","atr20"]
print("=== SURVIVING-LOSS FORENSICS AFTER V11 QUALITY FILTER ===")
print(z["class"].value_counts().to_string())
rows=[]
for f in features:
 w=z.loc[z["class"]=="WIN",f].dropna();s=z.loc[z["class"]=="STREAK_LOSS",f].dropna()
 eff=(s.mean()-w.mean())/(z[f].std()+1e-9)
 rows.append([f,w.mean(),s.mean(),eff])
print(pd.DataFrame(rows,columns=["feature","winner_mean","streak_loss_mean","effect"]).sort_values("effect",key=abs,ascending=False).round(3).to_string(index=False))
print("\n=== WR QUINTILES: NEW INTERACTIONS ===")
for f in features[:6]:
 z["bin"]=pd.qcut(z[f],5,duplicates="drop")
 print("\n"+f);print(z.groupby("bin",observed=True).agg(trades=("win","size"),wr=("win",lambda x:100*x.mean())).round(2).to_string())
z.drop(columns=["bin"],errors="ignore").to_csv("data/v12_surviving_loss_forensics.csv",index=False)
print("\nSaved: data/v12_surviving_loss_forensics.csv")
