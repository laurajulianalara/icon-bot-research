import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier, ExtraTreesRegressor
from sklearn.metrics import roc_auc_score

print("=== V98 LARGE RICH CAUSAL SEARCH ===")
d=pd.read_parquet("data/v97_rich_market_state_features.parquet").copy()
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
ys={r:gety(r) for r in range(1,7)}
models=[
 ("ET",lambda seed:ExtraTreesClassifier(n_estimators=700,max_depth=16,min_samples_leaf=12,n_jobs=-1,class_weight="balanced",random_state=seed)),
 ("RF",lambda seed:RandomForestClassifier(n_estimators=500,max_depth=14,min_samples_leaf=15,n_jobs=-1,class_weight="balanced",max_features=.65,random_state=seed)),
 ("HGB",lambda seed:HistGradientBoostingClassifier(max_iter=400,max_leaf_nodes=31,learning_rate=.04,l2_regularization=2.0,random_state=seed))
]
summary=[]
for R in range(1,7):
 y=ys[R]; tr=np.arange(a)[y.iloc[:a].notna().to_numpy()]; va=np.arange(a,b)[y.iloc[a:b].notna().to_numpy()]; te=np.arange(b,n)[y.iloc[b:].notna().to_numpy()]
 print(f"\n===== {R}R =====")
 best=None
 for name,mk in models:
  p=make_pipeline(SimpleImputer(strategy="median"),mk(100+R)); p.fit(X.iloc[tr],y.iloc[tr].astype(int))
  pv=p.predict_proba(X.iloc[va])[:,1]; pt=p.predict_proba(X.iloc[te])[:,1]; yy=y.iloc[te].to_numpy()
  auc=roc_auc_score(yy,pt)
  print(f"{name} AUC={auc:.4f}",end="")
  for frac in [.05,.10,.20]:
   cut=np.quantile(pv,1-frac); z=pt>=cut
   wr=np.nanmean(yy[z]) if z.sum() else np.nan
   print(f" | top{int(frac*100)} n={z.sum()} WR={wr*100:.2f}%",end="")
   score=(wr,z.sum(),name,frac,auc)
   if best is None or (np.isfinite(wr) and wr>best[0]): best=score
  print()
 print("BEST",best); summary.append((R,)+best)
print("\n=== BEST BY RR ===")
for z in summary: print(f"{z[0]}R bestWR={z[1]*100:.2f}% n={z[2]} model={z[3]} band=top{int(z[4]*100)}% AUC={z[5]:.4f}")
print("\nBENCHMARK TARGETS: 1R~97% 2R~87% 3R~75% 4R~65% 5R~57% 6R~51%")
print("NEXT: if high-R lift is still weak, rebuild actual CISD/liquidity/session-state mechanics rather than add more generic price statistics.")
