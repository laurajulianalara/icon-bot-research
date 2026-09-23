import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

print("=== LARGE CAUSAL SELECTOR SEARCH — NATIVE 1M 1,911 TARGET ===")
d=pd.read_parquet("data/rich_plus2_all_candidates.parquet").copy()
d["t"]=pd.to_datetime(d["t"],utc=True,errors="coerce")
d=d.sort_values("t").reset_index(drop=True)
ban={"is_ref"}
meta={"t","direction","_t","_dir"}
features=[c for c in d.columns if c not in ban|meta and pd.api.types.is_numeric_dtype(d[c])]
X=d[features].replace([np.inf,-np.inf],np.nan)
y=d.is_ref.astype(int)
n=len(d); tr=int(n*.60); va=int(n*.80)
med=X.iloc[:tr].median(numeric_only=True); X=X.fillna(med).fillna(0)
models=[
("ET4",ExtraTreesClassifier(n_estimators=900,min_samples_leaf=4,class_weight="balanced",max_features="sqrt",random_state=11,n_jobs=-1)),
("ET10",ExtraTreesClassifier(n_estimators=900,min_samples_leaf=10,class_weight="balanced",max_features=.7,random_state=22,n_jobs=-1)),
("RF6",RandomForestClassifier(n_estimators=700,min_samples_leaf=6,class_weight="balanced_subsample",max_features="sqrt",random_state=33,n_jobs=-1)),
("HGB",HistGradientBoostingClassifier(max_iter=350,learning_rate=.05,max_leaf_nodes=15,l2_regularization=2,random_state=44))
]
best=None
for name,m in models:
    m.fit(X.iloc[:tr],y.iloc[:tr])
    pv=m.predict_proba(X.iloc[tr:va])[:,1]
    auc=roc_auc_score(y.iloc[tr:va],pv)
    print(name,"validation AUC",f"{auc:.4f}")
    if best is None or auc>best[0]: best=(auc,name,m)
auc,name,m=best
pt=m.predict_proba(X.iloc[va:])[:,1]; yt=y.iloc[va:]
print("\nBEST:",name,"validation",f"{auc:.4f}","FINAL UNTOUCHED TEST AUC",f"{roc_auc_score(yt,pt):.4f}")
print("Final test rows:",len(yt),"positives",int(yt.sum()))
print("\nFINAL TEST PRECISION / RECALL")
for pct in [20,15,10,7.5,5,3,2,1,.5]:
    q=np.percentile(pt,100-pct); z=pt>=q
    print(f"TOP {pct:>4}% | signals={z.sum():4d} | purity={100*yt.to_numpy()[z].mean():6.2f}% | recall={100*yt.to_numpy()[z].sum()/max(yt.sum(),1):6.2f}%")
out=d.iloc[va:][["t","direction","is_ref"]].copy();out["score"]=pt
out.to_parquet("data/large_causal_selector_final_test_scores.parquet",index=False)
print("\nSaved final untouched scores. No RR labels were used to train.")
print("NEXT: if separation remains insufficient, stop generic classifier tuning and reconstruct the exact old deterministic filter chain on native 1m timing.")
