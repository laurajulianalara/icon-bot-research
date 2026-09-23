import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

print("=== FROZEN 766: CHRONOLOGICAL CAUSAL DISCOVERY / VALIDATION ===")
d=pd.read_parquet("data/clean766_vs_premature_forensic_rows.parquet").copy()
tc=next(c for c in ["candidate_time","time_ny","time","extreme_time"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.sort_values(tc).reset_index(drop=True)
y=d["target"].astype(int)

exclude=["target","is_clean_766","is_reference","outcome","future","label","win"]
features=[]
for c in d.select_dtypes(include=[np.number,bool]).columns:
    lc=c.lower()
    if any(k in lc for k in exclude): continue
    if d[c].notna().mean()>=.70 and d[c].nunique(dropna=True)>1: features.append(c)

cut=d[tc].quantile(.70)
train=d[d[tc]<=cut].copy(); test=d[d[tc]>cut].copy()
print("Rows:",len(d),"features:",len(features))
print("Train:",len(train),"positives:",int(train.target.sum()))
print("Untouched validation:",len(test),"positives:",int(test.target.sum()))
print("Chronological cutoff:",cut)

med=train[features].median()
Xtr=train[features].replace([np.inf,-np.inf],np.nan).fillna(med)
Xte=test[features].replace([np.inf,-np.inf],np.nan).fillna(med)
ytr=train.target.astype(int); yte=test.target.astype(int)

models=[
 ("ET",ExtraTreesClassifier(n_estimators=500,min_samples_leaf=8,max_features="sqrt",class_weight="balanced",random_state=42,n_jobs=-1)),
 ("HGB",HistGradientBoostingClassifier(max_iter=250,max_leaf_nodes=15,l2_regularization=2,random_state=42))
]
for name,m in models:
    m.fit(Xtr,ytr); p=m.predict_proba(Xte)[:,1]
    auc=roc_auc_score(yte,p)
    print("\n",name,"validation AUC",round(auc,4))
    for q in [.50,.70,.80,.90,.95,.97,.98,.99]:
        th=np.quantile(p,q); mask=p>=th; n=int(mask.sum())
        if not n: continue
        purity=float(yte[mask].mean()); recall=float(yte[mask].sum()/max(1,yte.sum()))
        print(f" top {100*(1-q):.0f}% | n={n} | clean-purity={purity*100:.2f}% | recall={recall*100:.2f}% | lift={purity/yte.mean():.2f}x")
    if name=="ET":
        imp=pd.Series(m.feature_importances_,index=features).sort_values(ascending=False).head(20)
        print("Top features:",", ".join(f"{k}={v:.3f}" for k,v in imp.items()))

print("\nPURPOSE: this does NOT claim trading performance. It tests whether causal information can identify the frozen 766 on later unseen history.")
print("NEXT: only if validation separation is strong do we convert the frozen model threshold into a sequential one-position RR backtest.")
