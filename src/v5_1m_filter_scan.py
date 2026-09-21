import pandas as pd
import numpy as np
from itertools import product

DATA="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
OUT="data/v5_1m_filter_scan.csv"
LOOKBACK=365
RR=4.0

one=pd.read_parquet(DATA); cand=pd.read_parquet(CAND)
one["time_ny"]=pd.to_datetime(one.time_ny); cand["time_ny"]=pd.to_datetime(cand.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True); cand=cand.sort_values("time_ny").reset_index(drop=True)
end=one.time_ny.max(); start=end-pd.Timedelta(days=LOOKBACK); split=start+(end-start)*.70
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
            return dict(signal=r.time_ny+pd.Timedelta(minutes=1),cisd=cp,disp=abs(r.close-r.open)/a,mins=j-i)
    return None

def simulate(c,t):
    sb=.25; stop=c.extreme-sb if c.direction=="LONG" else c.extreme+sb
    z=oi.loc[t:t];z=z[z.ticker==c.ticker]
    if z.empty:return None
    entry=float(z.iloc[0].open); risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return None
    target=entry+RR*risk if c.direction=="LONG" else entry-RR*risk
    td=oi.loc[t:t+pd.Timedelta(hours=4)];td=td[td.ticker==c.ticker]
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
    tr=simulate(c,cf["signal"])
    if not tr:continue
    xt,out,rv=tr
    atr=float(c.atr) if pd.notna(c.atr) else np.nan
    rows.append(dict(candidate_time=c.time_ny,fill_time=cf["signal"],exit_time=xt,session=c.session,direction=c.direction,
        outcome=out,result_r=rv,cisd=cf["cisd"],disp=cf["disp"],confirm_minutes=cf["mins"],
        sweep=(c.sweep_distance/atr if np.isfinite(atr) and atr>0 else 0)))
d=pd.DataFrame(rows).drop_duplicates(["candidate_time","session","direction"]).sort_values("fill_time")
print(f"Unique resolved candidates: {len(d):,}")

CISD=[None,.40,.50,.55,.60,.65,.70,.75,.80,.85,.90,.95]
CISD_MAX=[None,.70,.80,.90,.95]
DISP_MIN=[None,.20,.30,.40,.50,.60,.80]
DISP_MAX=[None,.60,.80,1.0,1.2,1.5]
SWEEP_MAX=[None,.05,.10,.20,.30,.50,1.0]
MIN_MIN=[1,2,3]
MAX_MIN=[3,4,5,8,15]

def one_live(x):
    keep=[]; until=None
    for ix,r in x.sort_values("fill_time").iterrows():
        if until is not None and r.fill_time<=until:continue
        keep.append(ix);until=r.exit_time
    return x.loc[keep]

def met(x):
    x=one_live(x)
    if x.empty:return None
    w=(x.outcome=="WIN").sum();eq=x.result_r.cumsum()
    return len(x),100*w/len(x),x.result_r.mean(),abs((eq-eq.cummax()).min())

res=[]
for session in ["ALL","ASIA","LONDON","NYAM","NYPM"]:
    base=d if session=="ALL" else d[d.session==session]
    for cmin,cmax,dmin,dmax,smax,mn,mx in product(CISD,CISD_MAX,DISP_MIN,DISP_MAX,SWEEP_MAX,MIN_MIN,MAX_MIN):
        if cmin is not None and cmax is not None and cmin>=cmax:continue
        if dmin is not None and dmax is not None and dmin>=dmax:continue
        if mn>mx:continue
        q=base.copy()
        if cmin is not None:q=q[q.cisd>=cmin]
        if cmax is not None:q=q[q.cisd<cmax]
        if dmin is not None:q=q[q.disp>=dmin]
        if dmax is not None:q=q[q.disp<dmax]
        if smax is not None:q=q[q.sweep<smax]
        q=q[(q.confirm_minutes>=mn)&(q.confirm_minutes<=mx)]
        tr=met(q[q.fill_time<split]);va=met(q[q.fill_time>=split])
        if not tr or not va or tr[0]<40 or va[0]<15:continue
        res.append(dict(session=session,cisd_min=cmin,cisd_max=cmax,disp_min=dmin,disp_max=dmax,sweep_max=smax,
            confirm_min=mn,confirm_max=mx,train_trades=tr[0],train_wr=tr[1],train_exp=tr[2],train_dd=tr[3],
            valid_trades=va[0],valid_wr=va[1],valid_exp=va[2],valid_dd=va[3],robust_wr=min(tr[1],va[1])))
r=pd.DataFrame(res)
if r.empty:raise RuntimeError("No combinations met sample minimums.")
r=r.sort_values(["robust_wr","valid_trades"],ascending=[False,False]).reset_index(drop=True)
r.to_csv(OUT,index=False)
print("\n=== 1M CAUSAL FILTER SCAN — TOP 40 ===")
print(r.head(40).round(2).to_string(index=False))
print("\n50%+ BOTH train/validation:",int(((r.train_wr>=50)&(r.valid_wr>=50)).sum()))
print("Saved:",OUT)
print("\nNEXT: inspect robust winners by session, then combine only rules that survive validation.")
