import pandas as pd, numpy as np
z=pd.read_csv("data/v27_option2a_trades.csv")
z["candidate_time"]=pd.to_datetime(z.candidate_time,utc=True)
end=z.candidate_time.max(); start=end-pd.Timedelta(days=90)
x=z[z.candidate_time>=start].copy()
x["win"]=(x.outcome=="WIN").astype(int);x["r"]=np.where(x.win==1,4.,-1.)
print("=== OPTION 2A — LAST 90 DAYS BY SESSION ===")
print("Window:",start,"to",end)
print("Total:",len(x),"trades | WR",f"{100*x.win.mean():.2f}%")
def md(g):
 eq=g.r.cumsum();return float((eq.cummax()-eq).max())
rows=[]
for s,g in x.groupby("session"):
 rows.append([s,len(g),int(g.win.sum()),int((1-g.win).sum()),100*g.win.mean(),g.r.sum(),g.r.mean(),md(g)])
o=pd.DataFrame(rows,columns=["session","trades","wins","losses","wr","net_r","exp_r","max_dd_r"]).sort_values("session")
print(o.round(2).to_string(index=False))
