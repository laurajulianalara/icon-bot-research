import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import roc_auc_score

print("=== RICH +2 SELECTOR — REBUILT DIRECTLY ON ALL 52K CANDIDATES ===")
base=pd.read_parquet("data/blind_plus2_filter_gap_audit.parquet").copy()
base["t"]=pd.to_datetime(base["t"],utc=True,errors="coerce")
base["direction"]=base.direction.astype(str).str.upper()
one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()
O,H,L,C=[one[x].astype(float).to_numpy() for x in ["open","high","low","close"]]
prev=np.r_[C[0],C[:-1]]
tr=np.maximum(H-L,np.maximum(abs(H-prev),abs(L-prev)))
ATR=pd.Series(tr).rolling(20,min_periods=5).mean().to_numpy()

rows=[]
for _,r in base.iterrows():
    i=idx.get(r.t)
    if i is None or i+2>=len(one): rows.append({}); continue
    j=i+2; a=ATR[j] if np.isfinite(ATR[j]) and ATR[j]>0 else np.nan
    s=1 if r.direction=="LONG" else -1
    z={}
    z["atr20"]=a
    # Candidate/+1/+2 movement normalized by ATR
    for q,k in enumerate([i,i+1,i+2]):
        rng=max(H[k]-L[k],.25)
        z[f"m{q}_range_atr"]=(H[k]-L[k])/a
        z[f"m{q}_body_atr"]=abs(C[k]-O[k])/a
        z[f"m{q}_reversal_close_pos"]=(C[k]-L[k])/rng if s==1 else (H[k]-C[k])/rng
        z[f"m{q}_reversal_body_atr"]=max((C[k]-O[k])*s,0)/a
    # Extreme/reclaim behavior through +2
    ext=min(L[i:j+1]) if s==1 else max(H[i:j+1])
    z["extreme_shift_atr"]=abs(ext-(L[i] if s==1 else H[i]))/a
    z["reclaim_atr"]=(C[j]-ext)/a if s==1 else (ext-C[j])/a
    # Wick at candidate
    rng0=max(H[i]-L[i],.25)
    z["wick_percent"]=((min(O[i],C[i])-L[i])/rng0) if s==1 else ((H[i]-max(O[i],C[i]))/rng0)
    z["reclaim_x_wick"]=z["reclaim_atr"]*z["wick_percent"]
    # Completed-only structure/liquidity pivots up to j-2
    lo=max(2,j-120); hi=j-2
    ph=[H[k] for k in range(lo,hi+1) if H[k]>H[k-1] and H[k]>=H[k+1]]
    pl=[L[k] for k in range(lo,hi+1) if L[k]<L[k-1] and L[k]<=L[k+1]]
    tol=.15*a
    z["equal_high_pairs"]=sum(abs(ph[p]-ph[q])<=tol for p in range(len(ph)) for q in range(p)) if len(ph)>1 else 0
    z["equal_low_pairs"]=sum(abs(pl[p]-pl[q])<=tol for p in range(len(pl)) for q in range(p)) if len(pl)>1 else 0
    z["nearest_swing_atr"]=(min([x-C[j] for x in ph if x>=C[j]],default=np.nan)/a) if s==-1 else (min([C[j]-x for x in pl if x<=C[j]],default=np.nan)/a)
    # Reversal displacement / delivery shift through +2
    bodies=np.abs(C-O); med=np.median(bodies[max(0,j-20):j+1])+1e-9
    rev=(C[i:j+1]-O[i:j+1])*s
    z["reversal_body_sum_3_atr"]=np.sum(np.maximum(rev,0))/a
    z["reversal_displacement_count_3"]=np.sum(rev>1.5*med)
    z["reversal_close_strength_3"]=(C[j]-C[i])*s/a
    # Simple causal CISD-like: reversal close crosses candidate open / prior opens
    z["cisd_candidate_open"]=int(C[j]>O[i]) if s==1 else int(C[j]<O[i])
    z["cisd_prior_open"]=int(C[j]>O[i+1]) if s==1 else int(C[j]<O[i+1])
    rows.append(z)

f=pd.DataFrame(rows)
d=pd.concat([base.reset_index(drop=True),f],axis=1)
basef=["rev0","rev1","rev2","range0","range1","range2","net_reversal_move","extreme_shift"]
new=list(f.columns); features=basef+new
print("Rows:",len(d),"rebuilt causal features:",len(new),"total:",len(features))
print("Median feature coverage:",f"{100*f.notna().mean().median():.2f}%")

X=d[features].replace([np.inf,-np.inf],np.nan)
cut=int(len(d)*.70); med=X.iloc[:cut].median(numeric_only=True)
X=X.fillna(med).fillna(0); y=d.is_ref.astype(int)
m=ExtraTreesClassifier(n_estimators=800,min_samples_leaf=6,class_weight="balanced",random_state=42,n_jobs=-1,max_features="sqrt")
m.fit(X.iloc[:cut],y.iloc[:cut]); p=m.predict_proba(X.iloc[cut:])[:,1]; yt=y.iloc[cut:]
print("Train:",cut,"positives",int(y.iloc[:cut].sum()))
print("Unseen:",len(yt),"positives",int(yt.sum()))
print("AUC:",f"{roc_auc_score(yt,p):.4f}")
print("\nUNSEEN PRECISION / RECALL")
for pct in [20,10,5,3,2,1]:
    q=np.percentile(p,100-pct); z=p>=q
    print(f"TOP {pct:>2}% | signals={z.sum():4d} | purity={100*yt.to_numpy()[z].mean():6.2f}% | recall={100*yt.to_numpy()[z].sum()/max(yt.sum(),1):6.2f}%")
print("\nTOP FEATURES")
for name,val in sorted(zip(features,m.feature_importances_),key=lambda x:x[1],reverse=True)[:25]:
    print(f"{name}: {val:.4f}")
d.to_parquet("data/rich_plus2_all_candidates.parquet",index=False)
print("\nSaved data/rich_plus2_all_candidates.parquet")
