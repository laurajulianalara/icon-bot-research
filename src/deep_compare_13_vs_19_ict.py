#!/usr/bin/env python3
"""Deep causal forensics: 13 historical-match vs 19 causal-only non-London trades.
Research-only. All features are computed from bars available before entry.
Includes Option2B internals plus objective proxies for CISD, FVG, displacement,
liquidity sweep, prior-session/day liquidity proximity, and local structure.
"""
from pathlib import Path
import sys
import numpy as np, pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

C=Path("data/reports/2026-09_strict_causal_outcomes.csv"); B=Path("data/reports/2026-09_trades.csv")
c=pd.read_csv(C); b=pd.read_csv(B)
def pick(df,n):
    for x in n:
        if x in df.columns:return x
    raise KeyError(n)
ce=pick(c,["entry_time_et","entry_time"]); cc=pick(c,["candidate_time_et","candidate_time"]); cs=pick(c,["session","Session"]); cd=pick(c,["direction","Direction"])
be=pick(b,["entry_time","entry_time_et"]); bc=pick(b,["candidate_time","candidate_time_et"]); bs=pick(b,["session","Session"]); bd=pick(b,["direction","Direction"])
for df,col in [(c,ce),(c,cc),(b,be),(b,bc)]: df[col]=pd.to_datetime(df[col],utc=True).dt.tz_convert(live.TZ)
hist={(r[be],str(r[bs]).upper(),str(r[bd]).upper(),r[bc]) for _,r in b.iterrows()}
c["historical_match"]=[(r[ce],str(r[cs]).upper(),str(r[cd]).upper(),r[cc]) in hist for _,r in c.iterrows()]
c=c[c[cs].astype(str).str.upper()!="LONDON"].sort_values(ce).copy()

frames=[]
h=pd.read_parquet(live.HIST)[live.NEED].copy(); h["time_ny"]=pd.to_datetime(h.time_ny)
h["time_ny"]=h.time_ny.dt.tz_localize(live.TZ) if h.time_ny.dt.tz is None else h.time_ny.dt.tz_convert(live.TZ); frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(live.NEED).issubset(q.columns):continue
        q=q[live.NEED].copy(); q["time_ny"]=pd.to_datetime(q.time_ny)
        q["time_ny"]=q.time_ny.dt.tz_localize(live.TZ) if q.time_ny.dt.tz is None else q.time_ny.dt.tz_convert(live.TZ); frames.append(q)
    except: pass
one=pd.concat(frames,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
for k in ["open","high","low","close","volume"]:one[k]=pd.to_numeric(one[k],errors="coerce")
pc=one.close.shift(1); one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

def cisd(pre,sg):
    post=pre.iloc[-2:]; prior=pre.iloc[:-2].tail(8)
    opp=prior[((prior.close-prior.open)*sg)<0]
    if opp.empty:return 0
    level=float(opp.iloc[-1].open); close=float(post.iloc[-1].close)
    return int(close>level if sg==1 else close<level)

def fvg(pre,sg):
    z=pre.tail(10).reset_index(drop=True)
    for j in range(2,len(z)):
        if sg==1 and float(z.loc[j,"low"])>float(z.loc[j-2,"high"]):return 1
        if sg==-1 and float(z.loc[j,"high"])<float(z.loc[j-2,"low"]):return 1
    return 0

rows=[]
for _,r in c.iterrows():
    p=idx.get(r[ce])
    if p is None or p<30:continue
    # Use the exact causal boundary used by the live evaluator: closed bars only plus entry open.
    closed=one.loc[:p-1,live.NEED].copy()
    cand=live.build_candidates(closed)
    z=cand[(cand.time_ny==r[cc])&(cand.direction.astype(str)==str(r[cd]))&(cand.session.astype(str)==str(r[cs]))]
    if z.empty:
        continue
    q=z.iloc[-1]
    # locate candidate inside the causal closed dataframe, not the full global index
    cidx=pd.Series(closed.index,index=closed.time_ny).to_dict()
    gi=cidx.get(r[cc])
    if gi is None: continue
    # closed retains original integer index, so use global one for bar offsets
    i=idx.get(r[cc])
    if i is None or i<25 or i+2>=p:continue
    a=float(one.iloc[i].atr1); sg=1 if str(r[cd])=="LONG" else -1
    if not np.isfinite(a) or a<=0: continue
    vals={}
    for k in [1,2]:
        bar=one.iloc[i+k]; pre6=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(bar.close)-float(one.iloc[i].close))/a*sg
        cp=(bar.close-bar.low)/(bar.high-bar.low) if bar.high>bar.low else .5
        vals[f"m{k}_close_pos"]=float(cp if sg==1 else 1-cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre6.close-pre6.open)*sg)>0)).sum())
    reclaim=(float(one.iloc[i+2].close)-float(q.extreme))/a if sg==1 else (float(q.extreme)-float(one.iloc[i+2].close))/a
    rq=(1-min(max(vals["m2_close_pos"],0),1))*(1-min(max(float(q.wick_percent),0),1))
    ri=-vals["m2_move_atr"]; ca=float(q.atr); sa=float(q.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
    rts=reclaim/(abs(sa)+.05); itr=ri/(abs(reclaim)+.05); rxw=reclaim*float(q.wick_percent)
    ff={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,"reversal_impulse":ri,"reclaim_x_wick":rxw,
        "close_x_reclaim":vals["m2_close_pos"]*reclaim,"sweep_minus_reclaim":sa-reclaim,"impulse_minus_reclaim":ri-reclaim,
        "quality_balance":rq*itr/(1+rts)}
    score=live.score(ff)
    pre=one.iloc[max(0,i-30):i+3].copy()
    bodies=(pre.close-pre.open).abs(); displacement=float(bodies.tail(3).max()/a)
    prior5=one.iloc[max(0,i-5):i]; m2=float(one.iloc[i+2].close)
    structure_break=int(m2>float(prior5.high.max()) if sg==1 else m2<float(prior5.low.min()))
    day=r[cc].date(); prev=one[one.time_ny.dt.date<day]
    prevday=prev[prev.time_ny.dt.date==prev.time_ny.dt.date.max()] if len(prev) else prev
    pdh=float(prevday.high.max()) if len(prevday) else np.nan; pdl=float(prevday.low.min()) if len(prevday) else np.nan
    ext=float(q.extreme); pdl_dist=abs(ext-pdl)/a if np.isfinite(pdl) else np.nan; pdh_dist=abs(ext-pdh)/a if np.isfinite(pdh) else np.nan
    sess_start={"ASIA":1200,"NYAM":570,"NYPM":810}.get(str(r[cs]),0); minute=r[cc].hour*60+r[cc].minute; mins=(minute-sess_start)%1440
    rows.append({"entry_time":r[ce],"session":r[cs],"direction":r[cd],"historical_match":bool(r["historical_match"]),
      "v15_score":score,"minutes_into_session":mins,"sweep_atr":sa,"wick_percent":float(q.wick_percent),"reclaim":reclaim,**vals,**ff,
      "cisd_proxy":cisd(pre,sg),"fvg_present":fvg(pre,sg),"displacement_atr":displacement,"structure_break_proxy":structure_break,
      "near_pdh_025atr":int(np.isfinite(pdh_dist) and pdh_dist<=.25),"near_pdl_025atr":int(np.isfinite(pdl_dist) and pdl_dist<=.25),
      "nearest_pd_level_atr":np.nanmin([pdh_dist,pdl_dist]) if np.isfinite(pdh_dist) or np.isfinite(pdl_dist) else np.nan})

x=pd.DataFrame(rows)
print("\n"+"="*118); print("THE ICON - DEEP CAUSAL FORENSICS: 13 HISTORICAL-MATCH vs 19 CAUSAL-ONLY"); print("="*118)
if x.empty:
    print("ERROR: 0 rows reconstructed. This means candidate matching still disagrees with the causal replay; no conclusions printed.")
    print("Expected non-London rows:",len(c),"| historical:",int(c["historical_match"].sum()),"| causal-only:",int((~c["historical_match"]).sum()))
    sys.exit(2)
features=[z for z in x.columns if z not in ["entry_time","session","direction","historical_match"]]
print("Rows:",len(x),"| historical:",int(x["historical_match"].sum()),"| causal-only:",int((~x["historical_match"]).sum()))
print("Expected:",len(c),"| 13 historical + 19 causal-only")
print("\nGROUP COMPARISON")
out=[]
for f in features:
    a=x.loc[x["historical_match"],f]; e=x.loc[~x["historical_match"],f]
    out.append([f,a.mean(),e.mean(),a.median(),e.median()])
print(pd.DataFrame(out,columns=["feature","hist_mean","extra_mean","hist_median","extra_median"]).round(5).to_string(index=False))
print("\nBINARY ICT/STRUCTURE CONCEPTS")
for f in ["cisd_proxy","fvg_present","structure_break_proxy","near_pdh_025atr","near_pdl_025atr"]:
    a=x.loc[x["historical_match"],f]; e=x.loc[~x["historical_match"],f]
    print(f"{f:24s} HIST {int(a.sum())}/{len(a)} ({100*a.mean():.1f}%) | EXTRA {int(e.sum())}/{len(e)} ({100*e.mean():.1f}%)")
print("\nBEST SIMPLE ONE-FEATURE SEPARATORS")
tests=[]
for f in features:
    if x[f].dtype.kind not in "biufc":continue
    vals=sorted(x[f].dropna().unique())
    for lo,hi in zip(vals[:-1],vals[1:]):
        cut=(lo+hi)/2
        for op in ["<=",">="]:
            keep=x[x[f]<=cut] if op=="<=" else x[x[f]>=cut]
            if len(keep)<3:continue
            hm=int(keep["historical_match"].sum()); ex=len(keep)-hm; recall=hm/max(1,int(x["historical_match"].sum())); purity=hm/len(keep)
            score=2*purity*recall/(purity+recall) if purity+recall else 0
            tests.append((score,hm,ex,purity,recall,f,op,cut))
for _,hm,ex,pur,rec,f,op,cut in sorted(tests,reverse=True)[:25]:
    print(f"{f:26s} {op} {cut: .5f} | {hm:2d} hist + {ex:2d} extras | purity {pur*100:5.1f}% | hist recall {rec*100:5.1f}%")
print("\nIMPORTANT: CISD/FVG/structure labels are objective research proxies, not claims that the frozen strategy used ICT labels.")
print("September is in-sample discovery. Any promising rule must be replayed on the uncapped causal stream and untouched months.")
print("READ-ONLY. No strategy/filter/threshold/session/execution logic changed.")
