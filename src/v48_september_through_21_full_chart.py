import pandas as pd
import numpy as np

BASE = "data/v27_option2a_trades.csv"
NEW = "data/sep18_sep21_option2a_all_sessions.csv"
RISK_DOLLARS = 300

base = pd.read_csv(BASE)
new = pd.read_csv(NEW)

# Locked historical Option 2A through Sep 17
time_col = next(c for c in ["entry_time","signal_time","time_ny","candidate_time"] if c in base.columns)
base[time_col] = pd.to_datetime(base[time_col], utc=True).dt.tz_convert("America/New_York")
sep = base[(base[time_col].dt.year == 2026) & (base[time_col].dt.month == 9) &
           (base[time_col].dt.day <= 17)].copy()

# Use canonical max-R column already stored in locked trade file if present.
# V27 has locked 4R outcomes but no max-R column. Replay exact lower RR from 1m.
one = pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand = pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
one["time_ny"] = pd.to_datetime(one["time_ny"])
cand["time_ny"] = pd.to_datetime(cand["time_ny"])
cand["next_same_extreme_time"] = cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
idx1 = pd.Series(one.index,index=one.time_ny).to_dict()
sep = sep.rename(columns={time_col:"entry_time"})
cm = cand[["time_ny","session","direction","ticker","extreme","next_same_extreme_time"]]
sep = sep.merge(cm,left_on=["entry_time","session","direction"],right_on=["time_ny","session","direction"],how="left")
def replay_maxr(r):
    i=idx1.get(r.time_ny)
    if i is None:return np.nan
    j=i+3
    entry=float(one.iloc[j].open)
    stop=float(r.extreme)-.25 if r.direction=="LONG" else float(r.extreme)+.25
    risk=entry-stop if r.direction=="LONG" else stop-entry
    if risk<=0:return np.nan
    m=0.0
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=r.ticker:break
        sh=b.low<=stop if r.direction=="LONG" else b.high>=stop
        if sh:break
        fav=(float(b.high)-entry)/risk if r.direction=="LONG" else (entry-float(b.low))/risk
        m=max(m,fav)
    return m
sep["max_rr"]=sep.apply(replay_maxr,axis=1)
sep["date"] = sep["entry_time"].dt.date

new["entry_time"] = pd.to_datetime(new["entry_time"], utc=True).dt.tz_convert("America/New_York")
new["date"] = new["entry_time"].dt.date
keep = ["date","entry_time","max_rr"]
alltr = pd.concat([sep[keep], new[keep]], ignore_index=True).sort_values("entry_time")

print("\n=== SEPTEMBER 2026 OPTION 2A — THROUGH SEP 21 ===")
print("Risk: $300/trade")
print()
print(f"{'DATE':<12}{'TRADES':>7}  {'1:1 W/L WR P&L':<25}{'1:2 W/L WR P&L':<25}{'1:3 W/L WR P&L':<25}{'1:4 W/L WR P&L':<25}")
print("-"*120)

for d,g in alltr.groupby("date"):
    parts=[]
    for rr in range(1,7):
        w=int((g.max_rr>=rr).sum()); l=len(g)-w
        wr=100*w/len(g)
        pnl=w*(rr*RISK_DOLLARS)-l*RISK_DOLLARS
        parts.append(f"{w}W/{l}L {wr:5.1f}% ${pnl:+,.0f}")
    print(f"{pd.Timestamp(d).strftime('%b %d'):<12}{len(g):>7}  " + "".join(f"{p:<25}" for p in parts))

print("-"*120)
print(f"TOTAL TRADES: {len(alltr)}")
for rr in range(1,7):
    w=int((alltr.max_rr>=rr).sum()); l=len(alltr)-w
    wr=100*w/len(alltr)
    pnl=w*(rr*RISK_DOLLARS)-l*RISK_DOLLARS
    print(f"1:{rr} | {w}W/{l}L | WR {wr:.2f}% | P&L {pnl:+,.0f} USD")
