import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import roc_auc_score

print("=== RICH +2 SELECTOR FIXED JOIN — ATR + V99 CAUSAL FEATURES ===")
base=pd.read_parquet("data/blind_plus2_filter_gap_audit.parquet").copy()
base["t"]=pd.to_datetime(base["t"],utc=True,errors="coerce")
base["direction"]=base["direction"].astype(str).str.upper()
base=base.sort_values("t").reset_index(drop=True)

rich=pd.read_parquet("data/v99_causal_structure_liquidity_features.parquet").copy()
timecol=next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in rich.columns)
rich["_t"]=pd.to_datetime(rich[timecol],utc=True,errors="coerce")
rich["_dir"]=rich["direction"].astype(str).str.upper()

ban=("win","target","outcome","future","reference","is_ref","rr","label","entry","stop","pnl","profit","loss")
idcols={timecol,"_t","_dir"}
num=[c for c in rich.columns if c not in idcols and pd.api.types.is_numeric_dtype(rich[c]) and not any(b in c.lower() for b in ban)]
r=rich[["_t","_dir"]+num].drop_duplicates(["_t","_dir"])
d=base.merge(r,left_on=["t","direction"],right_on=["_t","_dir"],how="left")

basef=["rev0","rev1","rev2","range0","range1","range2","net_reversal_move","extreme_shift"]
features=[]
for c in basef+num:
    s=pd.to_numeric(d[c],errors="coerce")
    if s.notna().mean()>=.50 and s.nunique(dropna=True)>1: features.append(c)

print("Rows:",len(d))
print("V99 numeric candidates:",len(num))
print("Usable merged features:",len(features))
print("Rows with any V99 feature:",int(d[num].notna().any(axis=1).sum()),"/",len(d))
if len(features)<=8:
    raise RuntimeError("V99 features still did not join. Stop here; do not report this as a rich-feature test.")

X=d[features].replace([np.inf,-np.inf],np.nan)
cut=int(len(d)*.70)
med=X.iloc[:cut].median(numeric_only=True)
X=X.fillna(med).fillna(0)
y=d.is_ref.astype(int)
m=ExtraTreesClassifier(n_estimators=700,min_samples_leaf=6,class_weight="balanced",random_state=42,n_jobs=-1,max_features="sqrt")
m.fit(X.iloc[:cut],y.iloc[:cut])
p=m.predict_proba(X.iloc[cut:])[:,1]; yt=y.iloc[cut:]
print("Train:",cut,"positives",int(y.iloc[:cut].sum()))
print("Unseen:",len(yt),"positives",int(yt.sum()))
print("AUC:",f"{roc_auc_score(yt,p):.4f}")
print("\nUNSEEN PRECISION / RECALL")
for pct in [20,10,5,3,2,1]:
    q=np.percentile(p,100-pct); z=p>=q
    print(f"TOP {pct:>2}% | signals={z.sum():4d} | purity={100*yt.to_numpy()[z].mean():6.2f}% | recall={100*yt.to_numpy()[z].sum()/max(yt.sum(),1):6.2f}%")
print("\nTOP FEATURES")
for f,v in sorted(zip(features,m.feature_importances_),key=lambda x:x[1],reverse=True)[:25]:
    print(f"{f}: {v:.4f}")
print("\nThis is the first valid rich-feature selector test only if usable merged features > 8.")
