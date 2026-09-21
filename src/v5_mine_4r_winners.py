import pandas as pd
import numpy as np

CACHE="data/v5_1m_filter_cache.parquet"
ONE="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"
OUT="data/v5_winner_mining_features.parquet"
SUMMARY="data/v5_winner_vs_loser_summary.csv"

d=pd.read_parquet(CACHE)
one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND)
for x in (one,cand): x["time_ny"]=pd.to_datetime(x.time_ny)
d["candidate_time"]=pd.to_datetime(d.candidate_time); d["fill_time"]=pd.to_datetime(d.fill_time)
one=one.sort_values("time_ny").reset_index(drop=True)
cand=cand.sort_values("time_ny").drop_duplicates(["time_ny","session"])
cm={(r.time_ny,r.session):r for _,r in cand.iterrows()}
idx=pd.Series(one.index,index=one.time_ny).to_dict()
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
rows=[]
for n,r in d.iterrows():
    if (n+1)%1000==0: print(f"Mining {n+1:,}/{len(d):,}",flush=True)
    c=cm.get((r.candidate_time,r.session))
    if c is None or r.candidate_time not in idx: continue
    i=idx[r.candidate_time]; pre=one.iloc[max(0,i-30):i+1].copy()
    if pre.empty:continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:continue
    direction=1 if c.direction=="LONG" else -1
    # Approach/exhaustion before the extreme
    ret3=(one.iloc[i].close-one.iloc[max(0,i-3)].close)/a*direction
    ret5=(one.iloc[i].close-one.iloc[max(0,i-5)].close)/a*direction
    ret10=(one.iloc[i].close-one.iloc[max(0,i-10)].close)/a*direction
    ranges=(pre.high-pre.low)/a
    bodies=(pre.close-pre.open).abs()/a
    same=((pre.close-pre.open)*direction>0)
    # Rejection at candidate extreme
    b=one.iloc[i]; rng=max(float(b.high-b.low),1e-9)
    rej=((b.close-b.low)/rng if c.direction=="LONG" else (b.high-b.close)/rng)
    # Prior structural reactions: how many prior 30m bars came within .25 ATR of extreme
    ex=float(c.extreme)
    touches=((pre.low-ex).abs()<=.25*a).sum() if c.direction=="LONG" else ((pre.high-ex).abs()<=.25*a).sum()
    # Distance from recent equilibrium/range and session travel proxies
    eq=float(pre.close.mean()); dist_eq=abs(ex-eq)/a
    prange=(float(pre.high.max()-pre.low.min()))/a
    # Failed continuation: last 3 bars made little progress beyond prior 10-bar extreme
    earlier=one.iloc[max(0,i-10):max(0,i-3)]
    if len(earlier):
        oldext=float(earlier.low.min() if c.direction=="LONG" else earlier.high.max())
        progress=abs(ex-oldext)/a
    else: progress=np.nan
    rows.append(dict(candidate_time=r.candidate_time,fill_time=r.fill_time,session=r.session,direction=c.direction,outcome=r.outcome,
        cisd=r.cisd,disp=r.disp,sweep=r.sweep,confirm_minutes=r.confirm_minutes,
        approach3_atr=ret3,approach5_atr=ret5,approach10_atr=ret10,pre30_range_atr=prange,
        pre10_avg_range_atr=float(ranges.tail(10).mean()),pre10_avg_body_atr=float(bodies.tail(10).mean()),
        pre5_directional_bars=int(same.tail(5).sum()),rejection_eff=rej,prior_touch_count=int(touches),
        distance_equilibrium_atr=dist_eq,extreme_progress_atr=progress))
x=pd.DataFrame(rows);x.to_parquet(OUT,index=False)
print(f"\nMined: {len(x):,} | winners={(x.outcome=='WIN').sum():,} | losers={(x.outcome=='LOSS').sum():,}")

features=[c for c in x.columns if c not in ["candidate_time","fill_time","session","direction","outcome"]]
out=[]
for f in features:
    w=x.loc[x.outcome=="WIN",f].dropna();l=x.loc[x.outcome=="LOSS",f].dropna()
    if not len(w) or not len(l):continue
    pooled=np.sqrt((w.var()+l.var())/2); effect=(w.mean()-l.mean())/pooled if pooled>0 else 0
    out.append(dict(feature=f,winner_mean=w.mean(),loser_mean=l.mean(),winner_median=w.median(),loser_median=l.median(),effect_size=effect,abs_effect=abs(effect)))
s=pd.DataFrame(out).sort_values("abs_effect",ascending=False);s.to_csv(SUMMARY,index=False)
print("\n=== WINNERS vs LOSERS — STRONGEST DIFFERENCES ===")
print(s.head(20).drop(columns="abs_effect").round(3).to_string(index=False))
print("\n=== WIN RATE BY SESSION ===")
print(x.groupby("session").outcome.apply(lambda z:pd.Series({"trades":len(z),"wins":(z=="WIN").sum(),"wr":100*(z=="WIN").mean()})).unstack().round(2).to_string())
print("\nSaved:",OUT);print("Saved:",SUMMARY)
print("\nNEXT: mine interactions/combinations of the strongest winner features, then validate them chronologically.")
