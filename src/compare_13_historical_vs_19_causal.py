#!/usr/bin/env python3
"""Read-only comparison of non-London historical-match vs causal-only trades."""
from pathlib import Path
import pandas as pd, numpy as np, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

C=Path("data/reports/2026-09_strict_causal_outcomes.csv")
B=Path("data/reports/2026-09_trades.csv")
c=pd.read_csv(C); b=pd.read_csv(B)

def pick(df,names):
    for n in names:
        if n in df.columns:return n
    raise KeyError(names)

ce=pick(c,["entry_time_et","entry_time"]); cc=pick(c,["candidate_time_et","candidate_time"])
cs=pick(c,["session","Session"]); cd=pick(c,["direction","Direction"])
be=pick(b,["entry_time","entry_time_et"]); bc=pick(b,["candidate_time","candidate_time_et"])
bs=pick(b,["session","Session"]); bd=pick(b,["direction","Direction"])
for df,col in [(c,ce),(c,cc),(b,be),(b,bc)]:
    df[col]=pd.to_datetime(df[col],utc=True).dt.tz_convert(live.TZ)
keys={(r[be],str(r[bs]).upper(),str(r[bd]).upper(),r[bc]) for _,r in b.iterrows()}
c["historical_match"]=[(r[ce],str(r[cs]).upper(),str(r[cd]).upper(),r[cc]) in keys for _,r in c.iterrows()]
c=c[c[cs].astype(str).str.upper()!="LONDON"].copy()

# Reconstruct pre-entry features by asking the unchanged live evaluator at each entry boundary.
frames=[]
h=pd.read_parquet(live.HIST)[live.NEED].copy(); h["time_ny"]=pd.to_datetime(h.time_ny)
h["time_ny"]=h.time_ny.dt.tz_localize(live.TZ) if h.time_ny.dt.tz is None else h.time_ny.dt.tz_convert(live.TZ)
frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(live.NEED).issubset(q.columns):continue
        q=q[live.NEED].copy(); q["time_ny"]=pd.to_datetime(q.time_ny)
        q["time_ny"]=q.time_ny.dt.tz_localize(live.TZ) if q.time_ny.dt.tz is None else q.time_ny.dt.tz_convert(live.TZ)
        frames.append(q)
    except Exception:pass
one=pd.concat(frames,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
for k in ["open","high","low","close","volume"]: one[k]=pd.to_numeric(one[k],errors="coerce")
idx=pd.Series(one.index,index=one.time_ny).to_dict()

rows=[]
for _,r in c.sort_values(ce).iterrows():
    p=idx.get(r[ce])
    if p is None or p<3:continue
    closed=one.loc[:p-1,live.NEED].tail(6500).copy()
    op={"time_ny":r[ce],"ticker":one.loc[p,"ticker"],"open":one.loc[p,"open"]}
    sigs=live.evaluate(closed,live_open=op)
    match=[s for s in sigs if pd.Timestamp(s["candidate_time_et"])==r[cc] and str(s["direction"])==str(r[cd]) and str(s["session"])==str(r[cs])]
    if not match:continue
    s=match[-1]
    rows.append({"entry_time":r[ce],"session":r[cs],"direction":r[cd],"historical_match":bool(r.historical_match),
                 "v15_score":float(s["v15_score"]),"risk_points":float(s["risk_points"])})

x=pd.DataFrame(rows)
print("\n"+"="*96)
print("THE ICON - 13 HISTORICAL-MATCH vs 19 CAUSAL-ONLY: PRE-ENTRY COMPARISON")
print("="*96)
print("Expected non-London trades:",len(c),"| reconstructed:",len(x))
print("Historical-match:",int(x.historical_match.sum()),"| causal-only:",int((~x.historical_match).sum()))

print("\nV15 + RISK COMPARISON")
for f in ["v15_score","risk_points"]:
    a=x.loc[x.historical_match,f]; z=x.loc[~x.historical_match,f]
    print(f"{f:14s} HIST mean={a.mean():.6f} median={a.median():.6f} min={a.min():.6f} max={a.max():.6f}")
    print(f"{'':14s} EXTRA mean={z.mean():.6f} median={z.median():.6f} min={z.min():.6f} max={z.max():.6f}")

print("\nBY SESSION")
print(pd.crosstab(x["session"],x["historical_match"],margins=True).rename(columns={False:"causal_only",True:"historical_match"}).to_string())

# Test simple causal thresholds on V15 and risk; discovery only.
print("\nBEST SIMPLE SINGLE-FEATURE SEPARATORS (discovery only)")
tests=[]
for f in ["v15_score","risk_points"]:
    vals=sorted(x[f].dropna().unique())
    for a,bv in zip(vals[:-1],vals[1:]):
        cut=(a+bv)/2
        for op in ["<=",">="]:
            keep=x[x[f]<=cut] if op=="<=" else x[x[f]>=cut]
            if len(keep)<3:continue
            hm=int(keep.historical_match.sum()); ex=len(keep)-hm
            recall=hm/max(1,int(x.historical_match.sum())); precision=hm/len(keep)
            score=2*precision*recall/(precision+recall) if precision+recall else 0
            tests.append((score,hm,ex,precision,recall,f,op,cut))
for _,hm,ex,prec,rec,f,op,cut in sorted(tests,reverse=True)[:12]:
    print(f"{f} {op} {cut:.6f}: keep {hm} historical + {ex} extras | purity {prec*100:.1f}% | historical recall {rec*100:.1f}%")

print("\nPER TRADE")
print(x.to_string(index=False))
print("\nNOTE: This first pass compares fields the live evaluator already outputs. It is discovery, not a new filter.")
print("READ-ONLY. No strategy/filter/threshold/session/execution changes.")
