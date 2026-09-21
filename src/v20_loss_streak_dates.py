import pandas as pd
q=pd.read_csv("data/v19_failed_reversal_sequence.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True)
q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int)
runs=[];i=0
while i<len(q):
 if q.win.iloc[i]==0:
  j=i
  while j<len(q) and q.win.iloc[j]==0:j+=1
  n=j-i
  if n>=3:
   z=q.iloc[i:j]
   runs.append([z.candidate_time.iloc[0],z.candidate_time.iloc[-1],n,", ".join(sorted(z.session.unique()))])
  i=j
 else:i+=1
r=pd.DataFrame(runs,columns=["start_utc","end_utc","losses","sessions"]).sort_values("start_utc",ascending=False)
r["start_et"]=r.start_utc.dt.tz_convert("America/New_York")
r["end_et"]=r.end_utc.dt.tz_convert("America/New_York")
print("=== MOST RECENT 3+ LOSS STREAKS ===")
print(r[["start_et","end_et","losses","sessions"]].head(20).to_string(index=False))
print("\n2026 streak count:",int((r.start_et.dt.year==2026).sum()))
print("Last streak:",r.iloc[0][["start_et","end_et","losses","sessions"]].to_dict())
r.to_csv("data/v20_loss_streak_dates.csv",index=False)
