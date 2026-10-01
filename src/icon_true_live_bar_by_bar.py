#!/usr/bin/env python3
"""
THE ICON — TRUE LIVE BAR-BY-BAR SHADOW TEST
Massive live 1m websocket -> completed 3m bars -> causal session extreme
-> frozen V7/V8/V15/V27 -> next completed 3m confirmation
-> following live 3m OPEN shadow signal.

NO orders. NO future supersession. NO next_same_extreme_time.
"""
import asyncio, bisect, json, os, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests, websockets

TZ="America/New_York"; ET=ZoneInfo(TZ); UTC=ZoneInfo("UTC")
WS_URL="wss://socket.massive.com/futures"
SYMBOL=os.getenv("ICON_MNQ_SYMBOL","MNQZ6")
RTH=.576132; WTH=.183258; V15_THRESHOLD=.145921011058
HIST="data/mnq_continuous_1m.parquet"; REF_PATH="data/icon_v15_pine_reference.json"
NUM=["open","high","low","close","volume"]; NEED=["time_ny","ticker",*NUM]
with open(REF_PATH) as f: REF={k:sorted(float(x) for x in v) for k,v in json.load(f).items()}
SPEC=[("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),
("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),
("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]

def session_name(ts):
    m=ts.hour*60+ts.minute
    if 1200<=m<1440:return "ASIA"
    if 120<=m<300:return "LONDON"
    if 570<=m<750:return "NYAM"
    if 810<=m<1020:return "NYPM"
    return None
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
def numeric(df):
    df=df.copy()
    for c in NUM: df[c]=pd.to_numeric(df[c],errors="coerce")
    return df
def fetch_today(key):
    now=datetime.now(ET); day=pd.Timestamp(now.date(),tz=TZ)
    url=f"https://api.massive.com/futures/v1/aggs/{SYMBOL}"
    params={"resolution":"1min","window_start.gte":day.tz_convert("UTC").isoformat(),
      "window_start.lt":pd.Timestamp(now).tz_convert("UTC").isoformat(),"limit":50000,
      "sort":"window_start.asc","apiKey":key}
    r=requests.get(url,params=params,timeout=60); r.raise_for_status(); out=[]
    for x in r.json().get("results",[]):
        ns=x.get("window_start")
        if ns is None: continue
        out.append({"time_ny":pd.to_datetime(ns,unit="ns",utc=True).tz_convert(TZ),"ticker":SYMBOL,
          "open":x.get("open"),"high":x.get("high"),"low":x.get("low"),"close":x.get("close"),"volume":x.get("volume",0)})
    return numeric(pd.DataFrame(out,columns=NEED))
def bootstrap(key):
    h=pd.read_parquet(HIST)[NEED].copy(); h["time_ny"]=pd.to_datetime(h.time_ny)
    h["time_ny"]=h.time_ny.dt.tz_localize(TZ) if h.time_ny.dt.tz is None else h.time_ny.dt.tz_convert(TZ)
    h=numeric(h); t=fetch_today(key)
    start=pd.Timestamp(datetime.now(ET).date(),tz=TZ)-pd.Timedelta(days=3)
    return numeric(pd.concat([h[h.time_ny>=start].tail(5000),t],ignore_index=True)
      .drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True))
def make3(one):
    z=one.set_index("time_ny")
    x=z.resample("3min",label="left",closed="left").agg(ticker=("ticker","last"),open=("open","first"),
      high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum"),n=("close","count")).reset_index()
    x=x[(x.n==3)&x.open.notna()].copy()
    pc=x.close.shift(1)
    x["atr_20"]=pd.concat([x.high-x.low,(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
    x["upper_wick"]=x.high-x[["open","close"]].max(axis=1)
    x["lower_wick"]=x[["open","close"]].min(axis=1)-x.low
    x["session"]=x.time_ny.apply(session_name)
    return x.reset_index(drop=True)
def prep1(one):
    x=one.sort_values("time_ny").reset_index(drop=True).copy(); pc=x.close.shift(1)
    x["atr1"]=pd.concat([x.high-x.low,(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
    return x
def frozen_filter(one,c):
    x=prep1(one); ids=pd.Series(x.index,index=x.time_ny).to_dict(); i=ids.get(c["time_ny"])
    if i is None or i<20 or i+2>=len(x): return False,"DATA",np.nan
    a=float(x.iloc[i].atr1)
    if not np.isfinite(a) or a<=0:return False,"ATR",np.nan
    sg=1 if c["direction"]=="LONG" else -1; v={}
    for k in (1,2):
        b=x.iloc[i+k]; pre=x.iloc[max(0,i+k-5):i+k+1]
        v[f"m{k}_move_atr"]=(float(b.close)-float(x.iloc[i].close))/a*sg
        cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
        v[f"m{k}_close_pos"]=float(cp if c["direction"]=="LONG" else 1-cp)
        v[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
    if not(v["m1_move_atr"]<=.300 and v["m1_close_pos"]>=.140 and v["m2_close_pos"]<=.912):return False,"V7",np.nan
    reclaim=(float(x.iloc[i+2].close)-c["extreme"])/a if c["direction"]=="LONG" else (c["extreme"]-float(x.iloc[i+2].close))/a
    if not(reclaim<=.90 and v["m2_close_pos"]<=.80 and c["wick_percent"]<=.60 and v["m2_move_atr"]<=.15 and v["m2_dir_bars5"]<=4):return False,"V8",np.nan
    rq=(1-min(max(v["m2_close_pos"],0),1))*(1-min(max(c["wick_percent"],0),1)); ri=-v["m2_move_atr"]
    sa=c["sweep_distance"]/c["atr"] if np.isfinite(c["atr"]) and c["atr"]>0 else np.nan
    rts=reclaim/(abs(sa)+.05); itr=ri/(abs(reclaim)+.05); rxw=reclaim*c["wick_percent"]
    f={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,"reversal_impulse":ri,
       "reclaim_x_wick":rxw,"close_x_reclaim":v["m2_close_pos"]*reclaim,"sweep_minus_reclaim":sa-reclaim,
       "impulse_minus_reclaim":ri-reclaim,"quality_balance":rq*itr/(1+rts)}
    sc=score(f)
    if not np.isfinite(sc) or sc<V15_THRESHOLD:return False,"V15",sc
    if reclaim>=RTH and rxw>=WTH:return False,"V27",sc
    return True,"PASS",sc

class Engine:
    def __init__(self,one,startup):
        self.one=one; self.startup=startup; self.running={}; self.pending=[]; self.entry_due=[]
        # Warm session extrema only. Do not generate/emit old signals.
        th=make3(one)
        for _,r in th.iterrows():
            s=r.session
            if s is None: continue
            key=(r.time_ny.date(),s); h=float(r.high); l=float(r.low)
            if key not in self.running:self.running[key]=[h,l]
            else:self.running[key]=[max(self.running[key][0],h),min(self.running[key][1],l)]
        self.last3=th.time_ny.max() if len(th) else None
    def on_closed_minute(self,row,next_live_row):
        self.one=pd.concat([self.one,pd.DataFrame([row])],ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
        th=make3(self.one)
        fresh=th if self.last3 is None else th[th.time_ny>self.last3]
        for _,r in fresh.iterrows(): self.on3(r)
        if len(th): self.last3=th.time_ny.max()
        # If a confirmed trade is due at the just-opened 3m boundary, use the live 1m open.
        t=next_live_row["time_ny"]
        if t.minute%3==0:
            due=[p for p in self.entry_due if p["entry_time"]==t]
            self.entry_due=[p for p in self.entry_due if p["entry_time"]!=t]
            for p in due:
                entry=float(next_live_row["open"]); stop=p["extreme"]-.25 if p["direction"]=="LONG" else p["extreme"]+.25
                risk=entry-stop if p["direction"]=="LONG" else stop-entry
                if risk>0:
                    print("\n"+"!"*72)
                    print("LIVE SHADOW TRADE")
                    print(f"{t.strftime('%Y-%m-%d %H:%M ET')} | {p['session']} | {p['direction']} {SYMBOL}")
                    print(f"Candidate {p['time_ny'].strftime('%H:%M')} | Confirm {p['confirm_time'].strftime('%H:%M')} | Entry {entry} | Stop {stop} | Risk {risk:.2f} | V15 {p['v15_score']:.6f}")
                    print("!"*72+"\n",flush=True)
    def on3(self,r):
        t=r.time_ny; s=r.session
        print(f"CLOSED 3M | {t.strftime('%Y-%m-%d %H:%M ET')} | {s or '-'} | O {r.open} H {r.high} L {r.low} C {r.close}",flush=True)
        # Confirm candidates from immediately previous completed 3m bar.
        due=[p for p in self.pending if p["confirm_time"]==t]
        self.pending=[p for p in self.pending if p["confirm_time"]!=t]
        for p in due:
            ok=float(r.close)>p["body_top"] if p["direction"]=="LONG" else float(r.close)<p["body_bottom"]
            print(f"CONFIRM {'PASS' if ok else 'FAIL'} | {p['session']} {p['direction']} candidate {p['time_ny'].strftime('%H:%M')} -> {t.strftime('%H:%M')}",flush=True)
            if ok:self.entry_due.append({**p,"confirm_time":t,"entry_time":t+pd.Timedelta(minutes=3)})
        if s is None:return
        key=(t.date(),s); h=float(r.high); l=float(r.low); rng=h-l
        if key not in self.running:self.running[key]=[h,l];return
        rh,rl=self.running[key]; cs=[]
        if l<rl:cs.append({"time_ny":t,"session":s,"direction":"LONG","extreme":l,"atr":float(r.atr_20),
          "sweep_distance":rl-l,"wick_percent":float(r.lower_wick/rng) if rng>0 else 0,
          "body_top":max(float(r.open),float(r.close)),"body_bottom":min(float(r.open),float(r.close))})
        if h>rh:cs.append({"time_ny":t,"session":s,"direction":"SHORT","extreme":h,"atr":float(r.atr_20),
          "sweep_distance":h-rh,"wick_percent":float(r.upper_wick/rng) if rng>0 else 0,
          "body_top":max(float(r.open),float(r.close)),"body_bottom":min(float(r.open),float(r.close))})
        self.running[key]=[max(rh,h),min(rl,l)]
        for c in cs:
            ok,stage,sc=frozen_filter(self.one,c)
            print(f"CANDIDATE | {s} {c['direction']} {t.strftime('%H:%M')} | {stage}" + (f" | V15 {sc:.6f}" if np.isfinite(sc) else ""),flush=True)
            if ok:self.pending.append({**c,"v15_score":sc,"confirm_time":t+pd.Timedelta(minutes=3)})

async def main():
    key=os.getenv("MASSIVE_API_KEY")
    if not key:sys.exit("MASSIVE_API_KEY is not set.")
    one=bootstrap(key); start=pd.Timestamp(datetime.now(ET))
    eng=Engine(one,start)
    print("="*72);print("THE ICON — TRUE LIVE BAR-BY-BAR SHADOW TEST");print("="*72)
    print("Massive websocket:",SYMBOL);print("Orders: DISABLED")
    print("Future supersession: DISABLED");print("Confirmation: NEXT FULL 3M CLOSE")
    print("Entry: FOLLOWING LIVE 3M OPEN");print("Started:",start.strftime("%Y-%m-%d %H:%M:%S ET"))
    print("Waiting for NEW live bars... Ctrl+C to stop.\n")
    async with websockets.connect(WS_URL,ping_interval=20,ping_timeout=20,max_size=None) as ws:
        await ws.recv(); await ws.send(json.dumps({"action":"auth","params":key}))
        while True:
            es=json.loads(await ws.recv()); es=es if isinstance(es,list) else [es]
            if any(e.get("status")=="auth_success" for e in es):break
            if any(e.get("status") in {"auth_failed","not_authorized"} for e in es):sys.exit(f"Auth failed: {es}")
        await ws.send(json.dumps({"action":"subscribe","params":f"AM.{SYMBOL}"}))
        pending=None
        async for raw in ws:
            es=json.loads(raw); es=es if isinstance(es,list) else [es]
            for e in es:
                if e.get("ev")!="AM":continue
                ms=e.get("s",e.get("start"))
                if ms is None:continue
                t=pd.Timestamp(datetime.fromtimestamp(float(ms)/1000,tz=UTC).astimezone(ET))
                row={"time_ny":t,"ticker":SYMBOL,"open":e.get("o",e.get("open")),"high":e.get("h",e.get("high")),
                     "low":e.get("l",e.get("low")),"close":e.get("c",e.get("close")),"volume":e.get("v",e.get("volume",0))}
                for c in NUM:row[c]=pd.to_numeric(row[c],errors="coerce")
                if pending is not None and t>pending["time_ny"]:
                    print(f"CLOSED 1M | {pending['time_ny'].strftime('%H:%M ET')} | O {pending['open']} H {pending['high']} L {pending['low']} C {pending['close']}",flush=True)
                    eng.on_closed_minute(pending,row)
                pending=row
if __name__=="__main__":
    try:asyncio.run(main())
    except KeyboardInterrupt:print("\nLive shadow test stopped.")
