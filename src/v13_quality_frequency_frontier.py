import pandas as pd, numpy as np
q=pd.read_csv("data/v12_surviving_loss_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 active=z.candidate_time.dt.date.nunique()
 daily=z.groupby(z.candidate_time.dt.date).size()
 return len(z),len(z)/365,len(z)/active,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx,int(daily.max()),int((daily>6).sum())
# Instead of stacking many filters, rank each trade by causal reversal quality.
# Percentile cutoffs let us search smoothly for the frequency/quality frontier.
rank_parts=[]
for col,good_high in [("rejection_quality",1),("impulse_to_reclaim",1),("sweep_minus_reclaim",1),
                       ("impulse_minus_reclaim",1),("quality_balance",1),("reclaim_x_wick",0),
                       ("close_x_reclaim",0),("wick_to_impulse",0)]:
 r=q[col].rank(pct=True)
 rank_parts.append(r if good_high else 1-r)
q["quality_score"]=pd.concat(rank_parts,axis=1).mean(axis=1)
rows=[]
for pct in np.arange(0,0.61,.01):
 z=q[q.quality_score>=q.quality_score.quantile(pct)].copy()
 m=met(z);a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 rows.append([pct,q.quality_score.quantile(pct),*m,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())])
r=pd.DataFrame(rows,columns=["drop_bottom_pct","score_min","trades","calendar_tpd","active_tpd","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","max_trades_day","days_over_6","train_wr","test_wr","robust_wr"])
r.to_csv("data/v13_quality_frequency_frontier.csv",index=False)
print("=== QUALITY / FREQUENCY FRONTIER ===")
print(r[(r.calendar_tpd>=3.0)&(r.calendar_tpd<=4.1)].sort_values(["max_dd_r","robust_wr"],ascending=[True,False]).head(40).round(2).to_string(index=False))
print("\nBest rows near original 4/day:")
print(r[(r.calendar_tpd>=3.7)&(r.calendar_tpd<=4.1)].sort_values(["robust_wr","max_dd_r"],ascending=[False,True]).head(20).round(2).to_string(index=False))
print("\nSaved: data/v13_quality_frequency_frontier.csv")
