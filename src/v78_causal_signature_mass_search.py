import pandas as pd
import numpy as np
from itertools import combinations

print("=== V78 CAUSAL SIGNATURE MASS SEARCH ===")
atlas=pd.read_parquet("data/v76_preentry_feature_atlas.parquet")
full=pd.read_parquet("data/v68_full_causal_feature_table.parquet")

# Only features present in BOTH the reference atlas and full causal universe.
stable=pd.read_csv("data/v77_stable_signatures.csv")
common=[f for f in stable.feature.unique() if f in atlas.columns and f in full.columns]
print("Common causal features:",common)

# Build outcome labels on full population if present. V68 was created with causal
# pre-entry features; outcome columns may differ, so fail clearly rather than guess.
labelmap={}
for rr in range(1,7):
    opts=[f"win_{rr}r",f"outcome_{rr}r",f"result_{rr}r"]
    c=next((x for x in opts if x in full.columns),None)
    if c: labelmap[rr]=c

if not labelmap:
    print("V68 has no RR outcome labels. Creating threshold library only; next script will rescore outcomes from 1m bars.")
else:
    print("RR labels found:",labelmap)

rows=[]
# Learn thresholds ONLY from reference distribution, then apply to full universe.
# Quantiles avoid hand-picking exact winner medians.
for rr in range(1,7):
    s=stable[stable.rr==rr].sort_values("separation",ascending=False).head(8)
    rules=[]
    for _,x in s.iterrows():
        f=x.feature
        if f not in common: continue
        direction=x.direction
        for q in [.20,.30,.40,.50,.60,.70,.80]:
            th=float(atlas[f].quantile(q))
            rules.append((f,direction,q,th))

    # Singles + pairs + triples; enough breadth without overfitting huge conjunctions.
    candidates=[(r,) for r in rules]
    candidates += list(combinations(rules,2))
    candidates += list(combinations(rules,3))

    seen=set()
    for combo in candidates:
        # no duplicate feature inside a rule
        fs=[x[0] for x in combo]
        if len(set(fs))!=len(fs): continue
        key=tuple(sorted((f,d,q,round(th,10)) for f,d,q,th in combo))
        if key in seen: continue
        seen.add(key)
        mask=pd.Series(True,index=full.index)
        desc=[]
        for f,d,q,th in combo:
            vals=pd.to_numeric(full[f],errors="coerce")
            mask &= vals>=th if d=="HIGHER" else vals<=th
            desc.append(f"{f}{'>=' if d=='HIGHER' else '<='}{th:.6g}")
        n=int(mask.sum())
        if n<300: continue
        rec={"rr":rr,"n":n,"rules":" AND ".join(desc)}
        if rr in labelmap:
            y=full.loc[mask,labelmap[rr]]
            if y.dtype==object:
                y=y.astype(str).str.upper().isin(["1","TRUE","WIN","W"])
            else:
                y=pd.to_numeric(y,errors="coerce")
            rec["wins"]=int((y==1).sum())
            rec["wr"]=100*rec["wins"]/len(y)
        rows.append(rec)

out=pd.DataFrame(rows)
if len(out):
    sort=["rr"]+(["wr"] if "wr" in out.columns else ["n"])
    asc=[True,False]
    out=out.sort_values(sort,ascending=asc)
out.to_csv("data/v78_causal_signature_search.csv",index=False)

print("Combinations tested/retained:",len(out))
if "wr" in out.columns:
    for rr in range(1,7):
        print(f"\nTOP 1:{rr}")
        print(out[out.rr==rr].head(10).to_string(index=False))
else:
    print(out.groupby("rr").size())
    print("\nNeed RR rescoring on full causal universe before performance ranking.")
print("\nSaved: data/v78_causal_signature_search.csv")
print("NEXT: causal RR rescore + chronological one-position-at-a-time validation of the strongest rules.")
