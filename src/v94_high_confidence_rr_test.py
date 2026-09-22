import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import balanced_accuracy_score

print("=== V94 HIGH-CONFIDENCE AI — ACTUAL RR TEST ===")
d=pd.read_parquet("data/v81_ai_wait_enter_dataset.parquet").copy()
rr=pd.read_parquet("data/v79_full_causal_rr_outcomes.parquet").copy()
tc=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
d["_t"]=pd.to_datetime(d[tc],utc=True,errors="coerce")
rtc=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in rr.columns)
rr["_t"]=pd.to_datetime(rr[rtc],utc=True,errors="coerce")
d=d.dropna(subset=["_t"]).sort_values("_t").reset_index(drop=True)

ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score","_row")
skip={tc,"_t","ai_wait","ai_enter","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(x in c.lower() for x in ban)
 and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]
X=d[features].replace([np.inf,-np.inf],np.nan); y=d.ai_wait.astype(int)
n=len(d); a=int(n*.60); b=int(n*.80)
m=make_pipeline(SimpleImputer(strategy="median"),ExtraTreesClassifier(n_estimators=800,max_depth=16,min_samples_leaf=12,n_jobs=-1,class_weight="balanced",random_state=42))
m.fit(X.iloc[:a],y.iloc[:a])
pv=m.predict_proba(X.iloc[a:b])[:,1]
th=max(np.arange(.30,.711,.01),key=lambda z:balanced_accuracy_score(y.iloc[a:b],(pv>=z).astype(int)))
pt=m.predict_proba(X.iloc[b:])[:,1]
te=d.iloc[b:].copy(); te["p_wait"]=pt
# We trade when model predicts ENTER (low WAIT probability); confidence in ENTER = 1-p_wait.
te["enter_conf"]=1-te.p_wait
keys=["_t"]
for k in ["direction","extreme"]:
 if k in te.columns and k in rr.columns: keys.append(k)
rrcols=[c for c in rr.columns if c.startswith("win_") or c.startswith("resolved_")]
if not rrcols:
 rrcols=[c for c in rr.columns if any(x in c.lower() for x in ["1r","2r","3r","4r","5r","6r"]) and pd.api.types.is_numeric_dtype(rr[c])]
z=te.merge(rr[keys+rrcols].drop_duplicates(keys),on=keys,how="left")
print("Final-test candidates:",len(te),"RR matched:",len(z))
print("WAIT threshold:",f"{th:.2f}")
print("\nAI ENTER CONFIDENCE -> REAL RR")
for cut in [.50,.60,.70,.80,.90]:
 q=z[z.enter_conf>=cut]
 if not len(q): continue
 print(f"\nENTER confidence >= {cut:.2f} | trades {len(q)} | coverage {len(q)/len(z)*100:.2f}%")
 for r in range(1,7):
  wc=next((c for c in q.columns if c.lower() in [f"win_{r}r",f"win{r}r",f"{r}r_win"]),None)
  if wc:
   vals=pd.to_numeric(q[wc],errors="coerce").dropna()
   print(f"  {r}R WR {vals.mean()*100:.2f}% resolved {len(vals)}")
z.to_csv("data/v94_high_confidence_rr_test.csv",index=False)
print("\nSaved data/v94_high_confidence_rr_test.csv")
print("NEXT: choose confidence policy from REAL RR results, then run sequential one-position-at-a-time simulation.")
