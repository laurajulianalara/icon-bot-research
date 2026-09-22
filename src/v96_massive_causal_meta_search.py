import pandas as pd, numpy as np
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier, RandomForestRegressor, ExtraTreesRegressor
from sklearn.metrics import roc_auc_score

print("=== V96 MASSIVE CAUSAL META SEARCH ===")
x=pd.read_parquet("data/v88_full_rich_causal_features.parquet").copy()
rr=pd.read_parquet("data/v79_full_causal_rr_outcomes.parquet").copy()
def tc(d): return next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in d.columns)
xt,rt=tc(x),tc(rr)
x["_t"]=pd.to_datetime(x[xt],utc=True,errors="coerce"); rr["_t"]=pd.to_datetime(rr[rt],utc=True,errors="coerce")
keys=["_t"]+[k for k in ["direction","extreme"] if k in x.columns and k in rr.columns]
rrcols=[c for c in rr.columns if c.startswith("win_") or c.startswith("resolved_")]
d=x.merge(rr[keys+rrcols].drop_duplicates(keys),on=keys,how="left").sort_values("_t").reset_index(drop=True)
ban=("win_","resolved_","outcome","target","exit","future","next_","hindsight","invalid","_row")
skip={xt,"_t","entry","risk"}
features=[c for c in d.columns if c not in skip and not any(z in c.lower() for z in ban) and pd.api.types.is_numeric_dtype(d[c]) and d[c].notna().sum()>1000]
for c in ["session","direction"]:
    if c in d:
        z=pd.get_dummies(d[c].astype(str),prefix=c,dtype=int); d=pd.concat([d,z],axis=1); features+=list(z.columns)
X=d[features].replace([np.inf,-np.inf],np.nan)
n=len(d); a=int(n*.60); b=int(n*.80)
print("Rows",n,"features",len(features),"train/val/test",a,b-a,n-b)

def label(R):
 c=next((c for c in d.columns if c.lower() in [f"win_{R}r",f"win{R}r",f"{R}r_win"]),None)
 return pd.to_numeric(d[c],errors="coerce") if c else None

# Multi-R expectancy target: maximum R reached before stop, capped 6.
ys=[label(r) for r in range(1,7)]
travel=np.zeros(n,float)
for r,y in enumerate(ys,1):
 if y is not None: travel=np.where(y.fillna(0).to_numpy()>0,r,travel)
# Utility favors setups that travel far, but penalizes immediate failure.
utility=travel.copy(); utility[travel==0]=-1

models=[
 ("ET_d10_l10",ExtraTreesRegressor(n_estimators=700,max_depth=10,min_samples_leaf=10,n_jobs=-1,random_state=1)),
 ("ET_d16_l20",ExtraTreesRegressor(n_estimators=700,max_depth=16,min_samples_leaf=20,n_jobs=-1,random_state=2)),
 ("RF_d12_l15",RandomForestRegressor(n_estimators=500,max_depth=12,min_samples_leaf=15,n_jobs=-1,random_state=3,max_features=.8)),
]
preds=[]
for name,m in models:
 p=make_pipeline(SimpleImputer(strategy="median"),m); p.fit(X.iloc[:a],utility[:a])
 pv=p.predict(X.iloc[a:b]); pt=p.predict(X.iloc[b:]); preds.append((name,pv,pt))
 print("\nMODEL",name)
 for frac in [.05,.10,.15,.20,.30]:
  cut=np.quantile(pv,1-frac); zv=pv>=cut; zt=pt>=cut
  print(f" top~{int(frac*100):2d}% test_n={zt.sum():4d}",end="")
  for R in [1,2,3,4,5,6]:
   y=ys[R-1]; arr=y.iloc[b:].to_numpy(); ok=zt & ~pd.isna(arr)
   if ok.sum(): print(f" {R}R={np.nanmean(arr[ok])*100:5.1f}%",end="")
  print()

# Ensemble rank of all models; select thresholds only from validation.
def rank01(v):
 return pd.Series(v).rank(pct=True).to_numpy()
rv=np.mean([rank01(pv) for _,pv,_ in preds],axis=0)
rt=np.mean([rank01(pt) for _,_,pt in preds],axis=0)
print("\nENSEMBLE RANK — FINAL UNSEEN TEST")
for frac in [.03,.05,.075,.10,.15,.20,.25,.30]:
 cut=np.quantile(rv,1-frac); z=rt>=cut
 print(f"top {frac*100:4.1f}% n={z.sum():4d}",end="")
 for R in range(1,7):
  arr=ys[R-1].iloc[b:].to_numpy(); ok=z & ~pd.isna(arr)
  print(f" {R}R={np.nanmean(arr[ok])*100:5.1f}%",end="")
 print()
out=d.iloc[b:][keys].copy(); out["meta_score"]=rt
for R in range(1,7): out[f"win_{R}r"]=ys[R-1].iloc[b:].to_numpy()
out.to_csv("data/v96_meta_search_test.csv",index=False)
print("\nSaved data/v96_meta_search_test.csv")
print("NEXT: if no high-R lift appears, current pre-entry feature set does not contain enough causal information; next rebuild must focus on richer price-path/liquidity/CISD state, not model tuning.")
