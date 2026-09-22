import pandas as pd
import numpy as np

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
one["time_ny"]=pd.to_datetime(one["time_ny"])
cand["time_ny"]=pd.to_datetime(cand["time_ny"])
cand["next_extreme"]=cand.groupby(["session_id","direction"],sort=False)["time_ny"].shift(-1)

tr=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1)
one["atr1"]=tr.rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

total=kept=removed=0
for _,c in cand.iterrows():
    i=idx.get(c.time_ny)
    if i is None or i<20 or i+3>=len(one) or one.iloc[i+3].ticker!=c.ticker:
        continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:
        continue
    sg=1 if c.direction=="LONG" else -1
    vals={}
    for k in (1,2):
        b=one.iloc[i+k]
        pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"move{k}"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"pos{k}"]=float(cp if c.direction=="LONG" else 1-cp)
        vals[f"dir{k}"]=int((((pre.close-pre.open)*sg)>0).sum())
    first2=one.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first2.iloc[-1].close))/a
    wick=float(c.wick_percent)
    ok=(vals["move1"]<=.300 and vals["pos1"]>=.140 and vals["pos2"]<=.80
        and wick<=.60 and vals["move2"]<=.15 and vals["dir2"]<=4
        and reclaim<=.90 and (reclaim<.576132 or reclaim*wick<.183258))
    if not ok:
        continue
    total+=1
    signal=one.iloc[i+3].time_ny
    old_keep=pd.isna(c.next_extreme) or signal<c.next_extreme
    if old_keep: kept+=1
    else: removed+=1

print("=== FINAL ICON SETUP TIMING CHECK ===")
print("Final setups before old future-dependent invalidation:",total)
print("Kept by old research rule:",kept)
print("Removed by that rule:",removed)
print("Live-causal setup count:",total)
print("Removed %:",round(100*removed/total,2) if total else 0)
