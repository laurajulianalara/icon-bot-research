import pandas as pd
import numpy as np

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
d=pd.read_parquet("data/v68_full_causal_feature_table.parquet").copy()
one["time_ny"]=pd.to_datetime(one.time_ny); d["candidate_time"]=pd.to_datetime(d.candidate_time)
idx=pd.Series(one.index,index=one.time_ny).to_dict()

# Existing fully observable quality population from V68/V70.
q=d[(d.m1_move_atr<=.300)&(d.m1_close_pos>=.140)&(d.m2_close_pos<=.80)&
    (d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)&
    (d.early_reclaim_atr<=.90)&
    ((d.early_reclaim_atr<.576132)|(d.reclaim_x_wick<.183258))].copy()

print("=== FILTERED CAUSAL TIMING × RR MATRIX ===")
print("Observable-filter setups:",len(q))
for delay in (3,6,9):
    results={rr:[0,0] for rr in range(1,7)}
    accepted=0
    for _,r in q.iterrows():
        i=idx.get(r.candidate_time); j=i+delay if i is not None else None
        if i is None or j>=len(one): continue
        # At delayed entry, only use bars that are already complete.
        if delay>3:
            wait=one.iloc[i+3:j]
            if r.direction=="LONG" and len(wait) and wait.low.min()<float(r.extreme): continue
            if r.direction=="SHORT" and len(wait) and wait.high.max()>float(r.extreme): continue
        entry=float(one.iloc[j].open)
        stop=float(r.extreme)-.25 if r.direction=="LONG" else float(r.extreme)+.25
        risk=entry-stop if r.direction=="LONG" else stop-entry
        if risk<=0: continue
        accepted+=1
        future=one.iloc[j:min(j+241,len(one))]
        for rr in range(1,7):
            target=entry+rr*risk if r.direction=="LONG" else entry-rr*risk
            out=0
            for _,b in future.iterrows():
                if r.direction=="LONG":
                    if b.low<=stop: out=-1; break
                    if b.high>=target: out=1; break
                else:
                    if b.high>=stop: out=-1; break
                    if b.low<=target: out=1; break
            if out==1: results[rr][0]+=1
            elif out==-1: results[rr][1]+=1
    print(f"\nDelay {delay}m | accepted {accepted}")
    for rr,(w,l) in results.items():
        n=w+l
        print(f"1:{rr} | {w}W/{l}L | WR {100*w/n:.2f}% | Net {w*rr-l:+d}R" if n else f"1:{rr} | no resolved trades")

print("\nThis matrix is causal. Next step is based on whether confirmation + quality filtering creates a materially stronger population across the RR curve.")
