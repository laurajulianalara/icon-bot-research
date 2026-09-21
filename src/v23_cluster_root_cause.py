import pandas as pd, numpy as np
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
# Focus specifically on the 169 clustered losses vs all other trades.
a=q[q.cluster_loss==1];b=q[q.cluster_loss==0]
# Build interaction candidates from causal pre-entry fields.
base=["score","early_reclaim_atr","wick_percent","m2_close_pos","reversal_impulse","sweep_atr","rejection_quality","impulse_to_reclaim","reclaim_to_sweep","reclaim_x_wick","close_x_reclaim","sweep_minus_reclaim","impulse_minus_reclaim","quality_balance","mins_into_session"]
cols=[c for c in base if c in q.columns]
# Rank single features by standardized cluster separation.
rows=[]
for c in cols:
 sd=q[c].std();e=(a[c].mean()-b[c].mean())/sd if sd else 0
 rows.append([c,b[c].mean(),a[c].mean(),e])
r=pd.DataFrame(rows,columns=["feature","other_mean","cluster_mean","effect"]).sort_values("effect",key=lambda s:s.abs(),ascending=False)
print("=== V23 CLUSTER-SPECIFIC ROOT CAUSE ===")
print(f"Cluster losses {len(a)} / total losses {(q.win==0).sum()}")
print(r.round(3).to_string(index=False))
# Decile concentration: which feature tails capture cluster losses without deleting too many trades?
out=[]
for c in cols:
 s=q[c].dropna()
 for pct in [10,15,20,25,30]:
  lo=s.quantile(pct/100);hi=s.quantile(1-pct/100)
  for side,mask in [("LOW",q[c]<=lo),("HIGH",q[c]>=hi)]:
   captured=int(q.loc[mask,"cluster_loss"].sum());removed=int(mask.sum())
   wins_removed=int(q.loc[mask,"win"].sum())
   out.append([c,pct,side,removed,captured,100*captured/max(1,len(a)),wins_removed,100*captured/max(1,removed)])
o=pd.DataFrame(out,columns=["feature","tail_pct","side","trades_removed","cluster_losses_captured","cluster_capture_pct","wins_removed","cluster_density_pct"])
o=o.sort_values(["cluster_capture_pct","wins_removed"],ascending=[False,True])
print("\nBEST TAILS FOR CAPTURING CLUSTER LOSSES")
print(o.head(30).round(2).to_string(index=False))
o.to_csv("data/v23_cluster_capture.csv",index=False)
