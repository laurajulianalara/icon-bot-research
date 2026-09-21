import pandas as pd, numpy as np, itertools
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
et=q.candidate_time.dt.tz_convert("America/New_York");q["date"]=et.dt.date
# Search around the V26 discovery: reject only when reclaim AND reclaim*wick are both poor.
# Broad thresholds deliberately include looser filters to recover frequency.
reclaim_q=np.arange(.72,.96,.02);rw_q=np.arange(.72,.96,.02)
rows=[]
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def metrics(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 active=z.date.nunique();daily=z.groupby("date").size()
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return len(z),len(z)/active,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx,int(daily.max()),100*a.win.mean(),100*b.win.mean()
for rq,wq in itertools.product(reclaim_q,rw_q):
 rt=q.early_reclaim_atr.quantile(rq);wt=q.reclaim_x_wick.quantile(wq)
 z=q[~((q.early_reclaim_atr>=rt)&(q.reclaim_x_wick>=wt))].copy()
 m=metrics(z)
 rows.append([rq,wq,rt,wt,*m])
r=pd.DataFrame(rows,columns=["reclaim_q","rw_q","reclaim_thr","rw_thr","trades","active_tpd","wr","net_r","exp_r","max_dd_r","max_streak","raw_max_day","train_wr","test_wr"])
r["robust_wr"]=r[["train_wr","test_wr"]].min(axis=1)
# Also enforce final hard 6/day by retaining highest quality-score six if raw candidates exceed six.
capped=[]
for _,a in r.iterrows():
 z=q[~((q.early_reclaim_atr>=a.reclaim_thr)&(q.reclaim_x_wick>=a.rw_thr))].copy()
 z["day_rank"]=z.groupby("date").score.rank(method="first",ascending=False)
 z=z[z.day_rank<=6].copy()
 capped.append(metrics(z))
cols=["cap_trades","cap_active_tpd","cap_wr","cap_net_r","cap_exp_r","cap_dd_r","cap_streak","cap_max_day","cap_train_wr","cap_test_wr"]
r[cols]=pd.DataFrame(capped,index=r.index)
r["cap_robust_wr"]=r[["cap_train_wr","cap_test_wr"]].min(axis=1)
r.to_csv("data/v28_option2b_frequency_frontier.csv",index=False)
print("=== V28 OPTION 2B FREQUENCY FRONTIER ===")
x=r[(r.cap_active_tpd>=4)&(r.cap_robust_wr>=55)].sort_values(["cap_dd_r","cap_wr","cap_active_tpd"],ascending=[True,False,False])
print(x.head(40).round(3).to_string(index=False))
print("\n4-5/day + <=5R DD + >=60% both:",len(r[(r.cap_active_tpd>=4)&(r.cap_active_tpd<=5)&(r.cap_dd_r<=5)&(r.cap_robust_wr>=60)]))
print("4-5/day + <=6R DD + >=60% both:",len(r[(r.cap_active_tpd>=4)&(r.cap_active_tpd<=5)&(r.cap_dd_r<=6)&(r.cap_robust_wr>=60)]))
