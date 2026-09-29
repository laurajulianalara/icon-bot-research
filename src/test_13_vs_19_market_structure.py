#!/usr/bin/env python3
"""Causal market-structure forensics for the 13 historical-match vs 19 causal-only non-London trades.
READ-ONLY research. Every feature is computed from bars available before the entry.
Uses confirmed pivots only: a pivot is not considered known until right-side confirmation bars have closed.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

C=Path("data/reports/2026-09_strict_causal_outcomes.csv")
B=Path("data/reports/2026-09_trades.csv")
c=pd.read_csv(C); b=pd.read_csv(B)
def pick(df,n):
    for x in n:
        if x in df.columns:return x
    raise KeyError(n)
ce=pick(c,["entry_time_et","entry_time"]); cc=pick(c,["candidate_time_et","candidate_time"])
cs=pick(c,["session","Session"]); cd=pick(c,["direction","Direction"])
be=pick(b,["entry_time","entry_time_et"]); bc=pick(b,["candidate_time","candidate_time_et"])
bs=pick(b,["session","Session"]); bd=pick(b,["direction","Direction"])
for df,col in [(c,ce),(c,cc),(b,be),(b,bc)]:
    df[col]=pd.to_datetime(df[col],utc=True).dt.tz_convert(live.TZ)
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
    except Exception: pass
one=pd.concat(frames,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
for k in ["open","high","low","close","volume"]: one[k]=pd.to_numeric(one[k],errors="coerce")
pc=one.close.shift(1); one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

SESSION_START={"ASIA":(20,0),"NYAM":(9,30),"NYPM":(13,30)}

def resample_closed(df, minutes):
    if minutes==1:return df.copy()
    z=df.set_index("time_ny").resample(f"{minutes}min",label="left",closed="left").agg(
        open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum"))
    return z.dropna().reset_index()

def confirmed_pivots(z,left=2,right=2):
    hi=[]; lo=[]
    # z contains CLOSED bars only. A pivot at i is known only after i+right is present.
    for i in range(left,len(z)-right):
        h=z.high.iloc[i]; l=z.low.iloc[i]
        if h>z.high.iloc[i-left:i].max() and h>=z.high.iloc[i+1:i+right+1].max(): hi.append((i,float(h)))
        if l<z.low.iloc[i-left:i].min() and l<=z.low.iloc[i+1:i+right+1].min(): lo.append((i,float(l)))
    return hi,lo

def structure_snapshot(raw, tf):
    z=resample_closed(raw,tf)
    if len(z)<8:return {"bias":0,"bos":0,"last_hi":np.nan,"last_lo":np.nan,"range_pos":np.nan}
    hi,lo=confirmed_pivots(z)
    last_hi=hi[-1][1] if hi else np.nan; last_lo=lo[-1][1] if lo else np.nan
    bias=0
    if len(hi)>=2 and len(lo)>=2:
        if hi[-1][1]>hi[-2][1] and lo[-1][1]>lo[-2][1]: bias=1
        elif hi[-1][1]<hi[-2][1] and lo[-1][1]<lo[-2][1]: bias=-1
    close=float(z.close.iloc[-1]); bos=0
    # compare current close with most recent confirmed swing that predates final bar
    if np.isfinite(last_hi) and close>last_hi: bos=1
    if np.isfinite(last_lo) and close<last_lo: bos=-1
    rp=np.nan
    if np.isfinite(last_hi) and np.isfinite(last_lo) and last_hi>last_lo: rp=(close-last_lo)/(last_hi-last_lo)
    return {"bias":bias,"bos":bos,"last_hi":last_hi,"last_lo":last_lo,"range_pos":rp}

def session_open_ts(t,s):
    hh,mm=SESSION_START[s]
    d=t.date()
    return pd.Timestamp(year=d.year,month=d.month,day=d.day,hour=hh,minute=mm,tz=live.TZ)

rows=[]
for _,r in c.iterrows():
    et=r[ce]; ct=r[cc]; s=str(r[cs]).upper(); d=str(r[cd]).upper(); sg=1 if d=="LONG" else -1
    p=idx.get(et)
    if p is None: continue
    # Entry decision may use only bars strictly before entry timestamp.
    pre=one.iloc[:p].copy()
    if pre.empty:continue
    st=session_open_ts(et,s)
    # For ASIA after midnight, session belongs to prior calendar date.
    if s=="ASIA" and et.hour<12: st-=pd.Timedelta(days=1)
    op=one.index[one.time_ny<st]
    if len(op)==0:continue
    oi=int(op[-1])+1
    open_pre=one.iloc[:oi].copy() # data available exactly at session open: all completed prior bars
    rec={"entry_time":et,"session":s,"direction":d,"historical_match":bool(r.historical_match)}
    for tf in [1,3,5,15,60]:
        a=structure_snapshot(open_pre,tf); e=structure_snapshot(pre,tf)
        rec[f"open_bias_{tf}m"]=a["bias"]; rec[f"entry_bias_{tf}m"]=e["bias"]
        rec[f"transition_{tf}m"]=e["bias"]-a["bias"]
        rec[f"aligned_entry_{tf}m"]=int(e["bias"]==sg)
        rec[f"reversal_transition_{tf}m"]=int(a["bias"]==-sg and e["bias"]==sg)
        rec[f"entry_bos_{tf}m"]=e["bos"]
        rec[f"bos_aligned_{tf}m"]=int(e["bos"]==sg)
        rec[f"entry_range_pos_{tf}m"]=e["range_pos"]
    # repeated attacks of candidate extreme region before entry, causal and ATR-normalized
    ci=idx.get(ct); atr=float(one.iloc[ci].atr1) if ci is not None and np.isfinite(one.iloc[ci].atr1) else np.nan
    if ci is not None and atr>0:
        cand=live.build_candidates(one.loc[:ci,live.NEED].copy())
        z=cand[(cand.time_ny==ct)&(cand.direction.astype(str)==d)]
        ext=float(z.iloc[-1].extreme) if len(z) else np.nan
        look=one.iloc[max(0,oi):p]
        tol=.15*atr
        if np.isfinite(ext):
            touches=((look.high>=ext-tol)&(look.low<=ext+tol)).sum()
            rec["extreme_touches"]=int(touches)
            rec["entry_distance_from_extreme_atr"]=abs(float(pre.close.iloc[-1])-ext)/atr
        else:
            rec["extreme_touches"]=np.nan; rec["entry_distance_from_extreme_atr"]=np.nan
    rows.append(rec)

x=pd.DataFrame(rows)
print("\n"+"="*118)
print("THE ICON - CAUSAL MARKET STRUCTURE: 13 HISTORICAL-MATCH vs 19 CAUSAL-ONLY")
print("="*118)
if x.empty or "historical_match" not in x:
    raise RuntimeError("No rows reconstructed. Stop: do not interpret this test.")
print("Rows:",len(x),"| historical:",int(x.historical_match.sum()),"| causal-only:",int((~x.historical_match).sum()))
print("Expected: 32 | 13 historical + 19 causal-only")
if len(x)!=32 or int(x.historical_match.sum())!=13:
    raise RuntimeError("Identity mismatch. Stop: do not interpret this test.")

print("\nSTRUCTURE PREVALENCE")
binary=[z for z in x.columns if z.startswith(("aligned_entry_","reversal_transition_","bos_aligned_"))]
for f in binary:
    a=x.loc[x.historical_match,f]; e=x.loc[~x.historical_match,f]
    print(f"{f:32s} HIST {int(a.sum()):2d}/13 ({100*a.mean():5.1f}%) | EXTRA {int(e.sum()):2d}/19 ({100*e.mean():5.1f}%)")

print("\nBIAS / TRANSITION MEANS")
numeric=[z for z in x.columns if z not in ["entry_time","session","direction","historical_match"]]
out=[]
for f in numeric:
    a=pd.to_numeric(x.loc[x.historical_match,f],errors="coerce"); e=pd.to_numeric(x.loc[~x.historical_match,f],errors="coerce")
    out.append([f,a.mean(),e.mean(),a.median(),e.median()])
print(pd.DataFrame(out,columns=["feature","hist_mean","extra_mean","hist_median","extra_median"]).round(4).to_string(index=False))

print("\nBEST SIMPLE CAUSAL STRUCTURE SEPARATORS")
tests=[]
for f in numeric:
    v=pd.to_numeric(x[f],errors="coerce"); vals=sorted(v.dropna().unique())
    for lo,hi in zip(vals[:-1],vals[1:]):
        cut=(lo+hi)/2
        for op in ["<=",">="]:
            keep=x[v<=cut] if op=="<=" else x[v>=cut]
            if len(keep)<3:continue
            hm=int(keep.historical_match.sum()); ex=len(keep)-hm
            recall=hm/13; purity=hm/len(keep)
            score=2*purity*recall/(purity+recall) if purity+recall else 0
            tests.append((score,hm,ex,purity,recall,f,op,cut))
for _,hm,ex,pur,rec,f,op,cut in sorted(tests,reverse=True)[:30]:
    print(f"{f:32s} {op} {cut: .4f} | {hm:2d} hist + {ex:2d} extras | purity {pur*100:5.1f}% | hist recall {rec*100:5.1f}%")

print("\nREAD-ONLY. Confirmed-pivot structure only; future bars are not used to define pivots at either snapshot.")
print("September remains in-sample forensic discovery. Promising rules require full causal replay + untouched-month validation.")
