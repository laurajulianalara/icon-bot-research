import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, ExtraTreesClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score

print("=== V91 SESSION-EXTREME AI RETRAIN ===")
d=pd.read_parquet("data/v90_session_extreme_structure_features.parquet").copy()\nlabels=pd.read_parquet("data/v81_ai_wait_enter_dataset.parquet").copy()
tc=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.dropna(subset=[tc]).sort_values(tc).reset_index(drop=True)\nlt=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in labels.columns)\nlabels["_label_time"]=pd.to_datetime(labels[lt],utc=True,errors="coerce")\njoin_keys=[]\nd["_label_time"]=d[tc]\njoin_keys=["_label_time"]\nfor k in ["direction","extreme"]:\n    if k in d.columns and k in labels.columns: join_keys.append(k)\nlab=labels[join_keys+["ai_wait","ai_enter"]].drop_duplicates(join_keys)\nd=d.merge(lab,on=join_keys,how="left")\nprint("AI labels matched:",f"{d.ai_wait.notna().mean()*100:.2f}%")\nd=d.dropna(subset=["ai_wait"]).reset_index(drop=True)

new=["reject_2m_atr","best_reject_2m_atr","reversal_closes_3","session_range_before_atr",
"extreme_from_session_open_atr","micro_cisd_break_atr","micro_cisd_confirm","finished_pressure"]
# Exclude V90 prior_same_extremes/minutes_since_prior_extreme: diagnostic output showed the counter
# was not session-reset, so it is not admitted into the model.
ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score")
skip={tc,"ai_wait","ai_enter","entry","risk","prior_same_extremes","minutes_since_prior_extreme","continuation_2m_atr"}
features=[c for c in d.columns if c not in skip and not any(x in c.lower() for x in ban)
          and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]
print("Features admitted:",len(features))
print("Excluded broken V90 fields: prior_same_extremes, minutes_since_prior_extreme, continuation_2m_atr")

n=len(d); a=int(n*.60); b=int(n*.80)
X=d[features].replace([np.inf,-np.inf],np.nan); y=d.ai_wait.astype(int)
models={
"HistGradientBoosting":HistGradientBoostingClassifier(max_iter=450,max_leaf_nodes=31,learning_rate=.04,l2_regularization=1.5,random_state=42),
"RandomForest":RandomForestClassifier(n_estimators=550,max_depth=14,min_samples_leaf=15,n_jobs=-1,class_weight="balanced",random_state=42),
"ExtraTrees":ExtraTreesClassifier(n_estimators=550,max_depth=16,min_samples_leaf=12,n_jobs=-1,class_weight="balanced",random_state=42)}
best=None
for name,m in models.items():
    p=make_pipeline(SimpleImputer(strategy="median"),m); p.fit(X.iloc[:a],y.iloc[:a])
    pv=p.predict_proba(X.iloc[a:b])[:,1]; pt=p.predict_proba(X.iloc[b:])[:,1]
    th=max(np.arange(.30,.711,.01),key=lambda z:balanced_accuracy_score(y.iloc[a:b],(pv>=z).astype(int)))
    pred=(pt>=th).astype(int); bal=balanced_accuracy_score(y.iloc[b:],pred)
    print(f"{name:20s} th={th:.2f} | FINAL acc {accuracy_score(y.iloc[b:],pred)*100:.2f}% | balanced {bal*100:.2f}% | AUC {roc_auc_score(y.iloc[b:],pt):.4f}")
    if best is None or bal>best[0]: best=(bal,name,th,p)
bal,name,th,p=best
print(f"\nBEST V91: {name} | balanced {bal*100:.2f}%")
print(f"CHANGE VS V89 73.39%: {(bal-.7339)*100:+.2f} percentage points")
if hasattr(p[-1],"feature_importances_"):
    fi=pd.Series(p[-1].feature_importances_,index=features).sort_values(ascending=False)
    print("\nTOP PREDICTORS"); print(fi.head(25).to_string())
print("\nNEXT: use V91 result to decide whether to deepen structure features or move to sequential RR simulation.")
