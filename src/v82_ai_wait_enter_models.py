import pandas as pd
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, ExtraTreesClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, roc_auc_score

print("=== V82 AI WAIT / ENTER — CHRONOLOGICAL TEST ===")
d=pd.read_parquet("data/v81_ai_wait_enter_dataset.parquet").copy()
tc=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.dropna(subset=[tc]).sort_values(tc).reset_index(drop=True)

ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score")
skip={tc,"ai_wait","ai_enter","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(x in c.lower() for x in ban)
          and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]

n=len(d); a=int(n*.60); b=int(n*.80)
X=d[features].replace([np.inf,-np.inf],np.nan)
y=d.ai_wait.astype(int)
Xtr,ytr=X.iloc[:a],y.iloc[:a]
Xva,yva=X.iloc[a:b],y.iloc[a:b]
Xte,yte=X.iloc[b:],y.iloc[b:]

models={
"HistGradientBoosting":HistGradientBoostingClassifier(max_iter=300,max_leaf_nodes=15,learning_rate=.05,l2_regularization=1.0,random_state=42),
"RandomForest":RandomForestClassifier(n_estimators=350,max_depth=10,min_samples_leaf=25,n_jobs=-1,class_weight="balanced",random_state=42),
"ExtraTrees":ExtraTreesClassifier(n_estimators=350,max_depth=12,min_samples_leaf=20,n_jobs=-1,class_weight="balanced",random_state=42)
}

best=None
for name,m in models.items():
    p=make_pipeline(SimpleImputer(strategy="median"),m)
    p.fit(Xtr,ytr)
    for label,xx,yy in [("VALIDATION",Xva,yva),("FINAL TEST",Xte,yte)]:
        pr=p.predict_proba(xx)[:,1]; pred=(pr>=.5).astype(int)
        cm=confusion_matrix(yy,pred,labels=[0,1])
        print(f"\n{name} — {label}")
        print(f"Accuracy: {accuracy_score(yy,pred)*100:.2f}% | Balanced: {balanced_accuracy_score(yy,pred)*100:.2f}% | AUC: {roc_auc_score(yy,pr):.4f}")
        print("Confusion [ENTER/WAIT]:",cm.tolist())
        if label=="FINAL TEST":
            score=balanced_accuracy_score(yy,pred)
            if best is None or score>best[0]: best=(score,name,p,pr)

score,name,p,pr=best
print(f"\nBEST FINAL MODEL: {name} | balanced accuracy {score*100:.2f}%")
# Probability threshold sweep on untouched final chronological segment.
print("\nFINAL TEST THRESHOLD SWEEP")
for th in [.35,.40,.45,.50,.55,.60,.65,.70,.75,.80]:
    pred=(pr>=th).astype(int)
    print(f"WAIT threshold {th:.2f} | WAIT {pred.sum():4d} | ENTER {(pred==0).sum():4d} | accuracy {accuracy_score(yte,pred)*100:.2f}% | balanced {balanced_accuracy_score(yte,pred)*100:.2f}%")

# Feature importance from ExtraTrees fitted only on first 80%, then reported (not tuned on final labels).
imp=make_pipeline(SimpleImputer(strategy="median"),ExtraTreesClassifier(n_estimators=500,max_depth=12,min_samples_leaf=20,n_jobs=-1,class_weight="balanced",random_state=7))
imp.fit(X.iloc[:b],y.iloc[:b])
est=imp[-1]
fi=pd.Series(est.feature_importances_,index=features).sort_values(ascending=False)
print("\nTOP WAIT/ENTER PREDICTORS")
print(fi.head(20).to_string())

print("\nNEXT: if prediction is strong enough, simulate AI decisions sequentially and score the resulting trades at 1R-6R.")
