import pandas as pd
tr=pd.read_csv("data/v27_option2a_trades.csv")
bars=pd.read_parquet("data/mnq_continuous_1m.parquet")
tr["candidate_time"]=pd.to_datetime(tr.candidate_time,utc=True)
bars["time_utc"]=pd.to_datetime(bars.time_utc,utc=True)
bars=bars.sort_values("time_utc").set_index("time_utc")
bad=tr[tr.outcome.eq("LOSS")].copy()
rows=[]
for _,r in bad.iterrows():
 t=r.candidate_time; entry=float(r.entry); risk=float(r.risk); long=r.direction=="LONG"
 stop=entry-risk if long else entry+risk; target=entry+4*risk if long else entry-4*risk
 w=bars.loc[t:t+pd.Timedelta(hours=4)]
 first_stop=first_target=None
 for ts,b in w.iterrows():
  sh=(b.low<=stop) if long else (b.high>=stop)
  th=(b.high>=target) if long else (b.low<=target)
  if sh and first_stop is None:first_stop=ts
  if th and first_target is None:first_target=ts
  if first_stop is not None and first_target is not None:break
 # only investigate rows where target appears no later than stop in this replay
 if first_target is not None and (first_stop is None or first_target<=first_stop):
  rows.append([t,r.session,r.direction,entry,risk,first_target,first_stop,
               None if first_target is None else (first_target-t).total_seconds()/60,
               None if first_stop is None else (first_stop-t).total_seconds()/60])
o=pd.DataFrame(rows,columns=["candidate_time","session","direction","entry","risk","first_4r","first_stop","mins_to_4r","mins_to_stop"])
print("=== V34 69-MISMATCH TIMING AUDIT ===")
print("Replay target-before-stop LOSS rows:",len(o))
if len(o):
 print("\nMinutes to apparent 4R:")
 print(o.mins_to_4r.describe().round(2).to_string())
 print("\nTarget/stop same minute:",(o.first_4r==o.first_stop).sum())
 print("Target before stop minute:",(o.first_4r<o.first_stop).sum())
 print("No stop within 4h:",o.first_stop.isna().sum())
 print("\nBy minutes to 4R:")
 print(pd.cut(o.mins_to_4r,[-.1,0,1,2,3,5,15,60,240],include_lowest=True).value_counts().sort_index().to_string())
 print("\nSample:")
 print(o.head(25).to_string(index=False))
o.to_csv("data/v34_mismatch_timing_audit.csv",index=False)
