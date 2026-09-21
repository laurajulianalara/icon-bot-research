import pandas as pd, numpy as np
q=pd.read_csv("data/v15_option2_loss_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def met(z):
 z=z.sort_values("candidate_time").copy()
 eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 active=z.candidate_time.dt.tz_convert("America/New_York").dt.date.nunique()
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return [len(z),len(z)/active,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())]
rows=[]
# Reject only combinations showing multiple remaining loser traits.
for rec in [.45,.50,.55,.60]:
 for rw in [.12,.14,.16,.18]:
  for cr in [.18,.20,.22,.24]:
   for im in [.05,.10,.15,.20]:
    for badn in [2,3,4]:
     bad=(q.early_reclaim_atr>rec).astype(int)+(q.reclaim_x_wick>rw).astype(int)+(q.close_x_reclaim>cr).astype(int)+(q.impulse_minus_reclaim<im).astype(int)
     z=q[bad<badn].copy();m=met(z)
     if m[0]>=950 and m[1]>=3.5:
      rows.append([rec,rw,cr,im,badn,*m])
r=pd.DataFrame(rows,columns=["reclaim_bad","reclaim_wick_bad","close_reclaim_bad","impulse_minus_reclaim_bad","bad_signals_needed","trades","active_tpd","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r.to_csv("data/v16_option2_selective_filter.csv",index=False)
print("=== V16 OPTION 2 SELECTIVE LOSS FILTER ===")
print("Candidates:",len(r))
if len(r):
 x=r.sort_values(["max_dd_r","robust_wr","active_tpd"],ascending=[True,False,False])
 print(x.head(50).round(2).to_string(index=False))
 print("\n>=55% both, >=3.5 active/day, <=5R DD:",len(r[(r.robust_wr>=55)&(r.max_dd_r<=5)]))
 print(">=55% both, >=3.5 active/day, <=4R DD:",len(r[(r.robust_wr>=55)&(r.max_dd_r<=4)]))
print("\nSaved: data/v16_option2_selective_filter.csv")
