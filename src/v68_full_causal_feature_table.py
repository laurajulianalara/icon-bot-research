import pandas as pd
import numpy as np

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
for d in (one,cand): d["time_ny"]=pd.to_datetime(d["time_ny"])

cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
tr=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1)
one["atr1"]=tr.rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

rows=[]
for _,c in cand.iterrows():
    i=idx.get(c.time_ny)
    if i is None or i<20 or i+3>=len(one) or one.iloc[i+3].ticker!=c.ticker: continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0: continue
    sg=1 if c.direction=="LONG" else -1
    row={"candidate_time":c.time_ny,"session":c.session,"direction":c.direction,
         "wick_percent":float(c.wick_percent),"extreme":float(c.extreme)}
    for k in (1,2):
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        row[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        row[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        row[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
    first2=one.iloc[i+1:i+3]
    row["early_reclaim_atr"]=(float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first2.iloc[-1].close))/a
    row["early_adverse_atr"]=(float(c.extreme)-float(first2.low.min()))/a if c.direction=="LONG" else (float(first2.high.max())-float(c.extreme))/a
    row["reclaim_x_wick"]=row["early_reclaim_atr"]*row["wick_percent"]
    signal=one.iloc[i+3].time_ny
    row["hindsight_kept"]=pd.isna(c.next_same_extreme_time) or signal<c.next_same_extreme_time
    rows.append(row)

d=pd.DataFrame(rows)
d.to_parquet("data/v68_full_causal_feature_table.parquet",index=False)

# Apply only the observable pre-entry filters to define the population we need to study.
q=d[(d.m1_move_atr<=.300)&(d.m1_close_pos>=.140)&(d.m2_close_pos<=.80)&
    (d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)&
    (d.early_reclaim_atr<=.90)&
    ((d.early_reclaim_atr<.576132)|(d.reclaim_x_wick<.183258))].copy()

print("=== FULL PRE-ENTRY FEATURE TABLE ===")
print("Feature rows:",len(d))
print("Final observable-filter population:",len(q))
print("Hindsight-kept:",int(q.hindsight_kept.sum()))
print("Hindsight-rejected:",int((~q.hindsight_kept).sum()))
print("Saved: data/v68_full_causal_feature_table.parquet")
print()
print("We now have BOTH groups with only pre-entry features available for the next winner/loser study.")
