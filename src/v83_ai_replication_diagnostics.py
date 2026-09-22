import pandas as pd
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score

print("=== V83 AI REPLICATION DIAGNOSTICS ===")
d=pd.read_parquet("data/v81_ai_wait_enter_dataset.parquet").copy()
tc=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.dropna(subset=[tc]).sort_values(tc).reset_index(drop=True)

ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score")
skip={tc,"ai_wait","ai_enter","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(x in c.lower() for x in ban)
          and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]

X=d[features].replace([np.inf,-np.inf],np.nan)
y=d.ai_wait.astype(int)
n=len(d); cut=int(n*.80)

model=make_pipeline(SimpleImputer(strategy="median"),
    RandomForestClassifier(n_estimators=600,max_depth=12,min_samples_leaf=15,n_jobs=-1,
                           class_weight="balanced",random_state=42))
model.fit(X.iloc[:cut],y.iloc[:cut])
pr=model.predict_proba(X.iloc[cut:])[:,1]
test=d.iloc[cut:].copy()
test["p_wait"]=pr
test["pred_wait"]=(pr>=.50).astype(int)

print("Test rows:",len(test))
print(f"Accuracy: {accuracy_score(y.iloc[cut:],test.pred_wait)*100:.2f}%")
print(f"Balanced: {balanced_accuracy_score(y.iloc[cut:],test.pred_wait)*100:.2f}%")
print(f"AUC: {roc_auc_score(y.iloc[cut:],pr):.4f}")

print("\nCONFIDENCE BINS — does confidence actually mean something?")
test["bin"]=pd.cut(test.p_wait,[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1],include_lowest=True)
g=test.groupby("bin",observed=True).agg(n=("ai_wait","size"),actual_wait=("ai_wait","mean"),avg_p=("p_wait","mean"))
g["actual_wait"]=g.actual_wait*100
g["avg_p"]=g.avg_p*100
print(g.to_string())

for col in ["session","direction"]:
    if col in test.columns:
        print(f"\nBY {col.upper()}")
        for k,z in test.groupby(col):
            print(k,"n=",len(z),
                  "acc=",f"{accuracy_score(z.ai_wait,z.pred_wait)*100:.2f}%",
                  "actual WAIT=",f"{z.ai_wait.mean()*100:.2f}%",
                  "pred WAIT=",f"{z.pred_wait.mean()*100:.2f}%")

et=model[-1]
fi=pd.Series(et.feature_importances_,index=features).sort_values(ascending=False)
print("\nTOP FEATURES")
print(fi.to_string())

test[[tc]+[c for c in ["session","direction"] if c in test.columns]+["ai_wait","pred_wait","p_wait"]].to_csv(
    "data/v83_ai_final_test_predictions.csv",index=False)
print("\nSaved: data/v83_ai_final_test_predictions.csv")
print("NEXT: expand causal market-state features/CISD, retrain, then trade-simulate only after WAIT/ENTER replication improves.")
