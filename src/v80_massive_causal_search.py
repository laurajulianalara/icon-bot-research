import pandas as pd
import numpy as np
from itertools import combinations

print("=== V80 MASSIVE CAUSAL SEARCH ===")
d=pd.read_parquet("data/v79_full_causal_rr_outcomes.parquet").copy()
atlas=pd.read_parquet("data/v76_preentry_feature_atlas.parquet")
stable=pd.read_csv("data/v77_stable_signatures.csv")

timecol="t_utc" if "t_utc" in d.columns else next(c for c in ["candidate_time","time","candidate_time_et"] if c in d.columns)
d[timecol]=pd.to_datetime(d[timecol],utc=True,errors="coerce")
d=d.sort_values(timecol).reset_index(drop=True)

common=[f for f in stable.feature.unique() if f in d.columns and f in atlas.columns]
print("Causal features:",common)

allrows=[]
for rr in range(1,7):
    y=f"win_{rr}r"
    s=stable[stable.rr==rr].sort_values("separation",ascending=False)
    rules=[]
    for _,z in s.iterrows():
        f=z.feature
        if f not in common: continue
        # broad threshold grid learned from reference sample only
        for q in np.arange(.10,.91,.05):
            th=float(pd.to_numeric(atlas[f],errors="coerce").quantile(q))
            rules.append((f,z.direction,float(q),th))
    combos=[]
    combos.extend((x,) for x in rules)
    combos.extend(combinations(rules,2))
    combos.extend(combinations(rules,3))
    seen=set(); tested=0
    for combo in combos:
        fs=[x[0] for x in combo]
        if len(set(fs))!=len(fs): continue
        key=tuple(sorted((f,di,round(th,8)) for f,di,q,th in combo))
        if key in seen: continue
        seen.add(key); tested+=1
        m=np.ones(len(d),dtype=bool)
        desc=[]
        for f,di,q,th in combo:
            v=pd.to_numeric(d[f],errors="coerce").to_numpy()
            m &= (v>=th) if di=="HIGHER" else (v<=th)
            desc.append(f"{f}{'>=' if di=='HIGHER' else '<='}{th:.6g}")
        ids=np.flatnonzero(m & d[y].notna().to_numpy())
        if len(ids)<400: continue
        # chronological thirds: rule must not collapse in any period
        chunks=np.array_split(ids,3)
        wrs=[100*pd.to_numeric(d.loc[c,y]).mean() for c in chunks if len(c)]
        wr=100*pd.to_numeric(d.loc[ids,y]).mean()
        worst=min(wrs)
        allrows.append({"rr":rr,"trades":len(ids),"wr":wr,"worst_third_wr":worst,
                        "third1":wrs[0],"third2":wrs[1],"third3":wrs[2],
                        "rules":" AND ".join(desc)})
    print(f"1:{rr} unique combinations tested: {tested}")

res=pd.DataFrame(allrows)
# Stability first, then overall WR; avoids returning a one-period fluke.
res=res.sort_values(["rr","worst_third_wr","wr","trades"],ascending=[True,False,False,False])
res.to_csv("data/v80_massive_causal_search.csv",index=False)

print("\n=== BEST STABLE CAUSAL VARIATIONS ===")
for rr in range(1,7):
    print(f"\n--- 1:{rr} ---")
    print(res[res.rr==rr].head(15).to_string(index=False))

print("\nSaved: data/v80_massive_causal_search.csv")
print("NEXT: take the strongest stable variations and run strict sequential one-position-at-a-time execution + leakage audit.")
