import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import balanced_accuracy_score, accuracy_score, roc_auc_score

print("=== V93 SPECIALIST / CONFIDENCE AI ===")
d=pd.read_parquet("data/v81_ai_wait_enter_dataset.parquet").copy()
tc=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
d[tc]=pd.to_datetime(d[tc],utc=True,errors="coerce")
d=d.dropna(subset=[tc]).sort_values(tc).reset_index(drop=True)
ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score","_row")
skip={tc,"ai_wait","ai_enter","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(x in c.lower() for x in ban)
 and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]
# Add only known-at-decision categorical context.
cat=[]
for c in ["session","direction"]:
 if c in d.columns:
  z=pd.get_dummies(d[c].astype(str),prefix=c,dtype=int)
  d=pd.concat([d,z],axis=1); cat+=list(z.columns)
features+=cat
X=d[features].replace([np.inf,-np.inf],np.nan); y=d.ai_wait.astype(int)
n=len(d); a=int(n*.60); b=int(n*.80)

def model():
 return make_pipeline(SimpleImputer(strategy="median"),ExtraTreesClassifier(n_estimators=800,max_depth=16,min_samples_leaf=12,n_jobs=-1,class_weight="balanced",random_state=42))

# Generalist.
g=model(); g.fit(X.iloc[:a],y.iloc[:a])
pv=g.predict_proba(X.iloc[a:b])[:,1]
th=max(np.arange(.30,.711,.01),key=lambda z:balanced_accuracy_score(y.iloc[a:b],(pv>=z).astype(int)))
pt=g.predict_proba(X.iloc[b:])[:,1]
base=(pt>=th).astype(int)
print(f"GENERALIST th={th:.2f} | acc {accuracy_score(y.iloc[b:],base)*100:.2f}% | balanced {balanced_accuracy_score(y.iloc[b:],base)*100:.2f}% | AUC {roc_auc_score(y.iloc[b:],pt):.4f}")

# Specialist learns only ambiguous training cases identified out-of-fold style by a first model trained on first 40%.
p0=int(n*.40)
seed=model(); seed.fit(X.iloc[:p0],y.iloc[:p0])
train_prob=seed.predict_proba(X.iloc[p0:a])[:,1]
amb_mask=(train_prob>=.25)&(train_prob<=.75)
amb_idx=np.arange(p0,a)[amb_mask]
print("Specialist training rows:",len(amb_idx))
sp=make_pipeline(SimpleImputer(strategy="median"),HistGradientBoostingClassifier(max_iter=500,max_leaf_nodes=31,learning_rate=.035,l2_regularization=2.0,random_state=7))
sp.fit(X.iloc[amb_idx],y.iloc[amb_idx])

# Choose routing band only on validation.
spv=sp.predict_proba(X.iloc[a:b])[:,1]
best=None
for lo,hi in [(.30,.70),(.35,.65),(.40,.60),(.45,.55)]:
 mix=pv.copy(); route=(pv>=lo)&(pv<=hi); mix[route]=spv[route]
 for t in np.arange(.40,.611,.01):
  sc=balanced_accuracy_score(y.iloc[a:b],(mix>=t).astype(int))
  if best is None or sc>best[0]: best=(sc,lo,hi,t)
_,lo,hi,t=best
spt=sp.predict_proba(X.iloc[b:])[:,1]
mix=pt.copy(); route=(pt>=lo)&(pt<=hi); mix[route]=spt[route]
pred=(mix>=t).astype(int)
print(f"SPECIALIST route={lo:.2f}-{hi:.2f} threshold={t:.2f} routed={route.sum()}")
print(f"FINAL acc {accuracy_score(y.iloc[b:],pred)*100:.2f}% | balanced {balanced_accuracy_score(y.iloc[b:],pred)*100:.2f}% | AUC {roc_auc_score(y.iloc[b:],mix):.4f}")
print(f"CHANGE VS 73.39%: {(balanced_accuracy_score(y.iloc[b:],pred)-.7339)*100:+.2f} points")

# High-confidence decision coverage, useful for a selective production policy.
conf=np.maximum(mix,1-mix)
print("\nSELECTIVE DECISION QUALITY")
for cut in [.60,.70,.80,.90]:
 z=conf>=cut
 if z.sum():
  print(f"confidence>={cut:.2f} coverage={z.mean()*100:.2f}% n={z.sum()} accuracy={(pred[z]==y.iloc[b:].to_numpy()[z]).mean()*100:.2f}%")
print("\nNEXT: if specialist materially improves, preserve it; otherwise stop optimizing the hindsight label and test high-confidence AI decisions against actual RR outcomes.")
