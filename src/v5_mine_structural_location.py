import pandas as pd
import numpy as np

IN="data/v5_winner_mining_features.parquet"
ONE="data/mnq_continuous_1m.parquet"
OUT="data/v5_structural_location_features.parquet"
SUMMARY="data/v5_structural_winner_vs_loser.csv"

x=pd.read_parquet(IN); one=pd.read_parquet(ONE)
x["candidate_time"]=pd.to_datetime(x.candidate_time); one["time_ny"]=pd.to_datetime(one.time_ny)
one=one.sort_values("time_ny").reset_index(drop=True)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()
rows=[]
for n,r in x.iterrows():
    if (n+1)%1000==0:print(f"Structure {n+1:,}/{len(x):,}",flush=True)
    i=idx.get(r.candidate_time)
    if i is None or i<65:continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:continue
    b=one.iloc[i]; pre=one.iloc[i-60:i]; p5=one.iloc[i-5:i]; p15=one.iloc[i-15:i]
    islong=r.direction=="LONG"; ex=float(b.low if islong else b.high)
    # Structural S/R from confirmed prior swing points only
    lows=pre.low.to_numpy(); highs=pre.high.to_numpy()
    pivlo=[lows[k] for k in range(2,len(lows)-2) if lows[k]<=min(lows[k-2:k+3])]
    pivhi=[highs[k] for k in range(2,len(highs)-2) if highs[k]>=max(highs[k-2:k+3])]
    piv=np.array(pivlo if islong else pivhi,dtype=float)
    sr_dist=float(np.min(np.abs(piv-ex))/a) if len(piv) else np.nan
    sr_touches=int(np.sum(np.abs(piv-ex)<=.25*a)) if len(piv) else 0
    # Equal-liquidity clusters near candidate
    liq_dist=sr_dist
    eq_cluster=int(np.sum(np.abs(piv-ex)<=.15*a)) if len(piv) else 0
    # Sweep/reclaim of most recent prior swing
    recent=piv[-1] if len(piv) else np.nan
    swept=(ex<recent if islong else ex>recent) if np.isfinite(recent) else False
    sweep_depth=abs(ex-recent)/a if swept else 0.
    rng=max(float(b.high-b.low),1e-9)
    reclaim=((b.close-recent)/a if islong else (recent-b.close)/a) if swept else np.nan
    # Failed continuation: progress in final 3m versus prior 12m directional travel
    p12=one.iloc[i-12:i-3]
    old=float(p12.low.min() if islong else p12.high.max())
    final_progress=max(0,(old-ex)/a if islong else (ex-old)/a)
    travel=abs(float(p15.close.iloc[-1]-p15.close.iloc[0]))/a
    progress_ratio=final_progress/max(travel,.05)
    # Exhaustion / compression / expansion into extreme
    range5=float((p5.high-p5.low).mean()/a); range15=float((p15.high-p15.low).mean()/a)
    compression=range5/max(range15,.01)
    directional5=int((((p5.close-p5.open)<0) if islong else ((p5.close-p5.open)>0)).sum())
    # Position in 60m structure: 0=edge low,1=edge high; convert so 1=at reversal-side edge
    lo=float(pre.low.min()); hi=float(pre.high.max()); pos=(ex-lo)/max(hi-lo,1e-9)
    edge_pos=(1-pos) if islong else pos
    # Distance stretched from 20m mean and VWAP-like typical-price mean (no volume)
    mean20=float(one.iloc[i-20:i].close.mean())
    stretch=abs(ex-mean20)/a
    rows.append({**r.to_dict(),"sr_dist_atr2":sr_dist,"sr_touch_cluster":sr_touches,"equal_liq_cluster":eq_cluster,
        "swept_prior_swing":int(swept),"sweep_depth2_atr":sweep_depth,"reclaim_prior_swing_atr":reclaim,
        "failed_cont_progress_atr":final_progress,"progress_vs_travel":progress_ratio,
        "approach_compression":compression,"approach_directional5":directional5,
        "structure_edge_pos":edge_pos,"stretch20_atr":stretch})
d=pd.DataFrame(rows);d.to_parquet(OUT,index=False)
features=["sr_dist_atr2","sr_touch_cluster","equal_liq_cluster","swept_prior_swing","sweep_depth2_atr",
"reclaim_prior_swing_atr","failed_cont_progress_atr","progress_vs_travel","approach_compression",
"approach_directional5","structure_edge_pos","stretch20_atr"]
res=[]
for f in features:
    w=d.loc[d.outcome=="WIN",f].dropna();l=d.loc[d.outcome=="LOSS",f].dropna()
    pooled=np.sqrt((w.var()+l.var())/2); eff=(w.mean()-l.mean())/pooled if pooled>0 else 0
    res.append((f,w.mean(),l.mean(),w.median(),l.median(),eff,abs(eff)))
s=pd.DataFrame(res,columns=["feature","winner_mean","loser_mean","winner_median","loser_median","effect_size","abs_effect"]).sort_values("abs_effect",ascending=False)
s.to_csv(SUMMARY,index=False)
print("\n=== STRUCTURAL/LOCATION WINNER vs LOSER DIFFERENCES ===")
print(s.drop(columns="abs_effect").round(3).to_string(index=False))
print("\nSaved:",OUT);print("Saved:",SUMMARY)
print("\nNEXT: interaction scan on these structural features + existing CISD/timing features with chronological validation.")
