import pandas as pd
import numpy as np

IN="data/v8_volatility_forensics.csv"; OUT="data/v8_volatility_filter_validation.csv"
q=pd.read_csv(IN)
# CSV contains mixed DST offsets (-04:00/-05:00). Normalize to UTC so pandas 3.x parses safely.
q["candidate_time"]=pd.to_datetime(q["candidate_time"],utc=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)

tests={
"BASE":pd.Series(True,index=q.index),
"REMOVE_ASIA_LOWEST20":~((q.session=="ASIA")&(q.vol_bin=="LOWEST20")),
"REMOVE_ASIA_LOWEST20_NYPM_LOWEST20":~(((q.session=="ASIA")|(q.session=="NYPM"))&(q.vol_bin=="LOWEST20")),
"REMOVE_ASIA_LOWEST20_LONDON_LOW20_40":~(((q.session=="ASIA")&(q.vol_bin=="LOWEST20"))|((q.session=="LONDON")&(q.vol_bin=="LOW20-40"))),
}
def met(z):
 z=z.sort_values("candidate_time");eq=z.r.cumsum();dd=float((eq.cummax()-eq).max())
 cur=mx=0
 for w in z.win:
  cur=0 if w else cur+1;mx=max(mx,cur)
 return len(z),len(z)/365,100*z.win.mean(),z.r.sum(),z.r.mean(),dd,mx

cut=q.candidate_time.min()+(q.candidate_time.max()-q.candidate_time.min())*.70
rows=[]
for name,mask in tests.items():
 z=q[mask].copy();a=z[z.candidate_time<cut];b=z[z.candidate_time>=cut]
 m=met(z)
 rows.append((name,*m,100*a.win.mean(),100*b.win.mean(),min(100*a.win.mean(),100*b.win.mean())))
r=pd.DataFrame(rows,columns=["rule","trades","trades_per_day","wr","net_r","expectancy_r","max_dd_r","max_loss_streak","train_wr","test_wr","robust_wr"])
r.to_csv(OUT,index=False)
print("=== VOLATILITY FILTER VALIDATION ===")
print(r.round(2).to_string(index=False))
print("\nSaved:",OUT)
