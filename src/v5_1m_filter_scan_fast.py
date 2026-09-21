import pandas as pd
import numpy as np
from itertools import product

DATA="data/mnq_continuous_1m.parquet"; CAND="data/reversal_candidates.parquet"
CACHE="data/v5_1m_filter_cache.parquet"; OUT="data/v5_1m_filter_scan_fast.csv"; RR=4.0
one=pd.read_parquet(DATA); cand=pd.read_parquet(CAND)
one["time_ny"]=pd.to_datetime(one.time_ny); cand["time_ny"]=pd.to_datetime(cand.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True); cand=cand.sort_values("time_ny").reset_index(drop=True)
end=one.time_ny.max(); start=end-pd.Timedelta(days=365); split=start+(end-start)*.70
one=one[one.time_ny>=start].reset_index(drop=True); cand=cand[cand.time_ny>=start].reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict(); oi=one.set_index("time_ny")

def confirm(c):
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

def simulate(c,t):
    stop=c.extreme-.25 if c.direction=="LONG" else c.extreme+.25
    z=oi.loc[t:t]; z=z[z.ticker==c.ticker]
    if z.empty:return None
    entry=float(z.iloc[0].open); risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return None
    target=entry+RR*risk if c.direction=="LONG" else entry-RR*risk
    td=oi.loc[t:t+pd.Timedelta(hours=4)]; td=td[td.ticker==c.ticker]
    for ts,b in td.iterrows():
        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
        th=b.high>=target if c.direction=="LONG" else b.low<=target
        if sh:return ts,"LOSS",-1.
        if th:return ts,"WIN",RR
    return None

rows=[]
for n,(_,c) in enumerate(cand.iterrows(),1):
    if n%2000==0:print(f"Candidate {n:,}/{len(cand):,}")
    cf=confirm(c)
    if not cf:continue
    t,cp,dp,mn=cf; tr=simulate(c,t)
    if not tr:continue
    xt,out,rv=tr; a=float(c.atr) if pd.notna(c.atr) else np.nan
    rows.append((c.time_ny,t,xt,c.session,out,rv,cp,dp,mn,c.sweep_distance/a if np.isfinite(a) and a>0 else 0))
d=pd.DataFrame(rows,columns=["candidate_time","fill_time","exit_time","session","outcome","result_r","cisd","disp","confirm_minutes","sweep"])
d=d.drop_duplicates(["candidate_time","session"]).sort_values("fill_time").reset_index(drop=True); d.to_parquet(CACHE,index=False)
print(f"Unique resolved candidates: {len(d):,}")

# Fast vectorized scan. No expensive dataframe copies or iterrows inside every combination.
CLO=[None,.40,.50,.55,.60,.65,.70]; CHI=[None,.70,.80,.90,.95]
DLO=[None,.20,.30,.40,.50]; DHI=[None,.60,.80,1.0,1.2]
SMAX=[None,.05,.10,.20,.30,.50]; MINS=[1,2,3]; MAXS=[3,4,5,8,15]
res=[]
sessions=["ALL","ASIA","LONDON","NYAM","NYPM"]
for si,s in enumerate(sessions,1):
    print(f"Scanning {s} ({si}/5)...",flush=True)
    sm=np.ones(len(d),bool) if s=="ALL" else d.session.eq(s).to_numpy()
    train=d.fill_time.lt(split).to_numpy(); win=d.outcome.eq("WIN").to_numpy()
    c=d.cisd.to_numpy(); dp=d.disp.to_numpy(); sw=d.sweep.to_numpy(); mins=d.confirm_minutes.to_numpy()
    for lo,hi,dlo,dhi,sx,mn,mx in product(CLO,CHI,DLO,DHI,SMAX,MINS,MAXS):
        if lo is not None and hi is not None and lo>=hi:continue
        if dlo is not None and dhi is not None and dlo>=dhi:continue
        if mn>mx:continue
        m=sm&(mins>=mn)&(mins<=mx)
        if lo is not None:m&=c>=lo
        if hi is not None:m&=c<hi
        if dlo is not None:m&=dp>=dlo
        if dhi is not None:m&=dp<dhi
        if sx is not None:m&=sw<sx
        mt=m&train; mv=m&~train; nt=mt.sum(); nv=mv.sum()
        if nt<40 or nv<15:continue
        tw=100*win[mt].mean(); vw=100*win[mv].mean()
        res.append((s,lo,hi,dlo,dhi,sx,mn,mx,nt,tw,nv,vw,min(tw,vw)))
r=pd.DataFrame(res,columns=["session","cisd_min","cisd_max","disp_min","disp_max","sweep_max","confirm_min","confirm_max","train_trades","train_wr","valid_trades","valid_wr","robust_wr"])
r=r.sort_values(["robust_wr","valid_trades"],ascending=[False,False]); r.to_csv(OUT,index=False)
print("\n=== FAST 1M CAUSAL FILTER SCAN — TOP 40 ===")
print(r.head(40).round(2).to_string(index=False))
print("\n50%+ BOTH train/validation:",int(((r.train_wr>=50)&(r.valid_wr>=50)).sum()))
print("Saved:",OUT)
