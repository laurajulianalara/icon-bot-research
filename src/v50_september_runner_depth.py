import pandas as pd
import numpy as np

BASE="data/v27_option2a_trades.csv"
NEW="data/sep18_sep21_option2a_all_sessions.csv"

base=pd.read_csv(BASE)
new=pd.read_csv(NEW)
time_col=next(c for c in ["entry_time","signal_time","time_ny","candidate_time"] if c in base.columns)
base[time_col]=pd.to_datetime(base[time_col],utc=True).dt.tz_convert("America/New_York")
sep=base[(base[time_col].dt.year==2026)&(base[time_col].dt.month==9)&(base[time_col].dt.day<=17)].copy()

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
one["time_ny"]=pd.to_datetime(one["time_ny"]); cand["time_ny"]=pd.to_datetime(cand["time_ny"])
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
idx1=pd.Series(one.index,index=one.time_ny).to_dict()
sep=sep.rename(columns={time_col:"entry_time"})
cm=cand[["time_ny","session","direction","ticker","extreme","next_same_extreme_time"]]
sep=sep.merge(cm,left_on=["entry_time","session","direction"],right_on=["time_ny","session","direction"],how="left")

def maxr(r):
 i=idx1.get(r.time_ny)
 if i is None:return np.nan
 j=i+3
 if j>=len(one) or one.iloc[j].ticker!=r.ticker:return np.nan
 e=float(one.iloc[j].open); st=float(r.extreme)-.25 if r.direction=="LONG" else float(r.extreme)+.25
 risk=e-st if r.direction=="LONG" else st-e
 if risk<=0:return np.nan
 m=0.
 for z in range(j,min(j+241,len(one))):
  b=one.iloc[z]
  if b.ticker!=r.ticker:break
  if (b.low<=st if r.direction=="LONG" else b.high>=st):break
  fav=(float(b.high)-e)/risk if r.direction=="LONG" else (e-float(b.low))/risk
  m=max(m,fav)
 return m

sep["max_rr"]=sep.apply(maxr,axis=1)
new["entry_time"]=pd.to_datetime(new["entry_time"],utc=True).dt.tz_convert("America/New_York")
alltr=pd.concat([sep[["entry_time","session","max_rr"]],new[["entry_time","session","max_rr"]]],ignore_index=True)
print("\n=== SEPTEMBER RUNNER DEPTH — 56 TRADES THROUGH SEP 21 ===")
for rr in [8,10,15,20,25]:
 n=int((alltr.max_rr>=rr).sum())
 print(f"{rr}R+: {n}/56 = {100*n/56:.2f}%")
print("\nBY SESSION")
for s,g in alltr.groupby(alltr.session.astype(str).str.upper()):
 print(s, "|", len(g), "trades", "|", " | ".join(f"{rr}R+ {int((g.max_rr>=rr).sum())}" for rr in [8,10,15,20,25]))
