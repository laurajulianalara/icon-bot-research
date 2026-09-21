import pandas as pd, numpy as np
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def stats(z):
 z=z.sort_values("candidate_time").copy();eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 et=z.candidate_time.dt.tz_convert("America/New_York");active=et.dt.date.nunique()
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return [len(z),len(z)/active,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())]
rows=[]
# Broad score cutoffs + optional late-session quality requirement. No arbitrary loss-streak guardrail.
for base in np.arange(.20,.51,.025):
 for late_extra in [0,.025,.05,.075,.10,.15]:
  keep=(q.score>=base) & ((q.mins_into_session<90) | (q.score>=base+late_extra))
  z=q[keep].copy();m=stats(z)
  rows.append([base,late_extra,*m])
r=pd.DataFrame(rows,columns=["base_score","late_extra","trades","active_tpd","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r.to_csv("data/v22_option2_quality_frontier.csv",index=False)
print("=== V22 OPTION 2 QUALITY/FREQUENCY/DD FRONTIER ===")
x=r[(r.active_tpd>=3.0)&(r.robust_wr>=55)].sort_values(["max_dd_r","active_tpd","robust_wr"],ascending=[True,False,False])
print(x.head(40).round(2).to_string(index=False))
print("\n>=3.5 active/day and <=5R DD:",len(r[(r.active_tpd>=3.5)&(r.max_dd_r<=5)&(r.robust_wr>=55)]))
print(">=3.0 active/day and <=5R DD:",len(r[(r.active_tpd>=3.0)&(r.max_dd_r<=5)&(r.robust_wr>=55)]))
