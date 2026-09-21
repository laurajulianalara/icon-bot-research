import pandas as pd, numpy as np

ONE="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
LOCKED="data/v27_option2a_trades.csv"
RRS=[1,2,3,4,5,6]

one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); locked=pd.read_csv(LOCKED)
one["time_ny"]=pd.to_datetime(one["time_ny"]); cand["time_ny"]=pd.to_datetime(cand["time_ny"])
locked["candidate_time"]=pd.to_datetime(locked["candidate_time"])
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
idx=pd.Series(one.index,index=one.time_ny).to_dict()
cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}

def replay(row,rr):
    c=cm.get((row.candidate_time,str(row.direction)))
    if c is None:return "MISSING"
    i=idx.get(c.time_ny)
    if i is None or i+3>=len(one):return "MISSING"
    j=i+3
    if one.iloc[j].ticker!=c.ticker:return "MISSING"
    signal=one.iloc[j].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time:return "MISSING"
    entry=float(one.iloc[j].open)
    stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return "MISSING"
    target=entry+rr*risk if c.direction=="LONG" else entry-rr*risk
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=c.ticker:break
        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
        th=b.high>=target if c.direction=="LONG" else b.low<=target
        if sh:return "LOSS"
        if th:return "WIN"
    return "UNRESOLVED"

locked["month"]=locked.candidate_time.dt.strftime("%Y-%m")
detail=[]
for rr in RRS:
    oc=locked.apply(lambda r:replay(r,rr),axis=1)
    tmp=locked[["candidate_time","month"]].copy();tmp["rr"]=rr;tmp["result"]=oc
    detail.append(tmp)
d=pd.concat(detail,ignore_index=True)
good=d[d.result.isin(["WIN","LOSS"])]
monthly=good.groupby(["month","rr"]).result.agg(trades="size",wins=lambda x:(x=="WIN").sum(),losses=lambda x:(x=="LOSS").sum()).reset_index()
monthly["wr_pct"]=100*monthly.wins/monthly.trades
monthly["expectancy_r"]=(monthly.wins*monthly.rr-monthly.losses)/monthly.trades
pivot=monthly.pivot(index="month",columns="rr",values="wr_pct")
pivot.columns=[f"{int(c)}R_WR" for c in pivot.columns]
print("=== OPTION 2A MONTHLY WIN RATE BY FIXED RR ===")
print(pivot.round(2).to_string())
print("\n=== MONTHLY TRADE COUNTS / WINS BY RR ===")
for m in monthly.month.unique():
    q=monthly[monthly.month==m]
    vals=" | ".join(f"{int(r.rr)}R {int(r.wins)}/{int(r.trades)} = {r.wr_pct:.2f}%" for _,r in q.iterrows())
    print(m, vals)

# Exact 4R parity check
r4=good[good.rr==4]
parity=((r4.result=="WIN").sum()==(locked.outcome=="WIN").sum() and (r4.result=="LOSS").sum()==(locked.outcome=="LOSS").sum() and len(r4)==len(locked))
print("\n4R FULL-SAMPLE PARITY:",parity)
if not parity: raise RuntimeError("4R parity failed — do not use monthly table.")
monthly.to_csv("data/v37_option2a_monthly_rr_1_to_6.csv",index=False)
print("Saved: data/v37_option2a_monthly_rr_1_to_6.csv")
