import pandas as pd, numpy as np
q=pd.read_csv("data/v17_market_regime_forensics.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time")
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max());cur=mx=0
 for w in z.win:cur=0 if w else cur+1;mx=max(mx,cur)
 active=z.candidate_time.dt.tz_convert("America/New_York").dt.date.nunique()
 a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 return [len(z),len(z)/active,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())]
rows=[]
# Test only broad regime exclusions suggested by V17; no fine-grained optimization.
for loc60_mid_bad in [0,1]:
 for r30_hi_bad in [0,1]:
  for r15_hi_bad in [0,1]:
   for require_bad in [1,2,3]:
    bad=np.zeros(len(q),dtype=int)
    n=0
    if loc60_mid_bad:
     bad+=((q.loc60>=.45)&(q.loc60<.95)).astype(int);n+=1
    if r30_hi_bad:
     bad+=((q.range30_atr>=6.0)&(q.range30_atr<7.1)).astype(int);n+=1
    if r15_hi_bad:
     bad+=((q.range15_atr>=4.35)&(q.range15_atr<5.25)).astype(int);n+=1
    if n==0 or require_bad>n: continue
    z=q[bad<require_bad].copy();m=met(z)
    if m[0]>=950 and m[1]>=3.3:
     rows.append([loc60_mid_bad,r30_hi_bad,r15_hi_bad,require_bad,*m])
r=pd.DataFrame(rows,columns=["loc60_mid_bad","range30_band_bad","range15_band_bad","bad_needed","trades","active_tpd","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r.to_csv("data/v18_regime_filter_validation.csv",index=False)
print("=== V18 REGIME FILTER VALIDATION ===")
if len(r):
 print(r.sort_values(["max_dd_r","robust_wr"],ascending=[True,False]).round(2).to_string(index=False))
 print("\n<=5R DD, >=55% both, >=3.3 active/day:",len(r[(r.max_dd_r<=5)&(r.robust_wr>=55)&(r.active_tpd>=3.3)]))
else: print("No qualifying rows.")
print("\nSaved: data/v18_regime_filter_validation.csv")
