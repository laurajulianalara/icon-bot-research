import pandas as pd
import numpy as np

print("=== V77 RR-BY-RR PRE-ENTRY WINNER/LOSER SIGNATURE STUDY ===")
d=pd.read_parquet("data/v76_preentry_feature_atlas.parquet")

exclude={"entry","risk","candidate_time","sample","session","direction"}
labels={f"win_{r}r" for r in range(1,7)}
features=[c for c in d.select_dtypes(include=np.number).columns if c not in exclude|labels]

rows=[]
for rr in range(1,7):
    y=f"win_{rr}r"
    for f in features:
        z=d[[f,y]].replace([np.inf,-np.inf],np.nan).dropna()
        if len(z)<100 or z[f].nunique()<3: continue
        w=z[z[y]==1][f]; l=z[z[y]==0][f]
        if len(w)<10 or len(l)<10: continue
        scale=z[f].quantile(.75)-z[f].quantile(.25)
        if not np.isfinite(scale) or scale==0: scale=z[f].std()
        sep=abs(w.median()-l.median())/(scale if scale and np.isfinite(scale) else 1)
        rows.append({"rr":rr,"feature":f,"winner_median":w.median(),"loser_median":l.median(),
                     "winner_mean":w.mean(),"loser_mean":l.mean(),"separation":sep})

res=pd.DataFrame(rows).sort_values(["rr","separation"],ascending=[True,False])
res.to_csv("data/v77_rr_feature_signatures.csv",index=False)

for rr in range(1,7):
    g=d
    print(f"\n--- 1:{rr} | {int(g[f'win_{rr}r'].sum())}W / {len(g)-int(g[f'win_{rr}r'].sum())}L ---")
    q=res[res.rr==rr].head(12)
    for _,x in q.iterrows():
        arrow="HIGHER" if x.winner_median>x.loser_median else "LOWER"
        print(f"{x.feature:24s} winners {arrow:6s} | W med {x.winner_median:.4f} | L med {x.loser_median:.4f} | sep {x.separation:.3f}")

# Stability: require the winner-vs-loser median direction to agree in BOTH historical samples.
stable=[]
for rr in range(1,7):
    y=f"win_{rr}r"
    for f in features:
        signs=[]
        for _,g in d.groupby("sample"):
            z=g[[f,y]].replace([np.inf,-np.inf],np.nan).dropna()
            w=z[z[y]==1][f]; l=z[z[y]==0][f]
            if len(w)<10 or len(l)<10: signs=[]; break
            delta=w.median()-l.median()
            signs.append(np.sign(delta))
        if len(signs)==2 and signs[0]!=0 and signs[0]==signs[1]:
            base=res[(res.rr==rr)&(res.feature==f)]
            if len(base):
                stable.append({"rr":rr,"feature":f,"direction":"HIGHER" if signs[0]>0 else "LOWER",
                               "separation":float(base.iloc[0].separation)})
stable=pd.DataFrame(stable).sort_values(["rr","separation"],ascending=[True,False])
stable.to_csv("data/v77_stable_signatures.csv",index=False)

print("\n=== STABLE ACROSS BOTH YEARS: TOP 10 PER RR ===")
for rr in range(1,7):
    print(f"\n1:{rr}")
    for _,x in stable[stable.rr==rr].head(10).iterrows():
        print(f"{x.feature:24s} {x.direction:6s} | sep {x.separation:.3f}")

print("\nSaved:")
print(" data/v77_rr_feature_signatures.csv")
print(" data/v77_stable_signatures.csv")
print("NEXT: convert only stable pre-entry signatures into threshold candidates and test them chronologically on ALL causal setups.")
