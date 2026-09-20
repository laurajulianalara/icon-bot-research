import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_four_session_risk_diagnostic.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&df.outcome.isin(["WIN","LOSS"])].copy()

rules={
 "ASIA":(.95,1.20,.20),"LONDON":(.96,1.20,.20),
 "NYAM":(.95,1.20,.20),"NYPM":(.97,1.10,None)
}
parts=[]
for s,(c,d,sw) in rules.items():
 q=df[df.session==s].copy()
 q=q[(q.confirm_close_pos>=c)&(q.disp_atr>=d)]
 if sw is not None:q=q[q.sweep_atr>=sw]
 parts.append(q)
z=pd.concat(parts).sort_values("fill_time").copy()
z["day"]=z.fill_time.dt.date

# chronological equity DD
eq=z.result_r.cumsum()
overall_dd=abs((eq-eq.cummax()).min())

# losing streak
loss=(z.outcome=="LOSS").to_numpy()
max_streak=cur=0
for x in loss:
 cur=cur+1 if x else 0
 max_streak=max(max_streak,cur)

daily=[]
for day,g in z.groupby("day"):
 e=g.result_r.cumsum()
 dd=abs((e-e.cummax()).min())
 daily.append((day,len(g),g.result_r.sum(),dd))
d=pd.DataFrame(daily,columns=["day","trades","net_r","peak_to_trough_dd_r"])

summary=pd.DataFrame([{
 "trades":len(z),"wr":(z.outcome=="WIN").mean()*100,"expectancy_r":z.result_r.mean(),
 "overall_max_dd_r":overall_dd,"max_losing_streak":max_streak,
 "worst_daily_dd_r":d.peak_to_trough_dd_r.max(),"avg_daily_dd_r":d.peak_to_trough_dd_r.mean(),
 "worst_day_net_r":d.net_r.min(),"best_day_net_r":d.net_r.max(),
 "avg_trades_per_active_day":d.trades.mean()
}])
summary.to_csv(OUTFILE,index=False)
print("\n=== V4 FOUR-SESSION RISK DIAGNOSTIC — 4R ===")
print(summary.round(2).to_string(index=False))
print("\nDaily DD distribution (R):")
print(d.peak_to_trough_dd_r.describe(percentiles=[.5,.75,.9,.95,.99]).round(2).to_string())
print("\nSaved:",OUTFILE)
