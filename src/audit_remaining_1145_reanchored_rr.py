import pandas as pd, numpy as np

print("=== 1,145 RE-ANCHORED 1M RR AUDIT ===")
rec=pd.read_csv("data/remaining_1145_native_1m_recoverability.csv")
rec["arrived_extreme_time"]=pd.to_datetime(rec["arrived_extreme_time"],utc=True,errors="coerce")
one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

print("Recoverable rows:",len(rec))
print("Rule: wait until the actual most-extreme 1m bar has printed, then enter at the NEXT 1m open.")
for rr in range(1,7):
    w=l=u=miss=0
    for _,x in rec.iterrows():
        i=idx.get(x.arrived_extreme_time)
        if i is None or i+1>=len(one): miss+=1; continue
        j=i+1; direction=str(x.direction).upper()
        entry=float(one.iloc[j].open); extreme=float(x.arrived_extreme)
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
    print(f"1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}% | misses={miss}" if n else f"1:{rr} no resolved")
print("\nIMPORTANT: This is a research ceiling for re-anchored timing. The arrived extreme is identified retrospectively inside the T..T+3 window; these RR numbers alone do NOT prove a live selector can know which arriving extreme is final.")
