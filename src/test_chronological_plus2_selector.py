import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import roc_auc_score

print("=== CHRONOLOGICAL +2 SELECTOR — BLIND POPULATION ===")
d=pd.read_parquet("data/blind_plus2_filter_gap_audit.parquet").copy()
d["t"]=pd.to_datetime(d["t"],utc=True,errors="coerce")
d=d.dropna(subset=["t"]).sort_values("t").reset_index(drop=True)

features=["rev0","rev1","rev2","range0","range1","range2","net_reversal_move","extreme_shift"]
X=d[features].replace([np.inf,-np.inf],np.nan).fillna(0)
y=d.is_ref.astype(int)

cut=int(len(d)*.70)
Xtr,Xte=X.iloc[:cut],X.iloc[cut:]
ytr,yte=y.iloc[:cut],y.iloc[cut:]
m=ExtraTreesClassifier(n_estimators=500,min_samples_leaf=8,class_weight="balanced",random_state=42,n_jobs=-1)
m.fit(Xtr,ytr)
p=m.predict_proba(Xte)[:,1]
print("Train:",len(Xtr),"positives",int(ytr.sum()))
print("Unseen test:",len(Xte),"positives",int(yte.sum()))
print("AUC:",f"{roc_auc_score(yte,p):.4f}")

test=d.iloc[cut:].copy(); test["score"]=p
print("\nUNSEEN PRECISION / RECALL")
for pct in [20,10,5,3,2,1]:
    q=np.percentile(p,100-pct)
    z=test[test.score>=q]
    precision=100*z.is_ref.mean()
    recall=100*z.is_ref.sum()/max(test.is_ref.sum(),1)
    print(f"TOP {pct:>2}% | signals={len(z):4d} | purity={precision:6.2f}% | recall={recall:6.2f}%")

print("\nFEATURE IMPORTANCE")
for f,v in sorted(zip(features,m.feature_importances_),key=lambda x:x[1],reverse=True):
    print(f"{f}: {v:.4f}")

test[["t","direction","is_ref","score"]+features].to_parquet("data/plus2_selector_unseen_scores.parquet",index=False)
print("\nSaved data/plus2_selector_unseen_scores.parquet")
print("This is selection-only. Do NOT interpret AUC/purity as trading win rate. Next step is RR backtest only if unseen separation is strong enough.")
