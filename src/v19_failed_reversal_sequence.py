import pandas as pd, numpy as np
q=pd.read_csv("data/v15_option2_loss_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
# Identify losses that belong to 3+ consecutive-loss clusters.
cluster=np.zeros(len(q),dtype=int);i=0
while i<len(q):
 if q.win.iloc[i]==0:
  j=i
  while j<len(q) and q.win.iloc[j]==0:j+=1
  if j-i>=3:cluster[i:j]=1
  i=j
 else:i+=1
q["cluster_loss"]=cluster
print("=== V19 FAILED-REVERSAL SEQUENCE FORENSICS ===")
print("Trades:",len(q),"cluster losses:",int(q.cluster_loss.sum()))
# Compare the developing 1m sequence and reversal anatomy already known causally.
features=["m1_move_atr","m1_close_pos","m1_dir_bars5","m2_move_atr","m2_body_atr","m2_close_pos","m2_dir_bars5",
"early_reclaim_atr","early_adverse_atr","wick_percent","sweep_atr","rejection_quality","reversal_impulse",
"reclaim_to_sweep","impulse_to_reclaim","reclaim_x_wick","close_x_reclaim","sweep_minus_reclaim","impulse_minus_reclaim","quality_balance","score"]
rows=[]
a=q[q.cluster_loss==1];b=q[q.win==1]
for c in features:
 if c not in q.columns:continue
 sd=q[c].std();effect=(a[c].mean()-b[c].mean())/sd if sd else 0
 rows.append([c,b[c].mean(),a[c].mean(),effect])
r=pd.DataFrame(rows,columns=["feature","winner_mean","cluster_loss_mean","effect_cluster_minus_win"]).sort_values("effect_cluster_minus_win",key=lambda s:s.abs(),ascending=False)
print(r.round(3).to_string(index=False))
# Time-of-session behavior
t=q.candidate_time.dt.tz_convert("America/New_York")
q["minute_of_day"]=t.dt.hour*60+t.dt.minute
starts={"ASIA":20*60,"LONDON":2*60,"NYAM":9*60+30,"NYPM":13*60+30}
def mins_since(row):
 m=row.minute_of_day;s=starts.get(row.session,np.nan)
 if pd.isna(s):return np.nan
 return (m-s)%1440
q["mins_into_session"]=q.apply(mins_since,axis=1)
print("\nMinutes into session:")
print(q.groupby(["cluster_loss","win"]).mins_into_session.agg(["count","mean","median"]).round(2).to_string())
print("\nCluster-loss rate by 30-minute session bucket:")
q["session_bucket"]=(q.mins_into_session//30).astype("Int64")
x=q.groupby("session_bucket").agg(trades=("win","size"),wr=("win","mean"),cluster_loss_pct=("cluster_loss","mean"))
x["wr"]*=100;x["cluster_loss_pct"]*=100
print(x.round(2).to_string())
q.to_csv("data/v19_failed_reversal_sequence.csv",index=False)
r.to_csv("data/v19_failed_reversal_feature_effects.csv",index=False)
print("\nSaved V19 files.")
