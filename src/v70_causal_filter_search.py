import pandas as pd
import numpy as np

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
d=pd.read_parquet("data/v68_full_causal_feature_table.parquet").copy()
for x in (one,d): x["time_ny" if "time_ny" in x.columns else "candidate_time"]=pd.to_datetime(x["time_ny" if "time_ny" in x.columns else "candidate_time"])

q=d[(d.m1_move_atr<=.300)&(d.m1_close_pos>=.140)&(d.m2_close_pos<=.80)&
    (d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)&
    (d.early_reclaim_atr<=.90)&
    ((d.early_reclaim_atr<.576132)|(d.reclaim_x_wick<.183258))].copy()

idx=pd.Series(one.index,index=one.time_ny).to_dict()

# Score actual 4R outcome causally for each setup.
outs=[]
for _,r in q.iterrows():
    i=idx.get(r.candidate_time)
    if i is None or i+3>=len(one): outs.append(np.nan); continue
    j=i+3; entry=float(one.iloc[j].open)
    stop=float(r.extreme)-.25 if r.direction=="LONG" else float(r.extreme)+.25
    risk=entry-stop if r.direction=="LONG" else stop-entry
    if risk<=0: outs.append(np.nan); continue
    target=entry+4*risk if r.direction=="LONG" else entry-4*risk
    out=0
    for k in range(j,min(j+241,len(one))):
        b=one.iloc[k]
        if r.direction=="LONG":
            if b.low<=stop: out=-1; break
            if b.high>=target: out=1; break
        else:
            if b.high>=stop: out=-1; break
            if b.low<=target: out=1; break
    outs.append(out)
q["out4"]=outs
q=q[q.out4!=0].copy()

features=["early_reclaim_atr","wick_percent","reclaim_x_wick","m2_close_pos","m2_move_atr"]
thresholds={f:sorted(set(float(q[f].quantile(x)) for x in [.2,.3,.4,.5,.6,.7,.8])) for f in features}

results=[]
# One-feature and two-feature AND screens. Discovery only; validation comes next.
masks=[]
for f in features:
    for t in thresholds[f]:
        masks.append((f"{f}>={t:.5f}",q[f]>=t))
        masks.append((f"{f}<={t:.5f}",q[f]<=t))
for name,m in masks:
    n=int(m.sum())
    if n>=300:
        w=int((q.loc[m,"out4"]==1).sum()); l=n-w
        results.append((100*w/n,n,w,l,name))
for a in range(len(masks)):
    for b in range(a+1,len(masks)):
        name1,m1=masks[a]; name2,m2=masks[b]
        m=m1&m2; n=int(m.sum())
        if n>=300:
            w=int((q.loc[m,"out4"]==1).sum()); l=n-w
            results.append((100*w/n,n,w,l,name1+" AND "+name2))

print("=== CAUSAL FILTER SEARCH — ACTUAL 4R OUTCOMES ===")
print("Resolved causal setups:",len(q))
basew=int((q.out4==1).sum())
print(f"Baseline: {basew}W / {len(q)-basew}L | {100*basew/len(q):.2f}%")
print()
print("TOP DISCOVERY SCREENS (min 300 trades)")
for wr,n,w,l,name in sorted(results,reverse=True)[:30]:
    print(f"{wr:6.2f}% | n={n:4d} | {w}W/{l}L | {name}")
print()
print("These are discovery results, NOT final strategy results. Any promising screen must pass chronological train/holdout validation next.")
