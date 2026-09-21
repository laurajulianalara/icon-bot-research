import pandas as pd
import numpy as np

SIG="data/v6_old_winner_early_signature.csv"
RULES="data/v6_early_rule_robustness.csv"
OUT="data/v6_walkforward_shortlist.csv"

d=pd.read_csv(SIG); d["candidate_time"]=pd.to_datetime(d.candidate_time,utc=True); d=d.sort_values("candidate_time").reset_index(drop=True)
r=pd.read_csv(RULES).drop_duplicates("rule")
# Prefer rules with real coverage and stability, not tiny high-WR cells.
r=r[(r.total_trades>=50)&(r.robust_wr>=55)&(r.spread<=12)].head(300).copy()

def apply_rule(z,rule):
    m=np.ones(len(z),dtype=bool)
    for part in rule.split(" & "):
        if "<=" in part:
            f,v=part.split("<="); m &= (z[f].to_numpy()<=float(v))
        elif ">=" in part:
            f,v=part.split(">="); m &= (z[f].to_numpy()>=float(v))
    return z[m]

rows=[]
# 5 chronological folds: rule must survive every slice, not just 3 coarse buckets.
idx_folds=np.array_split(np.arange(len(d)),5)
folds=[d.iloc[idx].copy() for idx in idx_folds]
for _,x in r.iterrows():
    stats=[]; ok=True
    for k,z in enumerate(folds,1):
        q=apply_rule(z,x.rule)
        if len(q)<5: ok=False; break
        stats.append((len(q),100*q.old_win.mean()))
    if not ok: continue
    wr=[v for _,v in stats]; nt=[n for n,_ in stats]
    rows.append((x.rule,sum(nt),sum(n*w for n,w in stats)/sum(nt),min(wr),max(wr)-min(wr),*sum(([n,w] for n,w in stats),[])))
cols=["rule","trades","wr","worst_fold_wr","fold_spread"]
for k in range(1,6): cols += [f"fold{k}_trades",f"fold{k}_wr"]
o=pd.DataFrame(rows,columns=cols).sort_values(["worst_fold_wr","trades"],ascending=[False,False])
o.to_csv(OUT,index=False)
print("Rules entering 5-fold stress test:",len(r))
print("Rules surviving minimum 5 trades in every fold:",len(o))
print("\n=== 5-FOLD WALK-FORWARD SHORTLIST ===")
print(o.head(30).round(2).to_string(index=False))
print("\n50%+ in EVERY fold:",int((o.worst_fold_wr>=50).sum()))
print("55%+ in EVERY fold:",int((o.worst_fold_wr>=55).sum()))
print("\nSaved:",OUT)
