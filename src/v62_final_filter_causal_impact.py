import pandas as pd
import numpy as np

ONE="data/mnq_continuous_1m.parquet"
CAND="data/reversal_candidates.parquet"

one=pd.read_parquet(ONE).sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet(CAND).sort_values("time_ny").reset_index(drop=True)
for x in (one,cand): x["time_ny"]=pd.to_datetime(x["time_ny"])

one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

rows=[]
for _,c in cand.iterrows():
    i=idx.get(c.time_ny)
    if i is None or i<20 or i+3>=len(one): continue
    if one.iloc[i+3].ticker!=c.ticker: continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0: continue
    sg=1 if c.direction=="LONG" else -1
    vals={}
    for k in [1,2]:
        b=one.iloc[i+k]
        pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
    base=vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912
    pop=base and vals["m2_close_pos"]<=.80 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4 and float(c.wick_percent)<=.60
    first2=one.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first2.iloc[-1].close))/a
    pop=pop and reclaim<=.90
    final=pop and (reclaim<.576132 or reclaim*float(c.wick_percent)<.183258)
    if final:
        rows.append({"candidate_time":c.time_ny,"signal_time":one.iloc[i+3].time_ny,"session":c.session,"direction":c.direction,
                     "next_same_extreme_time":c.get("next_same_extreme_time",pd.NaT)})

d=pd.DataFrame(rows)
# Recreate next same extreme from complete candidate stream.
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
nxt=cand[["time_ny","session","direction","next_same_extreme_time"]]
d=d.drop(columns=["next_same_extreme_time"]).merge(nxt,on=["time_ny","session","direction"],how="left")
d["old_rule_keeps"]=d.next_same_extreme_time.isna() | (d.signal_time<d.next_same_extreme_time)
d["causal_keeps"]=True
print("=== FINAL-FILTER CAUSAL IMPACT ===")
print("Final-filter setups before future-dependent invalidation:",len(d))
print("Kept by old Python rule:",int(d.old_rule_keeps.sum()))
print("Removed only because next 3m extreme is known at signal-time bar:",int((~d.old_rule_keeps).sum()))
print("Causal live/Pine setups:",int(d.causal_keeps.sum()))
print()
print("NEXT DECISION: if removed count is material, re-score RR outcomes using the causal set before Pine translation.")
