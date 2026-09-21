import pandas as pd

ONE="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
LOCKED="data/v27_option2a_trades.csv"
FRIDAY="data/sep18_option2a.csv"

one=pd.read_parquet(ONE)
cand=pd.read_parquet(CAND)
locked=pd.read_csv(LOCKED)
fri=pd.read_csv(FRIDAY)

one["time_ny"]=pd.to_datetime(one["time_ny"])
cand["time_ny"]=pd.to_datetime(cand["time_ny"])
locked["candidate_time"]=pd.to_datetime(locked["candidate_time"])
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
idx=pd.Series(one.index,index=one.time_ny).to_dict()
cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}

def replay(row,rr):
    c=cm.get((row.candidate_time,str(row.direction)))
    if c is None: return "MISSING"
    i=idx.get(c.time_ny)
    if i is None or i+3>=len(one): return "MISSING"
    j=i+3
    if one.iloc[j].ticker!=c.ticker: return "MISSING"
    signal=one.iloc[j].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time: return "MISSING"
    entry=float(one.iloc[j].open)
    stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0: return "MISSING"
    target=entry+rr*risk if c.direction=="LONG" else entry-rr*risk
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=c.ticker: break
        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
        th=b.high>=target if c.direction=="LONG" else b.low<=target
        if sh: return "LOSS"
        if th: return "WIN"
    return "UNRESOLVED"

start=pd.Timestamp("2026-09-14",tz="America/New_York")
end=pd.Timestamp("2026-09-18",tz="America/New_York")
hist=locked[(locked.candidate_time>=start)&(locked.candidate_time<end)].copy()

rows=[]
for day in pd.date_range("2026-09-14","2026-09-18",freq="D"):
    daydate=day.date()
    if daydate < pd.Timestamp("2026-09-18").date():
        q=hist[hist.candidate_time.dt.date==daydate]
        for rr in range(1,5):
            results=[replay(r,rr) for _,r in q.iterrows()]
            results=[x for x in results if x in ("WIN","LOSS")]
            n=len(results); w=results.count("WIN")
            rows.append({"date":day.strftime("%a Sep %d"),"rr":f"1:{rr}","trades":n,"wins":w,"wr_pct":100*w/n if n else None})
    else:
        n=len(fri)
        for rr in range(1,5):
            w=int((fri["max_rr"]>=rr).sum())
            rows.append({"date":day.strftime("%a Sep %d"),"rr":f"1:{rr}","trades":n,"wins":w,"wr_pct":100*w/n if n else None})

out=pd.DataFrame(rows)
print("\n=== OPTION 2A — SEPT 14–18 DAILY WR ===")
pivot=out.pivot(index="date",columns="rr",values="wr_pct").reindex(columns=["1:1","1:2","1:3","1:4"])
counts=out.groupby("date").trades.first()
for d in pivot.index:
    vals=pivot.loc[d]
    print(f"{d} | {int(counts[d])} trades | "+" | ".join(f"{rr} {vals[rr]:.2f}%" if pd.notna(vals[rr]) else f"{rr} —" for rr in pivot.columns))
print("\nWEEK TOTAL")
for rr in ["1:1","1:2","1:3","1:4"]:
    q=out[out.rr==rr]
    wins=int(q.wins.sum()); trades=int(q.trades.sum())
    print(f"{rr}: {wins}/{trades} = {100*wins/trades:.2f}%")
out.to_csv("data/sep14_18_option2a_daily_wr.csv",index=False)
print("Saved: data/sep14_18_option2a_daily_wr.csv")
