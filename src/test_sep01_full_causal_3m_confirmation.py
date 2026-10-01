#!/usr/bin/env python3
"""
Sept 1 true causal Option 2B + 3m confirmation diagnostic.

Pipeline:
causal 3m session extreme -> frozen V7 -> V8 -> V15 -> V27
-> next completed 3m candle confirms -> following 3m open entry -> 1R..6R.

No next_same_extreme_time. No future extreme knowledge. No historical trade list.
The frozen filters inspect the 1m bars inside the already-completed candidate 3m candle.
"""
import bisect, json
from pathlib import Path
import numpy as np
import pandas as pd

TZ="America/New_York"
DAY=pd.Timestamp("2026-09-01",tz=TZ)
FILE=Path("data/audit_sep01_24_1m.parquet")
REF_PATH=Path("data/icon_v15_pine_reference.json")
RTH=.576132
WTH=.183258
V15_THRESHOLD=.145921011058
SPEC=[("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),
      ("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),
      ("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]

with REF_PATH.open() as f:
    REF={k:sorted(float(x) for x in v) for k,v in json.load(f).items()}

def rank(v,a):
    if not np.isfinite(v): return np.nan
    lo=bisect.bisect_left(a,float(v)); hi=bisect.bisect_right(a,float(v))
    return (lo+(hi-lo+1)/2)/len(a) if hi>lo else min(1,max(0,(lo+1)/len(a)))

def score(f):
    p=[]
    for col,hi,w in SPEC:
        r=rank(f[col],REF[col])
        if not np.isfinite(r): return np.nan
        p += [(r if hi else 1-r)]*w
    return float(np.mean(p))

def session_name(ts):
    m=ts.hour*60+ts.minute
    if 1200<=m<1440:return "ASIA"
    if 120<=m<300:return "LONDON"
    if 570<=m<750:return "NYAM"
    if 810<=m<1020:return "NYPM"
    return None

one=pd.read_parquet(FILE).copy()
one["time_ny"]=pd.to_datetime(one["time_ny"])
if one["time_ny"].dt.tz is None:
    one["time_ny"]=one["time_ny"].dt.tz_localize(TZ)
else:
    one["time_ny"]=one["time_ny"].dt.tz_convert(TZ)
for c in ["open","high","low","close","volume"]:
    one[c]=pd.to_numeric(one[c],errors="coerce")
one=one.sort_values("time_ny").reset_index(drop=True)

# Frozen 1m ATR, calculated causally.
pc=one.close.shift(1)
one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()

# Completed 3m bars, with global causal ATR20 exactly as shadow runner.
z=one.set_index("time_ny")
three=z.resample("3min",label="left",closed="left").agg(
    ticker=("ticker","last"),open=("open","first"),high=("high","max"),low=("low","min"),
    close=("close","last"),volume=("volume","sum"),n=("close","count")
).reset_index()
three=three[(three.n==3)&three.open.notna()].copy()
pc3=three.close.shift(1)
three["atr_20"]=pd.concat([three.high-three.low,(three.high-pc3).abs(),(three.low-pc3).abs()],axis=1).max(axis=1).rolling(20).mean()
three["upper_wick"]=three.high-three[["open","close"]].max(axis=1)
three["lower_wick"]=three[["open","close"]].min(axis=1)-three.low
three["session"]=three.time_ny.apply(session_name)

# Only Sept 1 decisions; retain earlier source data above for indicator warm-up.
bars=three[(three.time_ny>=DAY)&(three.time_ny<DAY+pd.Timedelta(days=1))].reset_index(drop=True)
idx1=pd.Series(one.index,index=one.time_ny).to_dict()

running={}
pending_confirm=[]
scheduled_entries=[]
audit=[]
trades=[]

def frozen_filters(c):
    i=idx1.get(c["time_ny"])
    if i is None or i<20 or i+2>=len(one): return False,"DATA",np.nan
    a=float(one.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:return False,"ATR",np.nan
    sg=1 if c["direction"]=="LONG" else -1
    vals={}
    for k in [1,2]:
        b=one.iloc[i+k]
        pre=one.iloc[max(0,i+k-5):i+k+1]
        vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        vals[f"m{k}_close_pos"]=float(cp if c["direction"]=="LONG" else 1-cp)
        vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
    if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912):
        return False,"V7",np.nan
    first2=one.iloc[i+1:i+3]
    reclaim=(float(first2.iloc[-1].close)-c["extreme"])/a if c["direction"]=="LONG" else (c["extreme"]-float(first2.iloc[-1].close))/a
    if not(reclaim<=.90 and vals["m2_close_pos"]<=.80 and c["wick_percent"]<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4):
        return False,"V8",np.nan
    rq=(1-min(max(vals["m2_close_pos"],0),1))*(1-min(max(c["wick_percent"],0),1))
    ri=-vals["m2_move_atr"]
    ca=c["atr"]
    sa=c["sweep_distance"]/ca if np.isfinite(ca) and ca>0 else np.nan
    rts=reclaim/(abs(sa)+.05); itr=ri/(abs(reclaim)+.05); rxw=reclaim*c["wick_percent"]
    f={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,
       "reversal_impulse":ri,"reclaim_x_wick":rxw,"close_x_reclaim":vals["m2_close_pos"]*reclaim,
       "sweep_minus_reclaim":sa-reclaim,"impulse_minus_reclaim":ri-reclaim,
       "quality_balance":rq*itr/(1+rts)}
    sc=score(f)
    if not np.isfinite(sc) or sc<V15_THRESHOLD:return False,"V15",sc
    if reclaim>=RTH and rxw>=WTH:return False,"V27",sc
    return True,"PASS",sc

for bi,r in bars.iterrows():
    t=r.time_ny
    sess=r.session

    # Entry happens at this bar's OPEN, before its H/L/C can influence the decision.
    due=[x for x in scheduled_entries if x["entry_index"]==bi]
    scheduled_entries=[x for x in scheduled_entries if x["entry_index"]!=bi]
    for p in due:
        if sess!=p["session"]: continue
        entry=float(r.open)
        stop=p["extreme"]-.25 if p["direction"]=="LONG" else p["extreme"]+.25
        risk=entry-stop if p["direction"]=="LONG" else stop-entry
        if risk<=0:
            audit.append({**p,"stage":"BAD_RISK","entry_time":t,"entry":entry,"stop":stop})
            continue
        q={**p,"entry_time":t,"entry":entry,"stop":stop,"risk":risk}
        trades.append(q)
        audit.append({**q,"stage":"TRADE"})

    if sess is None: continue

    # Confirmation is evaluated only when this full 3m bar has closed.
    due=[x for x in pending_confirm if x["confirm_index"]==bi]
    pending_confirm=[x for x in pending_confirm if x["confirm_index"]!=bi]
    for p in due:
        if sess!=p["session"]: continue
        confirmed=(float(r.close)>p["body_top"]) if p["direction"]=="LONG" else (float(r.close)<p["body_bottom"])
        audit.append({**p,"stage":"CONFIRM_PASS" if confirmed else "CONFIRM_FAIL",
                      "confirm_time":t,"confirm_close":float(r.close)})
        if confirmed and bi+1<len(bars):
            scheduled_entries.append({**p,"confirm_time":t,"confirm_close":float(r.close),"entry_index":bi+1})

    key=(t.date(),sess)
    h=float(r.high); l=float(r.low)
    if key not in running:
        running[key]=[h,l]
        continue
    rh,rl=running[key]
    candidates=[]
    rng=h-l
    if l<rl:
        candidates.append({"time_ny":t,"session":sess,"direction":"LONG","ticker":r.ticker,
                           "extreme":l,"atr":float(r.atr_20),"sweep_distance":rl-l,
                           "wick_percent":float(r.lower_wick/rng) if rng>0 else 0,
                           "body_top":max(float(r.open),float(r.close)),
                           "body_bottom":min(float(r.open),float(r.close))})
    if h>rh:
        candidates.append({"time_ny":t,"session":sess,"direction":"SHORT","ticker":r.ticker,
                           "extreme":h,"atr":float(r.atr_20),"sweep_distance":h-rh,
                           "wick_percent":float(r.upper_wick/rng) if rng>0 else 0,
                           "body_top":max(float(r.open),float(r.close)),
                           "body_bottom":min(float(r.open),float(r.close))})
    running[key]=[max(rh,h),min(rl,l)]

    for c in candidates:
        ok,stage,sc=frozen_filters(c)
        audit.append({**c,"stage":stage,"v15_score":sc})
        if ok and bi+1<len(bars):
            pending_confirm.append({**c,"v15_score":sc,"confirm_index":bi+1})

# Outcomes: future data is used only after a trade has already been causally entered.
for q in trades:
    ei=bars.index[bars.time_ny==q["entry_time"]]
    if len(ei)==0: continue
    ei=int(ei[0])
    for R in range(1,7):
        target=q["entry"]+R*q["risk"] if q["direction"]=="LONG" else q["entry"]-R*q["risk"]
        outcome="OPEN"
        # ~4-hour canonical-style horizon: 81 x 3m bars.
        for _,b in bars.iloc[ei:min(len(bars),ei+81)].iterrows():
            if q["direction"]=="LONG":
                sh=float(b.low)<=q["stop"]; th=float(b.high)>=target
            else:
                sh=float(b.high)>=q["stop"]; th=float(b.low)<=target
            if sh: outcome="LOSS"; break
            if th: outcome="WIN"; break
        q[f"{R}R"]=outcome

adf=pd.DataFrame(audit)
tdf=pd.DataFrame(trades)
out=Path("data/reports")
out.mkdir(parents=True,exist_ok=True)
adf.to_csv(out/"2026-09-01_full_causal_confirmation_audit.csv",index=False)
tdf.to_csv(out/"2026-09-01_full_causal_confirmation_trades.csv",index=False)

print("\n"+"="*72)
print("SEPT 1 — FULL TRUE-CAUSAL OPTION 2B + 3M CONFIRMATION")
print("="*72)
print("Pipeline: causal 3m extreme -> V7 -> V8 -> V15 -> V27 -> confirmation -> trade")
print("Future supersession: DISABLED")
print("Historical trade list: NOT USED")
print("\nSTAGE COUNTS")
print(adf.stage.value_counts().to_string() if not adf.empty else "No events")
print("\nTRADES")
if tdf.empty:
    print("NO TRADES")
else:
    cols=["session","direction","time_ny","confirm_time","entry_time","entry","stop","risk","v15_score","1R","2R","3R","4R","5R","6R"]
    print(tdf[cols].to_string(index=False))
    print("\nRR SUMMARY")
    for R in range(1,7):
        w=int((tdf[f"{R}R"]=="WIN").sum()); l=int((tdf[f"{R}R"]=="LOSS").sum())
        n=w+l
        print(f"{R}R | {w}W / {l}L | {(100*w/n if n else 0):.1f}% WR")
print("\nAudit:",out/"2026-09-01_full_causal_confirmation_audit.csv")
print("Trades:",out/"2026-09-01_full_causal_confirmation_trades.csv")
print("="*72)
