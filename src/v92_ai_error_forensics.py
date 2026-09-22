import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import balanced_accuracy_score, accuracy_score, roc_auc_score

print("=== V92 AI ERROR FORENSICS ===")
d=pd.read_parquet("data/v81_ai_wait_enter_dataset.parquet").copy()
tc=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.dropna(subset=[tc]).sort_values(tc).reset_index(drop=True)
ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score")
skip={tc,"ai_wait","ai_enter","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(x in c.lower() for x in ban)
 and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]
X=d[features].replace([np.inf,-np.inf],np.nan); y=d.ai_wait.astype(int)
n=len(d); a=int(n*.60); b=int(n*.80)
p=make_pipeline(SimpleImputer(strategy="median"),ExtraTreesClassifier(n_estimators=700,max_depth=16,min_samples_leaf=12,n_jobs=-1,class_weight="balanced",random_state=42))
p.fit(X.iloc[:a],y.iloc[:a])
pv=p.predict_proba(X.iloc[a:b])[:,1]
th=max(np.arange(.30,.711,.01),key=lambda z:balanced_accuracy_score(y.iloc[a:b],(pv>=z).astype(int)))
pt=p.predict_proba(X.iloc[b:])[:,1]; pred=(pt>=th).astype(int)
te=d.iloc[b:].copy(); te["p_wait"]=pt; te["pred_wait"]=pred; te["correct"]=(pred==y.iloc[b:].to_numpy())
te["confidence"]=np.where(pred==1,pt,1-pt)
print(f"Threshold {th:.2f} | accuracy {accuracy_score(y.iloc[b:],pred)*100:.2f}% | balanced {balanced_accuracy_score(y.iloc[b:],pred)*100:.2f}% | AUC {roc_auc_score(y.iloc[b:],pt):.4f}")
print("\nERRORS BY CONFIDENCE")
for lo,hi in [(0.50,.60),(.60,.70),(.70,.80),(.80,.90),(.90,1.01)]:
 z=te[(te.confidence>=lo)&(te.confidence<hi)]
 if len(z): print(f"{lo:.2f}-{hi:.2f} n={len(z):4d} accuracy={z.correct.mean()*100:.2f}%")
for col in ["session","direction"]:
 if col in te:
  print("\nBY",col.upper())
  for k,z in te.groupby(col): print(k,len(z),f"acc={z.correct.mean()*100:.2f}%")
print("\nFALSE ENTERS (AI ENTER, original WAIT):",int(((pred==0)&(y.iloc[b:].to_numpy()==1)).sum()))
print("FALSE WAITS  (AI WAIT, original ENTER):",int(((pred==1)&(y.iloc[b:].to_numpy()==0)).sum()))
te.to_csv("data/v92_ai_error_forensics.csv",index=False)
print("\nSaved data/v92_ai_error_forensics.csv")
print("NEXT: V93 targets the specific error pockets instead of adding generic features.")
