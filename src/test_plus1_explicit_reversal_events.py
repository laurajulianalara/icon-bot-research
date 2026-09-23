import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import roc_auc_score

print("=== +1M EXPLICIT REVERSAL EVENTS — LIQUIDITY / RECLAIM / CISD / CHOCH ===")
seq=pd.read_parquet("data/v106_meaningful_reversal_sequence.parquet").copy()
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in seq.columns)
dc=next(c for c in ["direction","side","dir"] if c in seq.columns)
mc=next(c for c in ["minute","delay_min","minutes_after","minute_after"] if c in seq.columns)
seq[tc]=pd.to_datetime(seq[tc],utc=True,errors="coerce")

ref=pd.read_csv("data/final_corrected_766_causal_audit.csv")
ref=ref[ref["corrected_fully_causal_mechanics"].astype(str).str.lower().eq("true")].copy()
ref["mapped_candidate_time"]=pd.to_datetime(ref["mapped_candidate_time"],utc=True,errors="coerce")
pos=set(zip(ref["mapped_candidate_time"],ref["direction"].astype(str).str.upper()))

base=seq[seq[mc]==0].copy()
base["target"]=[int((t,str(s).upper()) in pos) for t,s in zip(base[tc],base[dc])]
ny=base[tc].dt.tz_convert("America/New_York"); base["_day"]=ny.dt.date
if "session" not in base.columns:
    mins=ny.dt.hour*60+ny.dt.minute
    base["session"]=np.select([(mins>=1200)|(mins<1),(mins>=120)&(mins<300),(mins>=570)&(mins<750),(mins>=810)&(mins<1020)],["Asia","London","NYAM","NYPM"],default="")
neg=set()
for _,p in base[base.target==1].iterrows():
    g=base[(base._day==p._day)&(base.session==p.session)&(base[dc].astype(str).str.upper()==str(p[dc]).upper())&(base[tc]<p[tc])]
    neg.update(zip(g[tc],g[dc].astype(str).str.upper()))
keys=pos|neg

# Load richer causal event tables if available and report exactly what is found.
paths=["data/v99_causal_structure_liquidity_features.parquet","data/v102_1m_cisd_choch_liquidity_forensics.parquet"]
rich=None
for p in paths:
    try:
        x=pd.read_parquet(p)
        print("Loaded:",p,"rows=",len(x))
        rich=x if rich is None else rich
        if rich is not None: break
    except Exception: pass
if rich is None: raise RuntimeError("No rich causal structure/liquidity feature file found.")

rtc=next((c for c in ["candidate_time","time_ny","time","extreme_time"] if c in rich.columns),None)
rdc=next((c for c in ["direction","side","dir"] if c in rich.columns),None)
if rtc is None or rdc is None: raise RuntimeError("Rich table missing candidate time/direction.")
rich[rtc]=pd.to_datetime(rich[rtc],utc=True,errors="coerce")
rich["_key"]=list(zip(rich[rtc],rich[rdc].astype(str).str.upper()))

event_tokens=["sweep","liquid","reclaim","cisd","choch","displace","structure","fvg","failed","wick"]
event_cols=[c for c in rich.columns if any(k in c.lower() for k in event_tokens) and pd.api.types.is_numeric_dtype(rich[c])]
print("Explicit causal event features found:",len(event_cols))
print(", ".join(event_cols[:60]))

# Merge explicit candidate-time events with minute 0-1 price behavior.
s=seq[seq[mc].between(0,1)].copy()
s=s[[(t,str(q).upper()) in keys for t,q in zip(s[tc],s[dc])]].copy()
s["target"]=[int((t,str(q).upper()) in pos) for t,q in zip(s[tc],s[dc])]
exclude=["target","reference","outcome","future","label","win","rr","entry","extreme","risk","bar_index","max_favorable"]
nums=[c for c in s.select_dtypes(include=[np.number,bool]).columns if c!=mc and not any(k in c.lower() for k in exclude)]
wide=None
for minute in [0,1]:
    z=s[s[mc]==minute][[tc,dc,"target"]+nums].drop_duplicates([tc,dc]).copy()
    z=z.rename(columns={c:f"m{minute}_{c}" for c in nums})
    if minute: z=z.drop(columns=["target"])
    wide=z if wide is None else wide.merge(z,on=[tc,dc],how="left")
wide["_key"]=list(zip(wide[tc],wide[dc].astype(str).str.upper()))
r=rich[["_key"]+event_cols].drop_duplicates("_key")
wide=wide.merge(r,on="_key",how="left").sort_values(tc).reset_index(drop=True)
features=[c for c in wide.columns if c.startswith("m") or c in event_cols]
cut=wide[tc].quantile(.70); tr=wide[wide[tc]<=cut]; te=wide[wide[tc]>cut]
med=tr[features].median()
m=ExtraTreesClassifier(n_estimators=900,min_samples_leaf=8,max_features="sqrt",class_weight="balanced",random_state=42,n_jobs=-1)
m.fit(tr[features].replace([np.inf,-np.inf],np.nan).fillna(med),tr.target.astype(int))
p=m.predict_proba(te[features].replace([np.inf,-np.inf],np.nan).fillna(med))[:,1]
print("\nValidation rows:",len(te),"positives:",int(te.target.sum()))
print("Validation AUC:",round(roc_auc_score(te.target,p),4),"(prior +1 baseline 0.8742)")
for top in [30,20,10,5,3,2,1]:
    th=np.quantile(p,1-top/100); mask=p>=th
    purity=te.loc[mask,"target"].mean(); recall=te.loc[mask,"target"].sum()/max(1,te.target.sum())
    print(f"TOP {top}% | n={mask.sum()} | purity={100*purity:.2f}% | recall={100*recall:.2f}% | lift={purity/te.target.mean():.2f}x")
print("\nTOP FEATURES")
print(pd.Series(m.feature_importances_,index=features).sort_values(ascending=False).head(30).round(4).to_string())
print("\nNEXT: if explicit events materially improve +1 separation, RR-backtest them at the earliest causally available entry. If not, audit the remaining 1,145 reference trades for recoverable 1m timing instead of over-tuning the 766.")
