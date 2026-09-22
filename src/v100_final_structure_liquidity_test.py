import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

print("=== V100 FINAL STRUCTURE/LIQUIDITY CAUSAL TEST ===")
d=pd.read_parquet("data/v99_causal_structure_liquidity_features.parquet").copy()
rr=pd.read_parquet("data/v79_full_causal_rr_outcomes.parquet").copy()
def tc(x): return next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in x.columns)
dt,rt=tc(d),tc(rr)
d["_t"]=pd.to_datetime(d[dt],utc=True,errors="coerce"); rr["_t"]=pd.to_datetime(rr[rt],utc=True,errors="coerce")
keys=["_t"]+[k for k in ["direction","extreme"] if k in d.columns and k in rr.columns]
rrcols=[c for c in rr.columns if c.startswith("win_") or c.startswith("resolved_")]
d=d.merge(rr[keys+rrcols].drop_duplicates(keys),on=keys,how="inner").sort_values("_t").reset_index(drop=True)
ban=("win_","resolved_","outcome","target","exit","future","next_","hindsight","invalid","_row")
skip={dt,"_t","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(z in c.lower() for z in ban) and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]
for c in ["session","direction"]:
 if c in d:
  z=pd.get_dummies(d[c].astype(str),prefix=c,dtype=int); d=pd.concat([d,z],axis=1); features+=list(z.columns)
X=d[features].replace([np.inf,-np.inf],np.nan)
n=len(d); a=int(n*.60); b=int(n*.80)
print("Rows:",n,"features:",len(features),"train/val/test:",a,b-a,n-b)
def gety(R):
 c=next((c for c in d.columns if c.lower() in [f"win_{R}r",f"win{R}r",f"{R}r_win"]),None)
 return pd.to_numeric(d[c],errors="coerce")
models=[
 ("ET",lambda s:ExtraTreesClassifier(n_estimators=900,max_depth=18,min_samples_leaf=10,n_jobs=-1,class_weight="balanced",random_state=s)),
 ("RF",lambda s:RandomForestClassifier(n_estimators=700,max_depth=16,min_samples_leaf=12,n_jobs=-1,class_weight="balanced",max_features=.7,random_state=s)),
 ("HGB",lambda s:HistGradientBoostingClassifier(max_iter=500,max_leaf_nodes=31,learning_rate=.035,l2_regularization=2.5,random_state=s))
]
v98={1:56.67,2:35.09,3:24.35,4:19.93,5:17.61,6:15.06}
allbest={}
for R in range(1,7):
 y=gety(R); tr=np.arange(a)[y.iloc[:a].notna().to_numpy()]; va=np.arange(a,b)[y.iloc[a:b].notna().to_numpy()]; te=np.arange(b,n)[y.iloc[b:].notna().to_numpy()]
 print(f"\n===== {R}R ====="); best=None
 for name,mk in models:
  p=make_pipeline(SimpleImputer(strategy="median"),mk(700+R)); p.fit(X.iloc[tr],y.iloc[tr].astype(int))
  pv=p.predict_proba(X.iloc[va])[:,1]; pt=p.predict_proba(X.iloc[te])[:,1]; yy=y.iloc[te].to_numpy(); auc=roc_auc_score(yy,pt)
  print(f"{name} AUC={auc:.4f}",end="")
  for frac in [.03,.05,.075,.10,.15,.20,.30]:
   cut=np.quantile(pv,1-frac); z=pt>=cut; wr=np.nanmean(yy[z]) if z.sum() else np.nan
   print(f" | t{frac*100:g}% n={z.sum()} {wr*100:.1f}%",end="")
   if z.sum()>=75 and (best is None or wr>best[0]): best=(wr,z.sum(),name,frac,auc)
  print()
 allbest[R]=best
 if best: print(f"BEST {R}R={best[0]*100:.2f}% n={best[1]} {best[2]} top{best[3]*100:g}% | vs V98 {best[0]*100-v98[R]:+.2f}pp")
print("\n=== V100 SCORECARD ===")
for R,best in allbest.items():
 print(f"{R}R V98={v98[R]:.2f}% V100={best[0]*100:.2f}% CHANGE={best[0]*100-v98[R]:+.2f}pp")
print("\nDECISION RULE: if V100 does not show broad, material high-R improvement, STOP this modeling path and pivot to direct 1,911-vs-rejected-extreme forensic strategy discovery.")
