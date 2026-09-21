import pandas as pd
import numpy as np

ONE="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
RULES="data/v6_walkforward_shortlist.csv"
OUT="data/v6_full_universe_validation.csv"
RR=4.0
STOP_BUFFER=.25

one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); rules=pd.read_csv(RULES).drop_duplicates("rule")
one["time_ny"]=pd.to_datetime(one.time_ny); cand["time_ny"]=pd.to_datetime(cand.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True); cand=cand.sort_values("time_ny").reset_index(drop=True)

end=one.time_ny.max(); start=end-pd.Timedelta(days=365)
one=one[one.time_ny>=start-pd.Timedelta(days=2)].reset_index(drop=True)
cand=cand[cand.time_ny>=start].drop_duplicates(["time_ny","session","direction"]).reset_index(drop=True)
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)

# Only the strongest higher-coverage finalists from the 121-trade discovery set.
rules=rules[(rules.worst_fold_wr>=55)&(rules.trades>=50)].head(25).copy()
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

def outcome(c,i,k):
    # Feature mK is only known after that 1m bar closes; enter next 1m open.
    j=i+k+1
    if j>=len(one) or one.iloc[j].ticker!=c.ticker:return None
    signal=one.iloc[j].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time:return None
    entry=float(one.iloc[j].open)
    stop=float(c.extreme)-STOP_BUFFER if c.direction=="LONG" else float(c.extreme)+STOP_BUFFER
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0:return None
    target=entry+RR*risk if c.direction=="LONG" else entry-RR*risk
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=c.ticker:break
        sh=b.low<=stop if c.direction=="LONG" else b.high>=stop
        th=b.high>=target if c.direction=="LONG" else b.low<=target
        if sh:return "LOSS"
        if th:return "WIN"
    return None

rows=[]
for n,c in cand.iterrows():
    if (n+1)%2000==0:print(f"Building causal features/outcomes {n+1:,}/{len(cand):,}",flush=True)
    i=idx.get(c.time_ny)
    if i is None or i<20 or i+4>=len(one):continue
    if one.iloc[i].ticker!=c.ticker:continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:continue
    sg=1 if c.direction=="LONG" else -1
    v={"candidate_time":c.time_ny,"session":c.session,"direction":c.direction}
    good=True
    for k in [1,2,3]:
        b=one.iloc[i+k]
        if b.ticker!=c.ticker:good=False;break
        pre=one.iloc[max(0,i+k-5):i+k+1]
        v[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        v[f"m{k}_body_atr"]=abs(float(b.close-b.open))/a
        cp=((b.close-b.low)/(b.high-b.low) if b.high>b.low else .5)
        v[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        v[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
        v[f"outcome_m{k}"]=outcome(c,i,k)
    if good:rows.append(v)

d=pd.DataFrame(rows)
print(f"\nFull 365d unique reversal candidates with causal features: {len(d):,}")

def mask_rule(df,rule):
    m=np.ones(len(df),dtype=bool)
    maxk=1
    for part in rule.split(" & "):
        if "<=" in part:f,val=part.split("<=");m &= df[f].to_numpy()<=float(val)
        else:f,val=part.split(">=");m &= df[f].to_numpy()>=float(val)
        if f.startswith("m"):maxk=max(maxk,int(f[1]))
    return m,maxk

res=[]
for _,r in rules.iterrows():
    m,k=mask_rule(d,r.rule); q=d[m].copy(); q=q[q[f"outcome_m{k}"].isin(["WIN","LOSS"])]
    if q.empty:continue
    # Chronological 70/30 split is independent of the 121-trade rule discovery scoring.
    cut=q.candidate_time.quantile(.70); tr=q[q.candidate_time<=cut]; te=q[q.candidate_time>cut]
    tw=100*(tr[f"outcome_m{k}"]=="WIN").mean(); ew=100*(te[f"outcome_m{k}"]=="WIN").mean(); aw=100*(q[f"outcome_m{k}"]=="WIN").mean()
    days=max(1,(q.candidate_time.max()-q.candidate_time.min()).days)
    exp=(aw/100)*RR-(1-aw/100)
    res.append((r.rule,k,len(q),aw,len(q)/days,len(tr),tw,len(te),ew,min(tw,ew),exp))
o=pd.DataFrame(res,columns=["rule","entry_after_minute","trades","wr","trades_per_day","train_trades","train_wr","test_trades","test_wr","robust_wr","expectancy_r"])
o=o.sort_values(["robust_wr","test_trades"],ascending=[False,False]);o.to_csv(OUT,index=False)
print("\n=== REAL FULL-UNIVERSE 365D CAUSAL VALIDATION ===")
print(o.head(25).round(2).to_string(index=False))
print("\n50%+ BOTH train/test:",int(((o.train_wr>=50)&(o.test_wr>=50)).sum()))
print("55%+ BOTH train/test:",int(((o.train_wr>=55)&(o.test_wr>=55)).sum()))
print("\nSaved:",OUT)
