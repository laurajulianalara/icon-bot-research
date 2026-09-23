import pandas as pd, numpy as np

print("=== EXACT ORIGINAL ICON FILTER CHAIN — NATIVE 1M RECONSTRUCTION ===")
one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
ny=one.t.dt.tz_convert("America/New_York"); mins=ny.dt.hour*60+ny.dt.minute
def sess(m):
    if m>=1200:return "ASIA"
    if 120<=m<300:return "LONDON"
    if 570<=m<750:return "NYAM"
    if 810<=m<1020:return "NYPM"
    return None
one["session"]=[sess(m) for m in mins]; one["date"]=ny.dt.date
prev=one.close.shift()
one["atr1"]=pd.concat([one.high-one.low,(one.high-prev).abs(),(one.low-prev).abs()],axis=1).max(axis=1).rolling(20).mean()

# Blind native-1m new-session-extreme stream.
cand=[]
for (d,s),g in one.dropna(subset=["session"]).groupby(["date","session"],sort=False):
    hi=-np.inf;lo=np.inf
    for i in g.index:
        h=float(one.at[i,"high"]);l=float(one.at[i,"low"])
        if h>hi:cand.append((i,"SHORT",h));hi=h
        if l<lo:cand.append((i,"LONG",l));lo=l

passed=[]
for i,direction,orig_ext in cand:
    if i<20 or i+3>=len(one):continue
    # Corrected native-1m state: update extreme through completed T+2, then T+3 open.
    if any(one.at[i+k,"t"]-one.at[i+k-1,"t"]!=pd.Timedelta(minutes=1) for k in [1,2,3]):continue
    if any(one.at[i+k,"session"]!=one.at[i,"session"] for k in [1,2]):continue
    a=float(one.at[i,"atr1"])
    if not np.isfinite(a) or a<=0:continue
    sg=1 if direction=="LONG" else -1
    ext=float(one.iloc[i:i+3].low.min() if direction=="LONG" else one.iloc[i:i+3].high.max())
    vals={}
    for k in [1,2]:
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.at[i,"close"]))/a*sg
        vals[f"m{k}_body_atr"]=abs(float(b.close-b.open))/a
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if direction=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
    # Exact old base
    if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912):continue
    # Candidate-level wick, plus first-two-minute reclaim using updated native extreme.
    b0=one.iloc[i]; rng=max(float(b0.high-b0.low),.25)
    wick=((min(b0.open,b0.close)-b0.low)/rng) if direction=="LONG" else ((b0.high-max(b0.open,b0.close))/rng)
    first2=one.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-ext)/a if direction=="LONG" else (ext-float(first2.iloc[-1].close))/a
    # Exact old pre-Option2
    if not(reclaim<=.90 and vals["m2_close_pos"]<=.80 and wick<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4):continue
    # Exact old final OR filter
    if not(reclaim<.576132 or (reclaim*wick)<.183258):continue
    passed.append((i,direction,ext,reclaim,wick,vals))

print("Blind candidates:",len(cand))
print("Passed exact original filter chain:",len(passed))

# Sequential forward RR; one position at a time, enter T+3 open, stop-first.
for rr in range(1,7):
    w=l=u=0; busy=-1; signals=0
    for i,direction,ext,reclaim,wick,vals in passed:
        j=i+3
        if j<=busy:continue
        entry=float(one.at[j,"open"]); stop=ext-.25 if direction=="LONG" else ext+.25
        risk=entry-stop if direction=="LONG" else stop-entry
        if risk<=0:continue
        target=entry+rr*risk if direction=="LONG" else entry-rr*risk
        signals+=1;out=0;end=j
        for k in range(j,min(j+241,len(one))):
            b=one.iloc[k];end=k
            if direction=="LONG":
                if b.low<=stop:out=-1;break
                if b.high>=target:out=1;break
            else:
                if b.high>=stop:out=-1;break
                if b.low<=target:out=1;break
        busy=end
        if out==1:w+=1
        elif out==-1:l+=1
        else:u+=1
    print(f"1:{rr} | signals={signals} | {w}W/{l}L/{u}U | WR={100*w/(w+l):.2f}%")

print("\nThis uses the documented original deterministic base + pre-Option2 + final OR filters, but replaces the illegal 3m future invalidation with the live-knowable native-1m +2 extreme update.")
