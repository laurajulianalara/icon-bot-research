import pandas as pd
import numpy as np

TRADES="data/v27_option2a_trades.csv"
RISK=300

df=pd.read_csv(TRADES)
tc=next(c for c in ["entry_time","signal_time","time_ny","candidate_time"] if c in df.columns)
df[tc]=pd.to_datetime(df[tc],utc=True).dt.tz_convert("America/New_York")
# Locked Option2A outcome is the canonical 4R result; replay exact 1R from 1m path.
one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
one["time_ny"]=pd.to_datetime(one["time_ny"]); cand["time_ny"]=pd.to_datetime(cand["time_ny"])
idx=pd.Series(one.index,index=one.time_ny).to_dict()
df=df.rename(columns={tc:"candidate_time"})
cm=cand[["time_ny","session","direction","ticker","extreme"]]
df=df.merge(cm,left_on=["candidate_time","session","direction"],right_on=["time_ny","session","direction"],how="left")

def hit1(r):
 i=idx.get(r.time_ny)
 if i is None:return np.nan
 j=i+3
 if j>=len(one) or one.iloc[j].ticker!=r.ticker:return np.nan
 e=float(one.iloc[j].open); st=float(r.extreme)-.25 if r.direction=="LONG" else float(r.extreme)+.25
 risk=e-st if r.direction=="LONG" else st-e
 if risk<=0:return np.nan
 tp=e+risk if r.direction=="LONG" else e-risk
 for z in range(j,min(j+241,len(one))):
  b=one.iloc[z]
  if b.ticker!=r.ticker:break
  sh=b.low<=st if r.direction=="LONG" else b.high>=st
  th=b.high>=tp if r.direction=="LONG" else b.low<=tp
  if sh:return 0
  if th:return 1
 return np.nan

df["win1"]=df.apply(hit1,axis=1)
df=df[df.win1.notna()].copy()
df["pnl"]=np.where(df.win1==1,RISK,-RISK)
df["date"]=df.candidate_time.dt.date
df["month"]=df.candidate_time.dt.to_period("M").astype(str)

daily=df.groupby("date").agg(trades=("win1","size"),wins=("win1","sum"),pnl=("pnl","sum"))
daily["losses"]=daily.trades-daily.wins
daily["wr"]=100*daily.wins/daily.trades

monthly=df.groupby("month").agg(trades=("win1","size"),wins=("win1","sum"),pnl=("pnl","sum"))
monthly["losses"]=monthly.trades-monthly.wins
monthly["wr"]=100*monthly.wins/monthly.trades

losing=daily[daily.pnl<0]
flat=daily[daily.pnl==0]
winning=daily[daily.pnl>0]
# consecutive losing days among chronological ACTIVE days
max_streak=cur=0
for x in (daily.pnl<0):
 cur=cur+1 if x else 0
 max_streak=max(max_streak,cur)

print("\n=== OPTION 2A — FULL HISTORY — 1:1 FUNDED MODEL ===")
print(f"Trades: {len(df)} | Wins: {int(df.win1.sum())} | Losses: {int((df.win1==0).sum())} | WR: {100*df.win1.mean():.2f}%")
print(f"Active trading days: {len(daily)}")
print(f"Winning days: {len(winning)} ({100*len(winning)/len(daily):.2f}%)")
print(f"Flat days: {len(flat)} ({100*len(flat)/len(daily):.2f}%)")
print(f"Losing days: {len(losing)} ({100*len(losing)/len(daily):.2f}%)")
print(f"Worst day: {daily.pnl.min():+,.0f} USD")
print(f"Best day: {daily.pnl.max():+,.0f} USD")
print(f"Average active-day P&L: {daily.pnl.mean():+,.2f} USD")
print(f"Median active-day P&L: {daily.pnl.median():+,.2f} USD")
print(f"Max consecutive losing active days: {max_streak}")
print(f"Total P&L at $300 risk: {daily.pnl.sum():+,.0f} USD")

print("\n=== MONTHLY ===")
for m,r in monthly.iterrows():
 print(f"{m} | {int(r.trades)} trades | {int(r.wins)}W/{int(r.losses)}L | WR {r.wr:.2f}% | P&L {r.pnl:+,.0f}")

print("\n=== LOSING DAYS ===")
if losing.empty: print("NONE")
else:
 for d,r in losing.iterrows():
  print(f"{d} | {int(r.trades)} trades | {int(r.wins)}W/{int(r.losses)}L | P&L {r.pnl:+,.0f}")

print("\n=== DAILY P&L DISTRIBUTION ===")
for pnl,n in daily.pnl.value_counts().sort_index().items():
 print(f"{pnl:+,.0f} USD: {n} days ({100*n/len(daily):.2f}%)")
