import pandas as pd
import numpy as np

BASE="data/v27_option2a_trades.csv"
NEW="data/sep18_sep21_option2a_all_sessions.csv"
RISK_DOLLARS=300

base=pd.read_csv(BASE)
new=pd.read_csv(NEW)
time_col=next(c for c in ["entry_time","signal_time","time_ny","candidate_time"] if c in base.columns)
base[time_col]=pd.to_datetime(base[time_col],utc=True).dt.tz_convert("America/New_York")
sep=base[(base[time_col].dt.year==2026)&(base[time_col].dt.month==9)&(base[time_col].dt.day<=17)].copy()

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
one["time_ny"]=pd.to_datetime(one["time_ny"])
cand["time_ny"]=pd.to_datetime(cand["time_ny"])
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
idx1=pd.Series(one.index,index=one.time_ny).to_dict()
sep=sep.rename(columns={time_col:"entry_time"})
cm=cand[["time_ny","session","direction","ticker","extreme","next_same_extreme_time"]]
sep=sep.merge(cm,left_on=["entry_time","session","direction"],right_on=["time_ny","session","direction"],how="left")

def replay_maxr(r):
    i=idx1.get(r.time_ny)
    if i is None:return np.nan
    j=i+3
    if j>=len(one) or one.iloc[j].ticker!=r.ticker:return np.nan
    entry=float(one.iloc[j].open)
    stop=float(r.extreme)-.25 if r.direction=="LONG" else float(r.extreme)+.25
    risk=entry-stop if r.direction=="LONG" else stop-entry
    if risk<=0:return np.nan
    m=0.0
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=r.ticker:break
        stop_hit=b.low<=stop if r.direction=="LONG" else b.high>=stop
        if stop_hit:break
        fav=(float(b.high)-entry)/risk if r.direction=="LONG" else (entry-float(b.low))/risk
        m=max(m,fav)
    return m

sep["max_rr"]=sep.apply(replay_maxr,axis=1)
new["entry_time"]=pd.to_datetime(new["entry_time"],utc=True).dt.tz_convert("America/New_York")
keep=["entry_time","session","max_rr"]
alltr=pd.concat([sep[keep],new[keep]],ignore_index=True).sort_values("entry_time")
alltr["session"]=alltr["session"].astype(str).str.upper()

order=["ASIA","LONDON","NYAM","NYPM"]
print("\n=== SEPTEMBER 2026 OPTION 2A — BY SESSION THROUGH SEP 21 ===")
print("Risk: $300/trade\n")
print(f"{'SESSION':<10}{'TRADES':>7}{'AVG MAX RR':>13}  "+ "".join(f"{'1:'+str(rr)+' WR':>10}" for rr in range(1,7)))
print("-"*92)
for s in order:
    g=alltr[alltr.session==s]
    if len(g)==0:continue
    vals=[]
    for rr in range(1,7):
        w=int((g.max_rr>=rr).sum())
        vals.append(f"{100*w/len(g):9.2f}%")
    print(f"{s:<10}{len(g):>7}{g.max_rr.mean():>13.2f}  "+ "".join(vals))

print("\n=== FULL SESSION DETAIL — W/L, WR, P&L ===")
for s in order:
    g=alltr[alltr.session==s]
    if len(g)==0:continue
    print(f"\n{s} | {len(g)} trades | Avg max RR {g.max_rr.mean():.2f}R")
    for rr in range(1,7):
        w=int((g.max_rr>=rr).sum()); l=len(g)-w
        wr=100*w/len(g)
        pnl=w*(rr*RISK_DOLLARS)-l*RISK_DOLLARS
        print(f"1:{rr} | {w}W/{l}L | WR {wr:.2f}% | P&L {pnl:+,.0f} USD")
