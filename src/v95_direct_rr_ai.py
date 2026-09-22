import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

print("=== V95 DIRECT RR AI ===")
x=pd.read_parquet("data/v88_full_rich_causal_features.parquet").copy()
rr=pd.read_parquet("data/v79_full_causal_rr_outcomes.parquet").copy()
def tc(d): return next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
xt,rt=tc(x),tc(rr)
x["_t"]=pd.to_datetime(x[xt],utc=True,errors="coerce"); rr["_t"]=pd.to_datetime(rr[rt],utc=True,errors="coerce")
keys=["_t"]
for k in ["direction","extreme"]:
    if k in x.columns and k in rr.columns: keys.append(k)
rrcols=[c for c in rr.columns if c.startswith("win_") or c.startswith("resolved_")]
d=x.merge(rr[keys+rrcols].drop_duplicates(keys),on=keys,how="left").sort_values("_t").reset_index(drop=True)
ban=("win_","resolved_","outcome","target","exit","future","next_","hindsight","invalid","_row")
skip={xt,"_t","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(z in c.lower() for z in ban)
          and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]
print("Rows:",len(d),"features:",len(features))
n=len(d); a=int(n*.60); b=int(n*.80)
X=d[features].replace([np.inf,-np.inf],np.nan)
for R in range(1,7):
    wc=next((c for c in d.columns if c.lower() in [f"win_{R}r",f"win{R}r",f"{R}r_win"]),None)
    if wc is None:
        print(f"{R}R label missing"); continue
    y=pd.to_numeric(d[wc],errors="coerce")
    tr=np.arange(0,a)[y.iloc[:a].notna().to_numpy()]
    va=np.arange(a,b)[y.iloc[a:b].notna().to_numpy()]
    te=np.arange(b,n)[y.iloc[b:].notna().to_numpy()]
    model=make_pipeline(SimpleImputer(strategy="median"),ExtraTreesClassifier(n_estimators=700,max_depth=14,min_samples_leaf=20,n_jobs=-1,class_weight="balanced",random_state=40+R))
    model.fit(X.iloc[tr],y.iloc[tr].astype(int))
    pv=model.predict_proba(X.iloc[va])[:,1]; pt=model.predict_proba(X.iloc[te])[:,1]
    # Choose probability cut on validation by best WR subject to >=5% coverage.
    best=None
    for cut in np.arange(.30,.91,.02):
        z=pv>=cut
        if z.mean()<.05 or z.sum()<100: continue
        wr=y.iloc[va].to_numpy()[z].mean()
        score=wr
        if best is None or score>best[0]: best=(score,cut,z.mean())
    if best is None: continue
    _,cut,_=best; z=pt>=cut; yy=y.iloc[te].to_numpy()
    print(f"\n{R}R | AUC {roc_auc_score(yy,pt):.4f} | cut {cut:.2f} | test trades {z.sum()} coverage {z.mean()*100:.2f}% | WR {yy[z].mean()*100:.2f}%")
    for q in [.70,.80,.90,.95]:
        cq=np.quantile(pt,q); zz=pt>=cq
        print(f" top {int((1-q)*100):2d}% n={zz.sum():4d} WR={yy[zz].mean()*100:.2f}%")
print("\nNEXT: use direct RR predictability to decide whether AI can select profitable setups causally; do not use hindsight WAIT/ENTER confidence as a profit score.")
