import pandas as pd
import numpy as np

DATA="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
OUT="data/v5_1m_reversal_diagnostic.csv"

one=pd.read_parquet(DATA); cand=pd.read_parquet(CAND)
one["time_ny"]=pd.to_datetime(one.time_ny); cand["time_ny"]=pd.to_datetime(cand.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True); cand=cand.sort_values("time_ny").reset_index(drop=True)
end=one.time_ny.max(); start=end-pd.Timedelta(days=365)
one=one[one.time_ny>=start].reset_index(drop=True); cand=cand[cand.time_ny>=start].reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict(); oi=one.set_index("time_ny")

def conf(c):
    if c.time_ny not in idx:return None
    i=idx[c.time_ny]; ref=c.open; nxt=c.next_same_extreme_time
    for j in range(i+1,min(i+16,len(one))):
        r=one.iloc[j]
        if r.ticker!=c.ticker:return None
        if pd.notna(nxt) and r.time_ny>=nxt:return None
        if c.direction=="LONG" and r.close<r.open:ref=r.open
        elif c.direction=="SHORT" and r.close>r.open:ref=r.open
        ok=(c.direction=="LONG" and r.close>ref) or (c.direction=="SHORT" and r.close<ref)
        if ok:
            a=float(r.atr1)
            if not np.isfinite(a) or a<=0:return None
            cp=(r.close-r.low)/(r.high-r.low) if r.high>r.low else .5
            if c.direction=="SHORT":cp=1-cp
            return r.time_ny+pd.Timedelta(minutes=1),cp,abs(r.close-r.open)/a,j-i
    return None

def sim(c,t,sb=.25):
    stop=c.extreme-sb if c.direction=="LONG" else c.extreme+sb
    z=oi.loc[t:t]; z=z[z.ticker==c.ticker]
    if z.empty:return None
    entry=float(z.iloc[0].open); risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return None
    target=entry+4*risk if c.direction=="LONG" else entry-4*risk
    td=oi.loc[t:t+pd.Timedelta(hours=4)];td=td[td.ticker==c.ticker]
    for ts,b in td.iterrows():
        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
        th=b.high>=target if c.direction=="LONG" else b.low<=target
        if sh:return "LOSS"
        if th:return "WIN"
    return None

rows=[]
for n,(_,c) in enumerate(cand.iterrows(),1):
    if n%2000==0:print(f"Candidate {n:,}/{len(cand):,}")
    q=conf(c)
    if not q:continue
    t,cp,disp,bars=q
    out=sim(c,t)
    if not out:continue
    atr=float(c.atr) if pd.notna(c.atr) else np.nan
    rows.append(dict(candidate_time=c.time_ny,fill_time=t,session=c.session,direction=c.direction,outcome=out,
        cisd=cp,disp=disp,sweep=(c.sweep_distance/atr if np.isfinite(atr) and atr>0 else 0),confirm_minutes=bars,
        rejection=(float(c.wick_percent) if pd.notna(c.wick_percent) else 0)))
d=pd.DataFrame(rows).drop_duplicates(["candidate_time","session","direction"])
print(f"\nResolved unique 1m causal candidates: {len(d):,} | WR={(d.outcome=='WIN').mean()*100:.2f}%")

bins={"cisd":[0,.4,.55,.7,.8,.9,.95,1.01],"disp":[0,.2,.4,.6,.8,1,1.2,1.5,2,999],
"sweep":[-999,0,.05,.1,.2,.3,.5,1,999],"confirm_minutes":[0,1,2,3,5,8,15,999]}
rows=[]
for col,edges in bins.items():
    d["bin"]=pd.cut(d[col],edges,right=False)
    for k,g in d.groupby("bin",observed=True):
        rows.append(dict(feature=col,bin=str(k),trades=len(g),wins=(g.outcome=="WIN").sum(),wr=(g.outcome=="WIN").mean()*100))
for s,g in d.groupby("session"):
    rows.append(dict(feature="session",bin=s,trades=len(g),wins=(g.outcome=="WIN").sum(),wr=(g.outcome=="WIN").mean()*100))
r=pd.DataFrame(rows).sort_values(["feature","wr"],ascending=[True,False])
r.to_csv(OUT,index=False)
print("\n=== WHICH 1M FEATURES ACTUALLY SEPARATE 4R WINNERS? ===")
for f in ["cisd","disp","sweep","confirm_minutes","session"]:
    print("\n",f.upper())
    print(r[r.feature==f].round(2).to_string(index=False))
print("\nSaved:",OUT)
print("\nNEXT: use these distributions to rebuild the fakeout filter for 1-minute data instead of reusing 3-minute thresholds.")
