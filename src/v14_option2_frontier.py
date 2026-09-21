import pandas as pd, numpy as np
q=pd.read_csv("data/v11_reversal_state_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def stats(z):
 z=z.sort_values("candidate_time").copy()
 # Hard final safety boundary: maximum first 6 qualified setups per ET calendar date
 z["d"]=z.candidate_time.dt.tz_convert("America/New_York").dt.date
 z["n"]=z.groupby("d").cumcount()+1;z=z[z.n<=6]
 eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 active=z.d.nunique();daily=z.groupby("d").size()
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return [len(z),len(z)/365,len(z)/active,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx,int(daily.max()),100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())]
# Smooth weighted score, searched for higher coverage than V12 hard interaction filters.
parts=[]
for col,hi,w in [("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),
                 ("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),
                 ("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]:
 r=q[col].rank(pct=True);parts += [(r if hi else 1-r)]*w
q["score"]=pd.concat(parts,axis=1).mean(axis=1)
rows=[]
for pct in np.arange(0,.46,.01):
 z=q[q.score>=q.score.quantile(pct)].copy();rows.append([pct,q.score.quantile(pct),*stats(z)])
r=pd.DataFrame(rows,columns=["drop_pct","score_min","trades","calendar_tpd","active_tpd","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","max_trades_day","train_wr","test_wr","robust_wr"])
r.to_csv("data/v14_option2_frontier.csv",index=False)
print("=== OPTION 2 FRONTIER — QUALITY + HARD 6/DAY SAFETY CAP ===")
print("\nTarget active-day frequency 4.0-5.5:")
x=r[(r.active_tpd>=4)&(r.active_tpd<=5.5)].sort_values(["max_dd_r","robust_wr","active_tpd"],ascending=[True,False,False])
print(x.head(40).round(2).to_string(index=False))
print("\nTarget >=55% both train/test, active >=4/day:")
y=r[(r.robust_wr>=55)&(r.active_tpd>=4)].sort_values(["max_dd_r","robust_wr"],ascending=[True,False])
print(y.head(30).round(2).to_string(index=False))
print("\nSaved: data/v14_option2_frontier.csv")
