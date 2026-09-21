import pandas as pd
import numpy as np

IN="data/v8_volatility_forensics.csv"; OUT="data/v10_daily_cluster_context.csv"
q=pd.read_csv(IN);q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True)
q=q.sort_values("candidate_time").reset_index(drop=True);q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
q["ny"]=q.candidate_time.dt.tz_convert("America/New_York");q["date"]=q.ny.dt.date;q["hour"]=q.ny.dt.hour

# Sequential context available BEFORE each trade.
q["prior_trade_r"]=q.r.shift(1);q["prior_win"]=q.win.shift(1)
q["prior2_losses"]=((q.win.shift(1)==0)&(q.win.shift(2)==0)).astype(int)
q["prior3_losses"]=((q.win.shift(1)==0)&(q.win.shift(2)==0)&(q.win.shift(3)==0)).astype(int)
q["day_trade_num"]=q.groupby("date").cumcount()+1
q["day_prior_losses"]=q.groupby("date").win.transform(lambda s:(1-s).cumsum().shift(fill_value=0))
q["day_prior_wins"]=q.groupby("date").win.transform(lambda s:s.cumsum().shift(fill_value=0))
q["day_prior_r"]=q.groupby("date").r.transform(lambda s:s.cumsum().shift(fill_value=0))
q["same_session_num"]=q.groupby(["date","session"]).cumcount()+1

# Label streak losses only for diagnosis.
run=(q.win==1).cumsum();sz=q.assign(loss=1-q.win).groupby(run).loss.transform("sum")
q["class"]=np.where(q.win==1,"WIN",np.where(sz>=3,"STREAK_LOSS","NORMAL_LOSS"))

print("=== SEQUENTIAL / DAILY CONTEXT DEEP DIVE ===")
for f in ["day_trade_num","day_prior_losses","day_prior_wins","day_prior_r","same_session_num","prior2_losses","prior3_losses"]:
 print("\n",f);print(q.groupby("class")[f].agg(["count","mean","median"]).round(3).to_string())

print("\n=== WR BY TRADE NUMBER IN DAY ===")
print(q.groupby("day_trade_num").agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()),avg_r=("r","mean")).round(2).to_string())
print("\n=== WR AFTER PRIOR LOSSES THAT DAY ===")
print(q.groupby("day_prior_losses").agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()),avg_r=("r","mean")).round(2).to_string())
print("\n=== WR BY SAME-SESSION ATTEMPT NUMBER ===")
print(q.groupby("same_session_num").agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()),avg_r=("r","mean")).round(2).to_string())

# Daily realized results / worst dates.
daily=q.groupby("date").agg(trades=("win","size"),wins=("win","sum"),net_r=("r","sum"))
daily["losses"]=daily.trades-daily.wins
print("\n=== WORST DAILY CLOSES ===");print(daily.sort_values("net_r").head(20).to_string())

q.to_csv(OUT,index=False)
print("\nSaved:",OUT)
