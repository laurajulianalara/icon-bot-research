import pandas as pd, numpy as np
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
et=q.candidate_time.dt.tz_convert("America/New_York");q["date"]=et.dt.date
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return len(z),len(z)/z.date.nunique(),100*z.win.mean(),z.r.sum(),dd,mx,100*a.win.mean(),100*b.win.mean()
rows=[]
# Search the full Option2 quality score continuum, then cap to 6/day by best score.
# This directly tests whether the existing candidate universe can physically support 4-5 qualified trades/day.
for score_min in np.arange(0.00,0.301,0.005):
 z=q[q.score>=score_min].copy()
 z["rank"]=z.groupby("date").score.rank(method="first",ascending=False)
 z=z[z["rank"]<=6].copy()
 rows.append([score_min,*met(z)])
r=pd.DataFrame(rows,columns=["score_min","trades","active_tpd","wr","net_r","dd_r","streak","train_wr","test_wr"])
r["robust_wr"]=r[["train_wr","test_wr"]].min(axis=1)
r.to_csv("data/v29_option2_frequency_ceiling.csv",index=False)
print("=== V29 OPTION 2 FREQUENCY CEILING ===")
print("BEST 4-5/DAY CONFIGURATIONS")
x=r[(r.active_tpd>=4)&(r.active_tpd<=5)].sort_values(["dd_r","robust_wr","active_tpd"],ascending=[True,False,False])
print(x.head(30).round(3).to_string(index=False))
print("\nHIGHEST FREQUENCY WITH >=60% BOTH TRAIN/TEST")
y=r[r.robust_wr>=60].sort_values("active_tpd",ascending=False)
print(y.head(15).round(3).to_string(index=False))
print("\nHIGHEST FREQUENCY WITH <=5R DD")
z=r[r.dd_r<=5].sort_values("active_tpd",ascending=False)
print(z.head(15).round(3).to_string(index=False))
