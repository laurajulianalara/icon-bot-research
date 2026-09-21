import pandas as pd
import numpy as np
from itertools import combinations

IN="data/v5_winner_mining_features.parquet"
OUT="data/v5_winner_interactions.csv"
d=pd.read_parquet(IN).sort_values("fill_time").reset_index(drop=True)
split=d.fill_time.min()+(d.fill_time.max()-d.fill_time.min())*.70
features=["disp","extreme_progress_atr","approach5_atr","cisd","approach3_atr","confirm_minutes",
          "distance_equilibrium_atr","sweep","rejection_eff","pre5_directional_bars"]
# Learn cut points ONLY from training data. Each condition is then frozen and tested on later validation.
tr=d[d.fill_time<split]
conds=[]
for f in features:
    vals=tr[f].dropna()
    for q in [.2,.3,.4,.5,.6,.7,.8]:
        v=float(vals.quantile(q))
        conds.append((f,f"<={v:.4g}",lambda x,f=f,v=v:x[f]<=v))
        conds.append((f,f">={v:.4g}",lambda x,f=f,v=v:x[f]>=v))

def stats(x):
    if len(x)==0:return None
    return len(x),100*(x.outcome=="WIN").mean(),4*(x.outcome=="WIN").mean()-1*(x.outcome=="LOSS").mean()

rows=[]
# Single features first
for f,label,fn in conds:
    a=tr[fn(tr)]; b=d[(d.fill_time>=split)&fn(d)]
    if len(a)>=60 and len(b)>=25:
        sa,sb=stats(a),stats(b)
        rows.append(("1",label,"",sa[0],sa[1],sa[2],sb[0],sb[1],sb[2],min(sa[1],sb[1])))
# Pair interactions, excluding two cuts of same feature
for i,j in combinations(range(len(conds)),2):
    f1,l1,a1=conds[i]; f2,l2,a2=conds[j]
    if f1==f2:continue
    mt=a1(tr)&a2(tr); mv=a1(d)&a2(d)&(d.fill_time>=split)
    a=tr[mt];b=d[mv]
    if len(a)<60 or len(b)<25:continue
    sa,sb=stats(a),stats(b)
    rows.append(("2",l1,l2,sa[0],sa[1],sa[2],sb[0],sb[1],sb[2],min(sa[1],sb[1])))
r=pd.DataFrame(rows,columns=["n_features","rule1","rule2","train_trades","train_wr","train_exp_r","valid_trades","valid_wr","valid_exp_r","robust_wr"])
r=r.sort_values(["robust_wr","valid_trades"],ascending=[False,False]).reset_index(drop=True)
r.to_csv(OUT,index=False)
print("\n=== WINNER-MINING INTERACTIONS — TOP 40 ===")
print(r.head(40).round(2).to_string(index=False))
print("\n50%+ BOTH train/validation:",int(((r.train_wr>=50)&(r.valid_wr>=50)).sum()))
print("40%+ BOTH train/validation:",int(((r.train_wr>=40)&(r.valid_wr>=40)).sum()))
print("\nSaved:",OUT)
print("\nNOTE: If these remain weak, the current numeric features do not explain the winners. Next step is richer structural/location features rather than more threshold tuning.")
