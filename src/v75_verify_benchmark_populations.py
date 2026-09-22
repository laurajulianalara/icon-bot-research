import pandas as pd
import numpy as np

A=pd.read_csv("data/v56_icon_bot_funded_prior_year_trades.csv")
B=pd.read_csv("data/v27_option2a_trades.csv")
one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
one["time_ny"]=pd.to_datetime(one.time_ny)
idx=pd.Series(one.index,index=one.time_ny).to_dict()

def norm_time(s):
    return pd.to_datetime(s)

A["t"]=norm_time(A.candidate_time)
B["t"]=norm_time(B.candidate_time)

def rescore(df,label):
    counts={r:[0,0,0] for r in range(1,7)}
    missing=0
    for _,x in df.iterrows():
        i=idx.get(x.t)
        if i is None or i+3>=len(one): missing+=1; continue
        j=i+3
        entry=float(x.entry); risk=float(x.risk)
        if not np.isfinite(risk) or risk<=0: continue
        stop=entry-risk if x.direction=="LONG" else entry+risk
        future=one.iloc[j:min(j+241,len(one))]
        for rr in range(1,7):
            target=entry+rr*risk if x.direction=="LONG" else entry-rr*risk
            out=0
            for _,b in future.iterrows():
                if x.direction=="LONG":
                    if b.low<=stop: out=-1; break
                    if b.high>=target: out=1; break
                else:
                    if b.high>=stop: out=-1; break
                    if b.low<=target: out=1; break
            if out==1: counts[rr][0]+=1
            elif out==-1: counts[rr][1]+=1
            else: counts[rr][2]+=1
    print(f"\n{label} | rows={len(df)} | timestamp misses={missing}")
    for rr,(w,l,u) in counts.items():
        n=w+l
        print(f"1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}%" if n else f"1:{rr} | no resolved")
    return counts

print("=== V75 EXACT BENCHMARK POPULATION VERIFICATION ===")
print("Prior-year reference:",len(A),"unique timestamps:",A.t.nunique())
print("Original reference:",len(B),"unique timestamps:",B.t.nunique())
rescore(A,"2024-2025 reference")
rescore(B,"2025-2026 reference")
print("\nIMPORTANT: This script verifies identity/outcomes only. It does NOT claim the selection rule was causal.")
print("NEXT: once counts match the benchmark, freeze these 1,911 timestamps and build their pre-entry-only feature atlas.")
