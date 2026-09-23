import pandas as pd, numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import roc_auc_score

print("=== RICH CAUSAL +2 SELECTOR — ATR + ORIGINAL ICON FEATURES ===")

base=pd.read_parquet("data/blind_plus2_filter_gap_audit.parquet").copy()
base["t"]=pd.to_datetime(base["t"],utc=True,errors="coerce")
base=base.sort_values("t").reset_index(drop=True)

# Add only causal features already built in prior research when available.
rich=pd.read_parquet("data/v99_causal_structure_liquidity_features.parquet").copy()
timecol=next((c for c in ["candidate_time","time","t","timestamp"] if c in rich.columns),None)
dircol=next((c for c in ["direction","dir","side"] if c in rich.columns),None)
if timecol is None or dircol is None:
    raise RuntimeError(f"Could not locate time/direction columns in V99. Columns: {list(rich.columns)[:30]}")
rich["_t"]=pd.to_datetime(rich[timecol],utc=True,errors="coerce")
rich["_dir"]=rich[dircol].astype(str).str.upper()

wanted=[
"atr","atr1","wick_percent","early_reclaim_atr","reclaim_x_wick",
"sweep_distance","sweep_distance_atr","cisd","cisd_by_1m","cisd_by_2m",
"choch","displacement","reversal_displacement","m1_move_atr","m2_move_atr",
"m1_close_pos","m2_close_pos","m1_dir_bars5","m2_dir_bars5"
]
# Also include causal numeric V99 structure/liquidity fields; exclude labels/outcomes/raw prices/IDs.
ban=("win","target","outcome","future","reference","is_ref","rr","label","entry","stop","pnl","profit","loss")
extra=[]
for c in rich.columns:
    if c in [timecol,dircol,"_t","_dir"]: continue
    if any(b in c.lower() for b in ban): continue
    if pd.api.types.is_numeric_dtype(rich[c]) and c not in extra: extra.append(c)
cols=list(dict.fromkeys([c for c in wanted if c in rich.columns]+extra))
print("Causal V99 numeric features available:",len(cols))

r=rich[["_t","_dir"]+cols].drop_duplicates(["_t","_dir"])
d=base.merge(r,left_on=["t","direction"],right_on=["_t","_dir"],how="left")
base_features=["rev0","rev1","rev2","range0","range1","range2","net_reversal_move","extreme_shift"]
features=base_features+cols
# remove constant / mostly missing
keep=[]
for c in features:
    s=pd.to_numeric(d[c],errors="coerce")
    if s.notna().mean()>=.50 and s.nunique(dropna=True)>1: keep.append(c)
features=keep
X=d[features].replace([np.inf,-np.inf],np.nan)
med=X.iloc[:int(len(X)*.70)].median(numeric_only=True)
X=X.fillna(med).fillna(0)
y=d.is_ref.astype(int)
cut=int(len(d)*.70)
m=ExtraTreesClassifier(n_estimators=700,min_samples_leaf=6,class_weight="balanced",random_state=42,n_jobs=-1,max_features="sqrt")
m.fit(X.iloc[:cut],y.iloc[:cut])
p=m.predict_proba(X.iloc[cut:])[:,1]
yt=y.iloc[cut:]
print("Rows:",len(d),"features:",len(features))
print("Train:",cut,"positives",int(y.iloc[:cut].sum()))
print("Unseen:",len(yt),"positives",int(yt.sum()))
print("AUC:",f"{roc_auc_score(yt,p):.4f}")
print("\nUNSEEN PRECISION / RECALL")
for pct in [20,10,5,3,2,1]:
    q=np.percentile(p,100-pct); z=p>=q
    purity=100*yt.to_numpy()[z].mean()
    recall=100*yt.to_numpy()[z].sum()/max(yt.sum(),1)
    print(f"TOP {pct:>2}% | signals={z.sum():4d} | purity={purity:6.2f}% | recall={recall:6.2f}%")
print("\nTOP FEATURES")
for f,v in sorted(zip(features,m.feature_importances_),key=lambda x:x[1],reverse=True)[:25]:
    print(f"{f}: {v:.4f}")
print("\nSelection test only; no RR optimization and no future outcome features.")
