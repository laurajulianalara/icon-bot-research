import pandas as pd
import numpy as np

one=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
cand=pd.read_parquet("data/reversal_candidates.parquet").sort_values("time_ny").reset_index(drop=True)
for d in (one,cand): d["time_ny"]=pd.to_datetime(d["time_ny"])

tr=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1)
one["atr1"]=tr.rolling(20).mean()
idx=pd.Series(one.index,index=one.time_ny).to_dict()

setups=[]
for _,c in cand.iterrows():
    i=idx.get(c.time_ny)
    if i is None or i<20 or i+3>=len(one) or one.iloc[i+3].ticker!=c.ticker: continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0: continue
    sg=1 if c.direction=="LONG" else -1
    v={}
    for k in (1,2):
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        v[f"move{k}"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        v[f"pos{k}"]=float(cp if c.direction=="LONG" else 1-cp)
        v[f"dir{k}"]=int((((pre.close-pre.open)*sg)>0).sum())
    reclaim=(float(one.iloc[i+2].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(one.iloc[i+2].close))/a
    wick=float(c.wick_percent)
    ok=(v["move1"]<=.300 and v["pos1"]>=.140 and v["pos2"]<=.80 and wick<=.60
        and v["move2"]<=.15 and v["dir2"]<=4 and reclaim<=.90
        and (reclaim<.576132 or reclaim*wick<.183258))
    if not ok: continue
    entry=float(one.iloc[i+3].open)
    stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk=(entry-stop) if c.direction=="LONG" else (stop-entry)
    if risk<=0: continue
    setups.append((c.time_ny,i+3,c.session,c.direction,entry,stop,risk))

print("=== CAUSAL ICON BOT — LARGE SAMPLE RESCORE ===")
print("Qualifying live-causal setups:",len(setups))
for rr in range(1,7):
    w=l=u=0
    for _,j,session,direction,entry,stop,risk in setups:
        target=entry+rr*risk if direction=="LONG" else entry-rr*risk
        result=0
        for k in range(j,min(j+241,len(one))):
            b=one.iloc[k]
            if direction=="LONG":
                if b.low<=stop: result=-1; break
                if b.high>=target: result=1; break
            else:
                if b.high>=stop: result=-1; break
                if b.low<=target: result=1; break
        if result==1: w+=1
        elif result==-1: l+=1
        else: u+=1
    resolved=w+l
    wr=100*w/resolved if resolved else 0
    net=w*rr-l
    print(f"{rr}R: {w}W / {l}L / {u} unresolved | WR {wr:.2f}% | Net {net:+d}R")
