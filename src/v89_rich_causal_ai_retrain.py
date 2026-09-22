import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, ExtraTreesClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score

print("=== V89 RICH CAUSAL AI — BASELINE VS ENRICHED ===")
base=pd.read_parquet("data/v81_ai_wait_enter_dataset.parquet").copy()
rich=pd.read_parquet("data/v88_full_rich_causal_features.parquet").copy()

def tc(d):
    return next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
bt,rt=tc(base),tc(rich)
base["_time"]=pd.to_datetime(base[bt],utc=True,errors="coerce")
rich["_time"]=pd.to_datetime(rich[rt],utc=True,errors="coerce")
base=base.dropna(subset=["_time"]).sort_values("_time").reset_index(drop=True)
rich=rich.dropna(subset=["_time"]).sort_values("_time").reset_index(drop=True)

# Join strictly by candidate time + direction + extreme when available.
keys=["_time"]
for c in ["direction","extreme"]:
    if c in base.columns and c in rich.columns: keys.append(c)
newcols=["cisd","disp","sweep","approach3_atr","approach5_atr","approach10_atr","pre30_range_atr",
"pre10_avg_range_atr","pre10_avg_body_atr","pre5_directional_bars","stretch20_atr","range5_atr","range10_atr","range20_atr"]
rr=rich[keys+newcols].drop_duplicates(keys)
d=base.merge(rr,on=keys,how="left",suffixes=("","_rich"))
print("Rows:",len(d),"Rich match:",f"{d[newcols[0]].notna().mean()*100:.2f}%")

ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score")
skip={bt,"_time","ai_wait","ai_enter","entry","risk"}
old=[c for c in base.columns if c not in skip and not any(x in c.lower() for x in ban)
     and pd.api.types.is_numeric_dtype(base[c]) and base[c].notna().sum()>1000]
enriched=list(dict.fromkeys(old+newcols))
print("Baseline features:",len(old),"Enriched:",len(enriched))

n=len(d); a=int(n*.60); b=int(n*.80)
y=d.ai_wait.astype(int)
models={
"HistGradientBoosting":lambda:HistGradientBoostingClassifier(max_iter=400,max_leaf_nodes=31,learning_rate=.04,l2_regularization=1.5,random_state=42),
"RandomForest":lambda:RandomForestClassifier(n_estimators=500,max_depth=14,min_samples_leaf=15,n_jobs=-1,class_weight="balanced",random_state=42),
"ExtraTrees":lambda:ExtraTreesClassifier(n_estimators=500,max_depth=16,min_samples_leaf=12,n_jobs=-1,class_weight="balanced",random_state=42)
}
best=None
for setname,features in [("BASELINE",old),("ENRICHED",enriched)]:
    X=d[features].replace([np.inf,-np.inf],np.nan)
    print("\n---",setname,"---")
    for name,mk in models.items():
        p=make_pipeline(SimpleImputer(strategy="median"),mk())
        p.fit(X.iloc[:a],y.iloc[:a])
        pv=p.predict_proba(X.iloc[a:b])[:,1]
        pt=p.predict_proba(X.iloc[b:])[:,1]
        # choose threshold only on validation, never final test
        choices=np.arange(.30,.711,.01)
        th=max(choices,key=lambda z:balanced_accuracy_score(y.iloc[a:b],(pv>=z).astype(int)))
        pred=(pt>=th).astype(int)
        bal=balanced_accuracy_score(y.iloc[b:],pred); acc=accuracy_score(y.iloc[b:],pred); auc=roc_auc_score(y.iloc[b:],pt)
        print(f"{name:20s} th={th:.2f} | FINAL acc {acc*100:.2f}% | balanced {bal*100:.2f}% | AUC {auc:.4f}")
        if setname=="ENRICHED" and (best is None or bal>best[0]): best=(bal,name,th,p,features)
bal,name,th,p,features=best
print(f"\nBEST ENRICHED: {name} | balanced {bal*100:.2f}% | threshold {th:.2f}")
print(f"CHANGE VS 73.13% BASELINE: {(bal-.7313)*100:+.2f} percentage points")
X=d[features].replace([np.inf,-np.inf],np.nan)
if hasattr(p[-1],"feature_importances_"):
    fi=pd.Series(p[-1].feature_importances_,index=features).sort_values(ascending=False)
    print("\nTOP PREDICTORS")
    print(fi.head(25).to_string())
print("\nNEXT: if enriched AI materially improves replication, V90 runs sequential 1R-6R trading simulation; otherwise expand strict-causal structure/CISD features before simulation.")
