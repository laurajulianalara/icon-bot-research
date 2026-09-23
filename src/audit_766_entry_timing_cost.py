import pandas as pd, numpy as np

print("=== ENTRY-TIMING COST AUDIT — FROZEN 766 ===")
ref=pd.read_csv("data/final_corrected_766_causal_audit.csv")
ref=ref[ref["corrected_fully_causal_mechanics"].astype(str).str.lower().eq("true")].copy()
ref["mapped_candidate_time"]=pd.to_datetime(ref["mapped_candidate_time"],utc=True,errors="coerce")
one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

print("Frozen cohort:",len(ref))
print("Question: how much performance is lost by waiting 0,1,2,3 minutes after the extreme?")

for delay in [1,2,3,4]:
    print(f"\nENTRY AT +{delay} MINUTE OPEN")
    for rr in range(1,7):
        w=l=u=miss=0
        for _,x in ref.iterrows():
            i=idx.get(x.mapped_candidate_time)
            if i is None or i+delay>=len(one): miss+=1; continue
            j=i+delay
            direction=str(x.direction).upper()
            entry=float(one.iloc[j].open)
            extreme=float(one.iloc[i].low if direction=="LONG" else one.iloc[i].high)
            stop=extreme-.25 if direction=="LONG" else extreme+.25
            risk=entry-stop if direction=="LONG" else stop-entry
            if not np.isfinite(risk) or risk<=0: u+=1; continue
            target=entry+rr*risk if direction=="LONG" else entry-rr*risk
            out=0
            for k in range(j,min(j+241,len(one))):
                b=one.iloc[k]
                if direction=="LONG":
                    if b.low<=stop: out=-1; break
                    if b.high>=target: out=1; break
                else:
                    if b.high>=stop: out=-1; break
                    if b.low<=target: out=1; break
            if out==1:w+=1
            elif out==-1:l+=1
            else:u+=1
        n=w+l
        print(f"  1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}% | misses={miss}" if n else f"  1:{rr} no resolved")

print("\nINTERPRETATION: +1 is earliest causal next-open entry. +4 approximates the 3-minute confirmation test.")
print("This isolates whether the weak RR is mainly caused by waiting too long versus poor trade selection.")
