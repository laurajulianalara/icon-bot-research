import pandas as pd
import numpy as np
from itertools import combinations

IN="data/v5_structural_location_features.parquet"; OUT="data/v5_structural_interactions.csv"
d=pd.read_parquet(IN).sort_values("fill_time").reset_index(drop=True)
split=d.fill_time.min()+(d.fill_time.max()-d.fill_time.min())*.70
tr=d[d.fill_time<split].copy(); va=d[d.fill_time>=split].copy()
features=["approach_compression","approach_directional5","failed_cont_progress_atr","sr_touch_cluster",
"stretch20_atr","reclaim_prior_swing_atr","swept_prior_swing","sweep_depth2_atr","equal_liq_cluster",
"sr_dist_atr2","cisd","disp","confirm_minutes"]
conds=[]
for f in features:
    vals=tr[f].dropna()
    if vals.nunique()<=6:
        for v in sorted(vals.unique())[:-1]:
            conds += [(f,f"<={v:g}",lambda z,f=f,v=v:z[f]<=v),(f,f">{v:g}",lambda z,f=f,v=v:z[f]>v)]
    else:
        for q in [.2,.3,.4,.5,.6,.7,.8]:
            v=float(vals.quantile(q))
            conds += [(f,f"<={v:.4g}",lambda z,f=f,v=v:z[f]<=v),(f,f">={v:.4g}",lambda z,f=f,v=v:z[f]>=v)]

def st(z):
    n=len(z)
    if not n:return None
    wr=100*(z.outcome=="WIN").mean()
    return n,wr,5*(wr/100)-1

rows=[]
# 1, 2, and targeted 3-feature interactions. Thresholds learned only on training.
for size in [1,2,3]:
    combos=((i,) for i in range(len(conds))) if size==1 else combinations(range(len(conds)),size)
    checked=0
    for ids in combos:
        fs=[conds[i][0] for i in ids]
        if len(set(fs))<len(fs):continue
        checked+=1
        mt=np.ones(len(tr),bool); mv=np.ones(len(va),bool)
        labels=[]
        for i in ids:
            _,lab,fn=conds[i]; labels.append(lab); mt &= fn(tr).fillna(False).to_numpy(); mv &= fn(va).fillna(False).to_numpy()
        a=tr[mt];b=va[mv]
        mintr=50 if size<3 else 40; minva=20 if size<3 else 15
        if len(a)<mintr or len(b)<minva:continue
        sa,sb=st(a),st(b)
        rows.append((size," & ".join(labels),sa[0],sa[1],sa[2],sb[0],sb[1],sb[2],min(sa[1],sb[1])))
    print(f"Finished {size}-feature interactions: {checked:,}",flush=True)
r=pd.DataFrame(rows,columns=["n_features","rule","train_trades","train_wr","train_exp_r","valid_trades","valid_wr","valid_exp_r","robust_wr"])
r=r.sort_values(["robust_wr","valid_trades"],ascending=[False,False]).reset_index(drop=True);r.to_csv(OUT,index=False)
print("\n=== STRUCTURAL INTERACTIONS — TOP 50 ===")
print(r.head(50).round(2).to_string(index=False))
print("\n50%+ BOTH:",int(((r.train_wr>=50)&(r.valid_wr>=50)).sum()))
print("40%+ BOTH:",int(((r.train_wr>=40)&(r.valid_wr>=40)).sum()))
print("35%+ BOTH:",int(((r.train_wr>=35)&(r.valid_wr>=35)).sum()))
print("\nSaved:",OUT)
print("\nNEXT: if still weak, stop hand-built feature mining and compare actual winning/losing price sequences around the reversal (shape/trajectory clustering).")
