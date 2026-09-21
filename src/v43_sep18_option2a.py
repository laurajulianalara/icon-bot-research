import pandas as pd
import numpy as np
TODAY="data/mnq_continuous_1m.parquet"; HIST="data/mnq_continuous_1m.parquet"
DATE=pd.Timestamp("2026-09-18").date(); RTH=0.576132; WTH=0.183258
h=pd.read_parquet(HIST); t=pd.read_parquet(TODAY)
for x in (h,t): x["time_ny"]=pd.to_datetime(x["time_ny"])
need=["time_ny","ticker","open","high","low","close","volume"]
one=pd.concat([h[need][h.time_ny<t.time_ny.min()].tail(300),t[need]],ignore_index=True).drop_duplicates("time_ny",keep="last").sort_values("time_ny").reset_index(drop=True)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
z=one.set_index("time_ny")
three=z.resample("3min",label="left",closed="left").agg(ticker=("ticker","last"),open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum")).dropna(subset=["open","high","low","close"]).reset_index()
three["atr"]=pd.concat([three.high-three.low,(three.high-three.close.shift()).abs(),(three.low-three.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
three["upper_wick"]=three.high-three[["open","close"]].max(axis=1); three["lower_wick"]=three[["open","close"]].min(axis=1)-three.low
mins=three.time_ny.dt.hour*60+three.time_ny.dt.minute\nsm=((mins>=120)&(mins<300))|((mins>=570)&(mins<750))|((mins>=810)&(mins<1020))\ng=three[(three.time_ny.dt.date==DATE)&sm].copy()\ndef sess(ts):\n    m=ts.hour*60+ts.minute\n    return "LONDON" if 120<=m<300 else ("NYAM" if 570<=m<750 else "NYPM")\ng["session"]=g.time_ny.apply(sess)\ng=g.reset_index(drop=True)
cands=[]; rh=rl=None
for _,r in g.iterrows():
    if rh is None: rh=float(r.high); rl=float(r.low); continue
    rng=float(r.high-r.low)
    if r.low<rl: cands.append(dict(time_ny=r.time_ny,session=session,direction="LONG",ticker=r.ticker,extreme=float(r.low),wick_percent=float(r.lower_wick/rng) if rng>0 else 0))
    if r.high>rh: cands.append(dict(time_ny=r.time_ny,session=session,direction="SHORT",ticker=r.ticker,extreme=float(r.high),wick_percent=float(r.upper_wick/rng) if rng>0 else 0))
    rh=max(rh,float(r.high)); rl=min(rl,float(r.low))
cand=pd.DataFrame(cands).sort_values("time_ny").reset_index(drop=True)
if cand.empty: print("NO LONDON CANDIDATES"); raise SystemExit
cand["next_same_extreme_time"]=cand.groupby(["session","direction"]).time_ny.shift(-1)
idx1=pd.Series(one.index,index=one.time_ny).to_dict(); rows=[]
for _,c in cand.iterrows():
    i=idx1.get(c.time_ny)
    if i is None or i<20 or i+3>=len(one): continue
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0: continue
    sg=1 if c.direction=="LONG" else -1; vals={}
    for k in [1,2]:
        b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int((((pre.close-pre.open)*sg)>0).sum())
    if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912): continue
    first2=one.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first2.iloc[-1].close))/a
    rw=reclaim*float(c.wick_percent)
    if reclaim>=RTH and rw>=WTH: continue
    j=i+3; signal=one.iloc[j].time_ny
    if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time: continue
    if one.iloc[j].ticker!=c.ticker: continue
    entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk=entry-stop if c.direction=="LONG" else stop-entry
    if risk<=0: continue
    maxr=0.0
    for q in range(j,min(j+241,len(one))):
        b=one.iloc[q]
        if b.ticker!=c.ticker: break
        fav=(float(b.high)-entry)/risk if c.direction=="LONG" else (entry-float(b.low))/risk
        sh=float(b.low)<=stop if c.direction=="LONG" else float(b.high)>=stop
        if sh: break
        maxr=max(maxr,fav)
    rows.append(dict(session=c.session,entry_time=signal,direction=c.direction,entry=entry,stop=stop,risk_points=risk,max_rr=maxr))
r=pd.DataFrame(rows)
print("\n=== OPTION 2A — SEPT 18 LONDON + NYAM + NYPM ===")
if r.empty: print("QUALIFYING TRADES: 0"); raise SystemExit
r["outcome_4r"]=np.where(r.max_rr>=4,"WIN","LOSS")
print("Trades:",len(r))
print(r[["session","entry_time","direction","entry","stop","risk_points","outcome_4r","max_rr"]].round(2).to_string(index=False))
print("\nRR HIT RATES")
for rr in range(1,7):
    w=int((r.max_rr>=rr).sum()); print(f"{rr}R: {w}/{len(r)} = {100*w/len(r):.2f}%")
w4=int((r.max_rr>=4).sum()); l4=len(r)-w4; net=w4*4-l4
print(f"\n4R: {w4}W / {l4}L | Net: {net:+.0f}R | at 250 risk: {net*250:+,.0f} USD")
print(f"Average max RR: {r.max_rr.mean():.2f}R | Median: {r.max_rr.median():.2f}R | Highest: {r.max_rr.max():.2f}R")
r.to_csv("data/sep18_option2a.csv",index=False)
print("Saved: data/sep21_london_option2a.csv")
