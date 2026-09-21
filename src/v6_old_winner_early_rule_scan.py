import pandas as pd
import numpy as np
from itertools import product

IN="data/v6_old_winner_early_signature.csv"; OUT="data/v6_old_winner_early_rules.csv"
d=pd.read_csv(IN)
# First 60% discovery, next 20% validation, final 20% untouched test.
d["candidate_time"]=pd.to_datetime(d.candidate_time);d=d.sort_values("candidate_time").reset_index(drop=True)
n=len(d); a=d.iloc[:int(n*.60)]; b=d.iloc[int(n*.60):int(n*.80)]; c=d.iloc[int(n*.80):]
features=["m1_body_atr","m1_move_atr","m1_close_pos","m1_dir_bars5",
"m2_body_atr","m2_move_atr","m2_close_pos","m2_dir_bars5",
"m3_body_atr","m3_move_atr","m3_close_pos","m3_dir_bars5"]
# thresholds learned ONLY from discovery period
conds=[]
for f in features:
    for q in [.2,.3,.4,.5,.6,.7,.8]:
        v=float(a[f].quantile(q))
        conds.append((f,f"{f}<={v:.3f}",lambda z,f=f,v=v:z[f]<=v))
        conds.append((f,f"{f}>={v:.3f}",lambda z,f=f,v=v:z[f]>=v))

def met(z):
    return len(z),100*z.old_win.mean() if len(z) else np.nan
rows=[]
# Test singles, pairs, and triples. Require enough samples in every chronological segment.
for size in [1,2,3]:
    if size==1:
        combos=((i,) for i in range(len(conds)))
    else:
        import itertools
        combos=itertools.combinations(range(len(conds)),size)
    checked=0
    for ids in combos:
        fs=[conds[i][0] for i in ids]
        if len(set(fs))<size:continue
        checked+=1
        masks=[]
        labels=[]
        for z in [a,b,c]:
            m=np.ones(len(z),bool)
            for i in ids:
                _,lab,fn=conds[i];m &= fn(z).fillna(False).to_numpy()
            masks.append(m)
        za,zb,zc=a[masks[0]],b[masks[1]],c[masks[2]]
        mins=(12,5,5) if size<3 else (10,4,4)
        if len(za)<mins[0] or len(zb)<mins[1] or len(zc)<mins[2]:continue
        ma,mb,mc=met(za),met(zb),met(zc)
        rule=" & ".join(conds[i][1] for i in ids)
        rows.append((size,rule,ma[0],ma[1],mb[0],mb[1],mc[0],mc[1],min(ma[1],mb[1],mc[1])))
    print(f"Finished {size}-feature rules: {checked:,}",flush=True)
r=pd.DataFrame(rows,columns=["n","rule","discovery_trades","discovery_wr","validation_trades","validation_wr","test_trades","test_wr","robust_wr"])
r=r.sort_values(["robust_wr","test_trades"],ascending=[False,False]).reset_index(drop=True);r.to_csv(OUT,index=False)
print("\n=== EARLY SIGNATURE RULES — TOP 40 ===")
print(r.head(40).round(2).to_string(index=False))
print("\n50%+ ALL 3 PERIODS:",int(((r.discovery_wr>=50)&(r.validation_wr>=50)&(r.test_wr>=50)).sum()))
print("55%+ ALL 3 PERIODS:",int(((r.discovery_wr>=55)&(r.validation_wr>=55)&(r.test_wr>=55)).sum()))
print("\nSaved:",OUT)
