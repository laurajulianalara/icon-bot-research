import pandas as pd, numpy as np

print("=== 1,145 PROSPECTIVE EXTREME-CHOICE AUDIT ===")
r=pd.read_csv("data/remaining_1145_native_1m_recoverability.csv")
r["original_time"]=pd.to_datetime(r["original_time"],utc=True,errors="coerce")
r["arrived_extreme_time"]=pd.to_datetime(r["arrived_extreme_time"],utc=True,errors="coerce")
one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

# For each original candidate, test simple rules that are knowable live:
# take first next-open, or WAIT only when the next completed minute makes a newer extreme.
rules={"FIRST_NEXT_OPEN":[],"UPDATE_THROUGH_1":[],"UPDATE_THROUGH_2":[],"UPDATE_THROUGH_3":[]}
for _,x in r.iterrows():
    i=idx.get(x.original_time)
    if i is None: continue
    direction=str(x.direction).upper()
    for horizon,name in [(0,"FIRST_NEXT_OPEN"),(1,"UPDATE_THROUGH_1"),(2,"UPDATE_THROUGH_2"),(3,"UPDATE_THROUGH_3")]:
        end=min(i+horizon,len(one)-2)
        w=one.iloc[i:end+1]
        rel=int(np.argmax(w.high.to_numpy())) if direction=="SHORT" else int(np.argmin(w.low.to_numpy()))
        ei=i+rel
        rules[name].append((x,ei,ei+1))

for name,items in rules.items():
    exact=sum(one.iloc[ei].t==x.arrived_extreme_time for x,ei,j in items)
    print(f"\n{name} | rows={len(items)} | chose retrospective final extreme={exact}/{len(items)} ({100*exact/len(items):.2f}%)")
    for rr in [1,2,3,4,5,6]:
        w=l=u=0
        for x,ei,j in items:
            if j>=len(one):continue
            direction=str(x.direction).upper()
            entry=float(one.iloc[j].open)
            extreme=float(one.iloc[ei].low if direction=="LONG" else one.iloc[ei].high)
            stop=extreme-.25 if direction=="LONG" else extreme+.25
            risk=entry-stop if direction=="LONG" else stop-entry
            if risk<=0 or not np.isfinite(risk):u+=1;continue
            target=entry+rr*risk if direction=="LONG" else entry-rr*risk
            out=0
            for k in range(j,min(j+241,len(one))):
                b=one.iloc[k]
                if direction=="LONG":
                    if b.low<=stop:out=-1;break
                    if b.high>=target:out=1;break
                else:
                    if b.high>=stop:out=-1;break
                    if b.low<=target:out=1;break
            if out==1:w+=1
            elif out==-1:l+=1
            else:u+=1
        n=w+l
        print(f"  1:{rr} | {100*w/n:.2f}% | {w}W/{l}L/{u}U" if n else f"  1:{rr} no resolved")

print("\nPurpose: quantify exactly how much of the 1,145 ceiling can be recovered with simple live-knowable update rules before building another selector.")
