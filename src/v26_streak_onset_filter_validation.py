import pandas as pd, numpy as np
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
# Candidate "danger" ingredients suggested by V25 onset, but validate across full stream.
features={
"score_low":("score","low"),"reclaim_high":("early_reclaim_atr","high"),
"rw_high":("reclaim_x_wick","high"),"impulse_reclaim_low":("impulse_to_reclaim","low"),
"quality_low":("quality_balance","low")}
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def stats(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 active=z.candidate_time.dt.tz_convert("America/New_York").dt.date.nunique()
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return len(z),len(z)/active,100*z.win.mean(),z.r.sum(),dd,mx,100*a.win.mean(),100*b.win.mean()
rows=[]
# Thresholds derived from broad quantiles, not from exact streak examples.
for pct in [.20,.25,.30,.35,.40]:
 flags={}
 for name,(c,side) in features.items():
  th=q[c].quantile(pct if side=="low" else 1-pct)
  flags[name]=(q[c]<=th) if side=="low" else (q[c]>=th)
 names=list(flags)
 from itertools import combinations
 for k in range(2,6):
  for combo in combinations(names,k):
   bad=sum(flags[x].astype(int) for x in combo)
   for need in range(2,k+1):
    z=q[bad<need].copy()
    m=stats(z)
    if m[1]>=3.3:
     rem=q[bad>=need]
     rows.append([pct,"+".join(combo),need,len(rem),int(rem.cluster_loss.sum()),int(rem.win.sum()),*m])
r=pd.DataFrame(rows,columns=["tail","signals","bad_needed","removed","cluster_removed","wins_removed","trades","active_tpd","wr","net_r","max_dd_r","max_streak","train_wr","test_wr"])
r["robust_wr"]=r[["train_wr","test_wr"]].min(axis=1)
r.to_csv("data/v26_streak_onset_filter_validation.csv",index=False)
print("=== V26 STREAK-ONSET FILTER VALIDATION ===")
x=r[r.robust_wr>=55].sort_values(["max_dd_r","active_tpd","cluster_removed"],ascending=[True,False,False])
print(x.head(50).round(2).to_string(index=False))
print("\n>=3.5/day <=5R:",len(r[(r.active_tpd>=3.5)&(r.max_dd_r<=5)&(r.robust_wr>=55)]))
print(">=3.3/day <=5R:",len(r[(r.active_tpd>=3.3)&(r.max_dd_r<=5)&(r.robust_wr>=55)]))
