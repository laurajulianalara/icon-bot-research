import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import roc_auc_score

print("=== 0-3 MINUTE REVERSAL-SEQUENCE SELECTOR — CHRONOLOGICAL VALIDATION ===")
d=pd.read_parquet("data/v106_meaningful_reversal_sequence.parquet").copy()
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in d.columns)
dc=next(c for c in ["direction","side","dir"] if c in d.columns)
mc=next(c for c in ["minute","delay_min","minutes_after","minute_after"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")

ref=pd.read_csv("data/final_corrected_766_causal_audit.csv")
ref=ref[ref["corrected_fully_causal_mechanics"].astype(str).str.lower().eq("true")].copy()
ref["mapped_candidate_time"]=pd.to_datetime(ref["mapped_candidate_time"],utc=True,errors="coerce")
pos=set(zip(ref["mapped_candidate_time"],ref["direction"].astype(str).str.upper()))

base=d[d[mc]==0].copy()
base["target"]=[int((t,str(s).upper()) in pos) for t,s in zip(base[tc],base[dc])]
ny=base[tc].dt.tz_convert("America/New_York"); base["_day"]=ny.dt.date
if "session" not in base.columns:
    mins=ny.dt.hour*60+ny.dt.minute
    base["session"]=np.select([(mins>=1200)|(mins<1),(mins>=120)&(mins<300),(mins>=570)&(mins<750),(mins>=810)&(mins<1020)],["Asia","London","NYAM","NYPM"],default="")

# Same comparison universe: frozen 766 + premature same-session/same-direction extremes.
neg=set()
for _,p in base[base.target==1].iterrows():
    g=base[(base._day==p._day)&(base.session==p.session)&(base[dc].astype(str).str.upper()==str(p[dc]).upper())&(base[tc]<p[tc])]
    neg.update(zip(g[tc],g[dc].astype(str).str.upper()))
keys=pos|neg
s=d[d[mc].between(0,3)].copy()
s=s[[(t,str(q).upper()) in keys for t,q in zip(s[tc],s[dc])]].copy()
s["target"]=[int((t,str(q).upper()) in pos) for t,q in zip(s[tc],s[dc])]

exclude=["target","reference","outcome","future","label","win","rr","entry","extreme","risk","bar_index","max_favorable"]
nums=[c for c in s.select_dtypes(include=[np.number,bool]).columns if c!=mc and not any(k in c.lower() for k in exclude)]

# Pivot each observable feature by elapsed minute. Missing later snapshots stay missing;
# model only uses completed snapshots through minute 3.
idcols=[tc,dc,"target"]
wide=None
for minute in range(4):
    z=s[s[mc]==minute][idcols+nums].drop_duplicates([tc,dc]).copy()
    z=z.rename(columns={c:f"m{minute}_{c}" for c in nums})
    z=z.drop(columns=["target"]) if minute else z
    wide=z if wide is None else wide.merge(z,on=[tc,dc],how="left")
wide=wide.sort_values(tc).reset_index(drop=True)

features=[c for c in wide.columns if c.startswith("m")]
cut=wide[tc].quantile(.70)
tr=wide[wide[tc]<=cut].copy(); te=wide[wide[tc]>cut].copy()
med=tr[features].median()
Xtr=tr[features].replace([np.inf,-np.inf],np.nan).fillna(med)
Xte=te[features].replace([np.inf,-np.inf],np.nan).fillna(med)
m=ExtraTreesClassifier(n_estimators=800,min_samples_leaf=8,max_features="sqrt",class_weight="balanced",random_state=42,n_jobs=-1)
m.fit(Xtr,tr.target.astype(int)); p=m.predict_proba(Xte)[:,1]
print("Rows:",len(wide),"features:",len(features),"train:",len(tr),"validation:",len(te))
print("Validation positives:",int(te.target.sum()))
print("Validation AUC:",round(roc_auc_score(te.target,p),4))
for top in [30,20,10,5,3,2,1]:
    th=np.quantile(p,1-top/100); mask=p>=th
    purity=te.loc[mask,"target"].mean(); recall=te.loc[mask,"target"].sum()/max(1,te.target.sum())
    print(f"TOP {top}% | n={mask.sum()} | clean-purity={100*purity:.2f}% | recall={100*recall:.2f}% | lift={purity/te.target.mean():.2f}x")
imp=pd.Series(m.feature_importances_,index=features).sort_values(ascending=False).head(25)
print("\nTOP SEQUENCE FEATURES")
print(imp.round(4).to_string())
print("\nNEXT: if this materially beats the prior AUC 0.7245 / purity profile, sequentially RR-backtest the frozen threshold. If not, current V106 sequence features are insufficient and we build explicit sweep/reclaim/CISD/CHoCH event features.")
