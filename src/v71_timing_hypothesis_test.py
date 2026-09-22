import pandas as pd
import numpy as np

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
for d in (one,cand): d["time_ny"]=pd.to_datetime(d["time_ny"])
idx=pd.Series(one.index,index=one.time_ny).to_dict()

# Test whether waiting for the next 3m bar to CONFIRM no continuation can
# reproduce the old hindsight idea causally. Entry is delayed until the next
# bar is complete; no future information is used at the decision timestamp.
print("=== CAUSAL DELAYED-CONFIRMATION TEST ===")
for delay in (3,6,9):
    trades=[]
    for _,c in cand.iterrows():
        i=idx.get(c.time_ny)
        j=i+delay if i is not None else None
        if i is None or i<20 or j>=len(one) or one.iloc[j].ticker!=c.ticker: continue
        # Reject if price makes a new same-direction extreme during the waiting window.
        wait=one.iloc[i+3:j+1] if delay>3 else one.iloc[0:0]
        if len(wait):
            if c.direction=="LONG" and wait.low.min()<float(c.extreme): continue
            if c.direction=="SHORT" and wait.high.max()>float(c.extreme): continue
        entry=float(one.iloc[j].open)
        stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
        risk=entry-stop if c.direction=="LONG" else stop-entry
        if risk<=0: continue
        target=entry+4*risk if c.direction=="LONG" else entry-4*risk
        out=0
        for k in range(j,min(j+241,len(one))):
            b=one.iloc[k]
            if c.direction=="LONG":
                if b.low<=stop: out=-1; break
                if b.high>=target: out=1; break
            else:
                if b.high>=stop: out=-1; break
                if b.low<=target: out=1; break
        if out: trades.append(out)
    w=sum(x==1 for x in trades); l=sum(x==-1 for x in trades)
    print(f"Delay {delay}m: {len(trades)} trades | {w}W/{l}L | 4R WR {100*w/(w+l):.2f}% | Net {w*4-l:+d}R")
print()
print("This is a timing hypothesis test only. If delayed confirmation materially improves results, next step is to combine it with the existing pre-entry quality filters and validate chronologically.")
