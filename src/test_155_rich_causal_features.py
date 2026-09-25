#!/usr/bin/env python3
"""THE ICON — rich causal feature separation study: 155 supersession extras vs 75 valid trades.

FAST / READ ONLY. Uses assembled September cache. No slow replay. No strategy changes.
Reconstructs the actual V7/V8/V15/V27 features using only data known before the
original entry open, then reports feature separation and simple one-feature screens.
It does NOT optimize outcomes or promote a rule.
"""
from pathlib import Path
import sys, bisect
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

PROOF=Path("data/reports/2026-09_original_simulate_extra_proof.csv")
GOOD=Path("data/reports/2026-09_trades.csv")
for p in [PROOF,GOOD,Path(live.HIST)]:
    if not p.exists(): raise RuntimeError(f"Missing {p}")

def et(s):
    x=pd.to_datetime(s,errors="coerce")
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

# Same assembled September source proven to cover 75/75.
hist=pd.read_parquet(live.HIST)[live.NEED].copy(); hist["time_ny"]=et(hist.time_ny)
pieces=[hist[(hist.time_ny.dt.year==2026)&(hist.time_ny.dt.month==9)].copy()]
cache=[]
for fp in sorted(Path("data").glob("mnq_sep*_2026*_1m.parquet")):
    try:
        x=pd.read_parquet(fp)
        if not set(live.NEED).issubset(x.columns): continue
        x=x[live.NEED].copy(); x["time_ny"]=et(x.time_ny)
        x=x[(x.time_ny.dt.year==2026)&(x.time_ny.dt.month==9)]
        if not x.empty: pieces.append(x); cache.append(fp.name)
    except Exception as e: print("CACHE READ ERROR:",fp.name,e)
one=(pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))
pc=one.close.shift(1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
cand=live.build_candidates(one)
cmap={(str(r.time_ny),str(r.session),str(r.direction)):r for _,r in cand.iterrows()}
idx=pd.Series(one.index,index=one.time_ny).to_dict()

bad=pd.read_csv(PROOF); bad=bad[bad.original_simulate_result.eq("SUPERSEDED")].copy()
bad["entry_time"]=et(bad.entry_time); bad["candidate_time"]=et(bad.candidate_time); bad["kind"]="EXTRA"
good=pd.read_csv(GOOD)
ec="entry_time_et" if "entry_time_et" in good.columns else "entry_time"
cc="candidate_time_et" if "candidate_time_et" in good.columns else "candidate_time"
good["entry_time"]=et(good[ec]); good["candidate_time"]=et(good[cc]); good["kind"]="VALID"

def make(df):
    rows=[]
    for _,x in df.iterrows():
        c=cmap.get((str(x.candidate_time),str(x.session),str(x.direction)))
        i=idx.get(x.candidate_time)
        if c is None or i is None or i<20 or i+2>=len(one): continue
        a=float(one.iloc[i].atr1)
        if not np.isfinite(a) or a<=0: continue
        sg=1 if c.direction=="LONG" else -1; v={}
        for k in [1,2]:
            b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
            v[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
            cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
            v[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
            v[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
        first2=one.iloc[i+1:i+3]
        reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first2.iloc[-1].close))/a
        adverse=(float(c.extreme)-float(first2.low.min()))/a if c.direction=="LONG" else (float(first2.high.max())-float(c.extreme))/a
        rq=(1-min(max(v["m2_close_pos"],0),1))*(1-min(max(float(c.wick_percent),0),1))
        ri=-v["m2_move_atr"]; ca=float(c.atr)
        sweep=float(c.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
        rts=reclaim/(abs(sweep)+.05); itr=ri/(abs(reclaim)+.05); rxw=reclaim*float(c.wick_percent)
        f=dict(v)
        f.update(dict(early_reclaim_atr=reclaim,early_adverse_atr=adverse,wick_percent=float(c.wick_percent),
          sweep_atr=sweep,rejection_quality=rq,reversal_impulse=ri,reclaim_to_sweep=rts,
          impulse_to_reclaim=itr,reclaim_x_wick=rxw,close_x_reclaim=v["m2_close_pos"]*reclaim,
          sweep_minus_reclaim=sweep-reclaim,impulse_minus_reclaim=ri-reclaim,
          quality_balance=rq*itr/(1+rts)))
        f["v15_score"]=live.score(f)
        f["v27_margin_reclaim"]=live.RTH-reclaim
        f["v27_margin_rw"]=live.WTH-rxw
        f.update(kind=x.kind,entry_time=x.entry_time,candidate_time=x.candidate_time,session=x.session,direction=x.direction)
        rows.append(f)
    return pd.DataFrame(rows)

q=pd.concat([make(bad),make(good)],ignore_index=True)
B=q[q.kind=="EXTRA"]; G=q[q.kind=="VALID"]
features=["m1_move_atr","m1_close_pos","m1_dir_bars5","m2_move_atr","m2_close_pos","m2_dir_bars5",
"early_reclaim_atr","early_adverse_atr","wick_percent","sweep_atr","rejection_quality","reversal_impulse",
"reclaim_to_sweep","impulse_to_reclaim","reclaim_x_wick","close_x_reclaim","sweep_minus_reclaim",
"impulse_minus_reclaim","quality_balance","v15_score","v27_margin_reclaim","v27_margin_rw"]

print("="*112); print("THE ICON — RICH ENTRY-TIME CAUSAL FEATURE STUDY"); print("="*112)
print("Coverage:",one.time_ny.min(),"->",one.time_ny.max(),"| caches:",len(cache))
print(f"Extras reconstructed: {len(B)}/155 | Valid reconstructed: {len(G)}/75")
print("\nFEATURE MEDIANS + STANDARDIZED SEPARATION")
stats=[]
for col in features:
    b=B[col].dropna(); g=G[col].dropna()
    if not len(b) or not len(g): continue
    pooled=np.sqrt((b.var(ddof=1)+g.var(ddof=1))/2)
    d=(b.mean()-g.mean())/pooled if np.isfinite(pooled) and pooled>0 else 0
    stats.append((col,float(b.median()),float(g.median()),float(d)))
for col,bm,gm,d in sorted(stats,key=lambda z:abs(z[3]),reverse=True):
    print(f"{col:24s} extra_med={bm:9.4f} valid_med={gm:9.4f} separation={d:+7.3f}")

# Fixed quantile screens derived from VALID distribution only.
# For each feature/direction, report the strongest extra rejection obtainable
# while preserving at least 95%, 98%, or 100% of valid September trades.
print("\nSIMPLE ONE-FEATURE CAUSAL SCREENS (cutoffs derived from VALID trades only)")
print("No outcome labels are used. This is diagnostic, not a promoted strategy rule.")
candidates=[]
for col in features:
    bv=B[col]; gv=G[col].dropna()
    if len(gv)<10: continue
    for side in ["LOW","HIGH"]:
        for keep_target in [1.00,.98,.95,.90]:
            if side=="LOW":
                cutoff=float(gv.min()) if keep_target==1 else float(gv.quantile(1-keep_target))
                brej=int((bv<cutoff).sum()); grej=int((G[col]<cutoff).sum())
                rule=f"{col} < {cutoff:.6g}"
            else:
                cutoff=float(gv.max()) if keep_target==1 else float(gv.quantile(keep_target))
                brej=int((bv>cutoff).sum()); grej=int((G[col]>cutoff).sum())
                rule=f"{col} > {cutoff:.6g}"
            candidates.append((brej,grej,rule))
for max_good in [0,1,4,8]:
    pool=[x for x in candidates if x[1]<=max_good]
    print(f"\nBest screens with <= {max_good} valid trades rejected:")
    for br,gr,rule in sorted(pool,key=lambda x:(-x[0],x[1]))[:10]:
        print(f"  extras {br:3d}/155 removed | valid {gr:2d}/75 removed | {rule}")

out=Path("data/reports/2026-09_rich_causal_feature_study.csv"); q.to_csv(out,index=False)
print("\nSaved:",out)
print("READ ONLY — no strategy thresholds, entries, datasets, or live engine changed.")
