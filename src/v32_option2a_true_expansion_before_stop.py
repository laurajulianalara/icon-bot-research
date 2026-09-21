import pandas as pd, numpy as np
tr=pd.read_csv("data/v27_option2a_trades.csv")
bars=pd.read_parquet("data/mnq_continuous_1m.parquet")
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True)
bars["time_utc"]=pd.to_datetime(bars["time_utc"],utc=True)
bars=bars.sort_values("time_utc").set_index("time_utc")
rows=[]
for _,r in tr.iterrows():
 t=r.candidate_time; entry=float(r.entry); risk=float(r.risk)
 if risk<=0: continue
 w=bars.loc[t:t+pd.Timedelta(hours=4)]
 if w.empty: continue
 is_long=str(r.direction).upper()=="LONG"
 stop=entry-risk if is_long else entry+risk
 maxr=0.0; stopped=False
 # Conservative path: once original 1R stop is touched, trade is over.
 for _,b in w.iterrows():
  if is_long:
   if b.low<=stop: stopped=True; break
   maxr=max(maxr,(b.high-entry)/risk)
  else:
   if b.high>=stop: stopped=True; break
   maxr=max(maxr,(entry-b.low)/risk)
 rows.append([t,r.session,r.outcome,maxr,stopped])
o=pd.DataFrame(rows,columns=["time","session","outcome","mfe_before_stop_r","stopped"])
print("=== OPTION 2A TRUE EXPANSION BEFORE ORIGINAL STOP — 4H ===")
print("Trades measured:",len(o))
print(f"Average MFE before stop: {o.mfe_before_stop_r.mean():.2f}R | Median: {o.mfe_before_stop_r.median():.2f}R")
for rr in [4,5,6,8,10,12,15,20]:
 print(f">= {rr:2d}R before stop: {(o.mfe_before_stop_r>=rr).sum():4d} | {100*(o.mfe_before_stop_r>=rr).mean():5.2f}%")
w=o[o.outcome=="WIN"]
print("\nORIGINAL 4R WINNERS")
print(f"Count {len(w)} | Avg MFE {w.mfe_before_stop_r.mean():.2f}R | Median {w.mfe_before_stop_r.median():.2f}R")
for rr in [5,6,8,10,12,15,20]:
 print(f">= {rr:2d}R before stop: {(w.mfe_before_stop_r>=rr).sum():4d} | {100*(w.mfe_before_stop_r>=rr).mean():5.2f}%")
print("\nBY SESSION")
print(o.groupby("session").mfe_before_stop_r.agg(["count","mean","median","max"]).round(2).to_string())
o.to_csv("data/v32_option2a_true_expansion_before_stop.csv",index=False)
