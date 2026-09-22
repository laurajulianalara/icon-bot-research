import pandas as pd
import numpy as np

d=pd.read_parquet("data/v68_full_causal_feature_table.parquet")
q=d[(d.m1_move_atr<=.300)&(d.m1_close_pos>=.140)&(d.m2_close_pos<=.80)&
    (d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)&
    (d.early_reclaim_atr<=.90)&
    ((d.early_reclaim_atr<.576132)|(d.reclaim_x_wick<.183258))].copy()

features=["early_reclaim_atr","early_adverse_atr","wick_percent","reclaim_x_wick",
          "m1_move_atr","m1_close_pos","m2_move_atr","m2_close_pos",
          "m1_dir_bars5","m2_dir_bars5"]

print("=== PRE-ENTRY SEPARATOR STUDY ===")
print("Population:",len(q),"| kept:",int(q.hindsight_kept.sum()),"| rejected:",int((~q.hindsight_kept).sum()))
print()
print("FEATURE MEDIANS / MEANS")
for f in features:
    a=pd.to_numeric(q.loc[q.hindsight_kept,f],errors="coerce").dropna()
    b=pd.to_numeric(q.loc[~q.hindsight_kept,f],errors="coerce").dropna()
    if len(a) and len(b):
        medgap=abs(a.median()-b.median())
        pooled=np.nanstd(pd.concat([a,b]).to_numpy())
        score=medgap/pooled if pooled>0 else 0
        print(f"{f:22s} kept med={a.median():8.4f} reject med={b.median():8.4f} | kept mean={a.mean():8.4f} reject mean={b.mean():8.4f} | sep={score:.3f}")

print()
print("KEEP RATE BY SESSION")
print((q.groupby("session").hindsight_kept.mean()*100).round(2).to_string())
print()
print("KEEP RATE BY DIRECTION")
print((q.groupby("direction").hindsight_kept.mean()*100).round(2).to_string())

# Simple single-feature quantile screens, discovery only.
print()
print("BEST SIMPLE PRE-ENTRY SCREENS (DISCOVERY ONLY)")
out=[]
for f in features:
    x=pd.to_numeric(q[f],errors="coerce")
    for quant in [.1,.2,.3,.4,.5,.6,.7,.8,.9]:
        t=x.quantile(quant)
        for op in ("<=",">="):
            mask=x<=t if op=="<=" else x>=t
            n=int(mask.sum())
            if n<200: continue
            kr=100*q.loc[mask,"hindsight_kept"].mean()
            out.append((kr,n,f,op,float(t)))
for kr,n,f,op,t in sorted(out,reverse=True)[:20]:
    print(f"{f} {op} {t:.5f} | n={n} | hindsight-keep rate={kr:.2f}%")

print()
print("These screens are NOT strategy results. They identify live-observable variables worth testing next on actual trade outcomes.")
