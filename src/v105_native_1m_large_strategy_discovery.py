import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
print("=== V105 NATIVE 1M LARGE STRATEGY DISCOVERY ===")
m=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
c=pd.read_parquet("data/v102_1m_cisd_choch_liquidity_forensics.parquet").copy()
tc="time_ny" if "time_ny" in m.columns else next(x for x in m if "time" in x.lower())
m["_t"]=pd.to_datetime(m[tc],utc=True,errors="coerce"); m=m.dropna(subset=["_t"]).sort_values("_t").drop_duplicates("_t").reset_index(drop=True)
c["candidate_time"]=pd.to_datetime(c.candidate_time,utc=True)
idx=pd.Series(np.arange(len(m)),index=m["_t"])
O,H,L,C=[m[x].astype(float).to_numpy() for x in ["open","high","low","close"]]; V=m["volume"].astype(float).to_numpy() if "volume" in m else np.zeros(len(m))
prev=np.r_[C[0],C[:-1]]; TR=np.maximum(H-L,np.maximum(abs(H-prev),abs(L-prev))); ATR=pd.Series(TR).rolling(20,min_periods=5).mean().to_numpy()
rows=[]
for _,r in c.iterrows():
 j=idx.get(r.candidate_time,None)
 if j is None or j<65 or j+1>=len(m): continue
 j=int(j); s=1 if r.direction=="LONG" else -1; a=ATR[j] if np.isfinite(ATR[j]) and ATR[j]>0 else 1.
 z={"candidate_time":r.candidate_time,"direction":r.direction,"extreme":float(r.extreme)}
 # candidate-time only features
 z.update(swept_liquidity=float(r.swept_liquidity),sweep_reclaimed=float(r.sweep_reclaimed),sweep_depth_atr=float(r.sweep_depth_atr),structure_distance_atr=float(r.structure_distance_atr) if pd.notna(r.structure_distance_atr) else np.nan)
 rng=max(H[j]-L[j],.25); z["bar_body_pct"]=abs(C[j]-O[j])/rng; z["close_reversal_pos"]=(C[j]-L[j])/rng if s==1 else (H[j]-C[j])/rng
 z["candidate_range_atr"]=rng/a; z["candidate_body_atr"]=abs(C[j]-O[j])/a
 for w in [2,3,5,8,13,21,34,55]:
  q=j-w+1
  z[f"ret_{w}_atr"]=s*(C[j]-C[q])/a
  z[f"range_{w}_atr"]=(H[q:j+1].max()-L[q:j+1].min())/a
  z[f"eff_{w}"]=abs(C[j]-C[q])/(np.abs(np.diff(C[q:j+1])).sum()+.25)
  z[f"dirbars_{w}"]=np.mean(np.sign(C[q:j+1]-O[q:j+1])==s)
  z[f"volrel_{w}"]=V[j]/(np.mean(V[q:j+1])+1) if V.any() else 0
 # strictly past relative position
 for w in [5,10,20,40,60]:
  q=j-w
  hi=H[q:j].max(); lo=L[q:j].min(); z[f"pastpos_{w}"]=(C[j]-lo)/(hi-lo+.25)
  z[f"extension_{w}_atr"]=((L[q:j].min()-L[j]) if s==1 else (H[j]-H[q:j].max()))/a
 # forward RR labels only, never predictors; next 1m open, stop extreme +/- tick, conservative stop-first
 entry=O[j+1]; stop=float(r.extreme)+(.25 if s==-1 else -.25); risk=abs(entry-stop)
 for R in range(1,7):
  target=entry+s*R*risk; y=0
  for q in range(j+1,min(len(m),j+242)):
   hs=(L[q]<=stop) if s==1 else (H[q]>=stop); ht=(H[q]>=target) if s==1 else (L[q]<=target)
   if hs: y=0; break
   if ht: y=1; break
  z[f"win_{R}R"]=y
 rows.append(z)
d=pd.DataFrame(rows).sort_values("candidate_time").reset_index(drop=True)
features=[x for x in d if x not in ["candidate_time","direction","extreme"] and not x.startswith("win_")]
features=[x for x in features if d[x].notna().mean()>.95]
X=d[features].replace([np.inf,-np.inf],np.nan).fillna(0)
n=len(d); a=int(n*.60); b=int(n*.80)
print("Rows",n,"features",len(features),"train/val/test",a,b-a,n-b)
models={"ET":ExtraTreesClassifier(n_estimators=350,min_samples_leaf=20,max_features=.7,n_jobs=-1,random_state=42,class_weight="balanced"),
"RF":RandomForestClassifier(n_estimators=300,min_samples_leaf=20,max_features=.7,n_jobs=-1,random_state=42,class_weight="balanced_subsample"),
"HGB":HistGradientBoostingClassifier(max_iter=250,max_leaf_nodes=15,l2_regularization=2,random_state=42)}
for R in range(1,7):
 y=d[f"win_{R}R"].astype(int); best=None
 for name,model in models.items():
  model.fit(X.iloc[:a],y.iloc[:a]); pv=model.predict_proba(X.iloc[a:b])[:,1]
  for pct in [70,80,85,90,92,94,95,96,97,98,99]:
   th=np.percentile(pv,pct); mask=pv>=th
   if mask.sum()<75: continue
   wr=y.iloc[a:b][mask].mean(); score=wr*np.sqrt(mask.sum())
   if best is None or score>best[0]: best=(score,name,model,th,wr,mask.sum(),pct)
 if best:
  _,name,model,th,vwr,vn,pct=best; pt=model.predict_proba(X.iloc[b:])[:,1]; mt=pt>=th
  twr=y.iloc[b:][mt].mean() if mt.sum() else 0
  print(f"{R}R {name} val={vwr*100:5.2f}% n={vn:4d} | TEST={twr*100:5.2f}% n={mt.sum():4d} cutoff_pctl={pct}")
print("Saved data/v105_native_1m_discovery_dataset.parquet")
d.to_parquet("data/v105_native_1m_discovery_dataset.parquet",index=False)
print("NEXT: V106 will take only genuinely improved unseen-test regions and run sequential equity/DD validation; if high-R remains weak, we change the entry/stop architecture rather than keep filtering.")
