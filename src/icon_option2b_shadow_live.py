#!/usr/bin/env python3
"""
THE ICON — OPTION 2B SHADOW-LIVE RUNNER

Massive real-time MNQ minute aggregates -> exact 1m/3m Option 2B pipeline
-> immutable final-signal log.

SHADOW ONLY: this program NEVER sends orders.

Important live-timing rule:
Massive AM bars are treated as closed only after the next minute begins.
A candidate is created only from a completed 3-minute candle. V7/V8/V15/V27
are evaluated after m1 and m2 are closed. The final signal/entry is stamped at
the open of T+3, matching the frozen historical engine.
"""

import asyncio, bisect, csv, json, os, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import requests
import websockets

TZ="America/New_York"; ET=ZoneInfo(TZ); UTC=ZoneInfo("UTC")
WS_URL="wss://socket.massive.com/futures"
SYMBOL=os.getenv("ICON_MNQ_SYMBOL","MNQZ6")
RTH=.576132; WTH=.183258; V15_THRESHOLD=.145921011058
HIST="data/mnq_continuous_1m.parquet"
REF_PATH="data/icon_v15_pine_reference.json"
LOG_PATH=Path("data/live/option2b_shadow_signals.csv")
STATE_PATH=Path("data/live/option2b_shadow_state.json")
NEED=["time_ny","ticker","open","high","low","close","volume"]

def session_name(ts):
    m=ts.hour*60+ts.minute
    if 1200<=m<1440:return "ASIA"
    if 120<=m<300:return "LONDON"
    if 570<=m<750:return "NYAM"
    if 810<=m<1020:return "NYPM"
    return None

with open(REF_PATH) as f: REF={k:sorted(float(x) for x in v) for k,v in json.load(f).items()}
SPEC=[("rejection_quality",1,2),("impulse_to_reclaim",1,2),("reclaim_to_sweep",0,1),("reversal_impulse",1,1),("reclaim_x_wick",0,2),("close_x_reclaim",0,2),("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),("quality_balance",1,2)]

def rank(v,a):
    if not np.isfinite(v): return np.nan
    lo=bisect.bisect_left(a,float(v)); hi=bisect.bisect_right(a,float(v))
    return (lo+(hi-lo+1)/2)/len(a) if hi>lo else min(1,max(0,(lo+1)/len(a)))

def score(f):
    p=[]
    for col,hi,w in SPEC:
        r=rank(f[col],REF[col])
        if not np.isfinite(r):return np.nan
        p += [(r if hi else 1-r)]*w
    return float(np.mean(p))

def normalize_time(s):
    x=pd.to_datetime(s)
    return x.tz_localize(TZ) if x.tzinfo is None else x.tz_convert(TZ)

def fetch_today(api_key):
    now=datetime.now(ET); local=pd.Timestamp(now.date(),tz=TZ)
    url=f"https://api.massive.com/futures/v1/aggs/{SYMBOL}"
    params={"resolution":"1min","window_start.gte":local.tz_convert("UTC").isoformat(),
            "window_start.lt":pd.Timestamp(now).tz_convert("UTC").isoformat(),
            "limit":50000,"sort":"window_start.asc","apiKey":api_key}
    r=requests.get(url,params=params,timeout=60); r.raise_for_status()
    out=[]
    for x in r.json().get("results",[]):
        ns=x.get("window_start")
        if ns is None:continue
        t=pd.to_datetime(ns,unit="ns",utc=True).tz_convert(TZ)
        out.append({"time_ny":t,"ticker":SYMBOL,"open":x.get("open"),"high":x.get("high"),
                    "low":x.get("low"),"close":x.get("close"),"volume":x.get("volume",0)})
    return pd.DataFrame(out,columns=NEED)

def bootstrap(api_key):
    hist=pd.read_parquet(HIST)[NEED].copy(); hist["time_ny"]=pd.to_datetime(hist.time_ny)
    if hist.time_ny.dt.tz is None: hist["time_ny"]=hist.time_ny.dt.tz_localize(TZ)
    else: hist["time_ny"]=hist.time_ny.dt.tz_convert(TZ)
    today=fetch_today(api_key)
    start=pd.Timestamp(datetime.now(ET).date(),tz=TZ)-pd.Timedelta(days=3)
    h=hist[hist.time_ny>=start].tail(5000)
    x=pd.concat([h,today],ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny")
    return x.reset_index(drop=True)

def build_candidates(one):
    z=one.set_index("time_ny")
    three=z.resample("3min",label="left",closed="left").agg(ticker=("ticker","last"),open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum"),n=("close","count")).reset_index()
    # A live candidate is legal only when all 3 constituent 1m bars exist.
    three=three[(three.n==3)&three.open.notna()].copy()
    pc=three.close.shift(1)
    three["atr_20"]=pd.concat([three.high-three.low,(three.high-pc).abs(),(three.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
    three["upper_wick"]=three.high-three[["open","close"]].max(axis=1)
    three["lower_wick"]=three[["open","close"]].min(axis=1)-three.low
    three["session"]=three.time_ny.apply(session_name)
    cs=[]
    g=three[three.session.notna()]
    for (d,s),gg in g.groupby([g.time_ny.dt.date,"session"],sort=False):
        rh=rl=None
        for _,r in gg.iterrows():
            if rh is None:rh=float(r.high);rl=float(r.low);continue
            rng=float(r.high-r.low)
            if r.low<rl:cs.append(dict(time_ny=r.time_ny,date=d,session=s,direction="LONG",ticker=r.ticker,extreme=float(r.low),atr=float(r.atr_20),sweep_distance=float(rl-r.low),wick_percent=float(r.lower_wick/rng) if rng>0 else 0))
            if r.high>rh:cs.append(dict(time_ny=r.time_ny,date=d,session=s,direction="SHORT",ticker=r.ticker,extreme=float(r.high),atr=float(r.atr_20),sweep_distance=float(r.high-rh),wick_percent=float(r.upper_wick/rng) if rng>0 else 0))
            rh=max(rh,float(r.high));rl=min(rl,float(r.low))
    if not cs:return pd.DataFrame()
    c=pd.DataFrame(cs).sort_values("time_ny").reset_index(drop=True)
    c["next_same_extreme_time"]=c.groupby(["date","session","direction"]).time_ny.shift(-1)
    return c

def evaluate(one, live_open=None):
    one=one.copy().sort_values("time_ny").reset_index(drop=True)
    pc=one.close.shift(1)
    one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
    cand=build_candidates(one)
    if cand.empty:return []
    idx=pd.Series(one.index,index=one.time_ny).to_dict(); selected=[]
    for _,c in cand.iterrows():
        i=idx.get(c.time_ny)
        if i is None or i<20 or i+3>=len(one):continue
        a=float(one.iloc[i].atr1)
        if not np.isfinite(a) or a<=0:continue
        sg=1 if c.direction=="LONG" else -1; vals={}
        for k in [1,2]:
            b=one.iloc[i+k]; pre=one.iloc[max(0,i+k-5):i+k+1]
            vals[f"m{k}_move_atr"]=(float(b.close)-float(one.iloc[i].close))/a*sg
            cp=(b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
            vals[f"m{k}_close_pos"]=float(cp if c.direction=="LONG" else 1-cp)
            vals[f"m{k}_dir_bars5"]=int(((((pre.close-pre.open)*sg)>0)).sum())
        if not(vals["m1_move_atr"]<=.300 and vals["m1_close_pos"]>=.140 and vals["m2_close_pos"]<=.912):continue
        first2=one.iloc[i+1:i+3]
        reclaim=(float(first2.iloc[-1].close)-float(c.extreme))/a if c.direction=="LONG" else (float(c.extreme)-float(first2.iloc[-1].close))/a
        if not(reclaim<=.90 and vals["m2_close_pos"]<=.80 and float(c.wick_percent)<=.60 and vals["m2_move_atr"]<=.15 and vals["m2_dir_bars5"]<=4):continue
        rq=(1-min(max(vals["m2_close_pos"],0),1))*(1-min(max(float(c.wick_percent),0),1))
        ri=-vals["m2_move_atr"]; ca=float(c.atr)
        sa=float(c.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
        rts=reclaim/(abs(sa)+.05); itr=ri/(abs(reclaim)+.05); rxw=reclaim*float(c.wick_percent)
        f={"rejection_quality":rq,"impulse_to_reclaim":itr,"reclaim_to_sweep":rts,"reversal_impulse":ri,
           "reclaim_x_wick":rxw,"close_x_reclaim":vals["m2_close_pos"]*reclaim,"sweep_minus_reclaim":sa-reclaim,
           "impulse_minus_reclaim":ri-reclaim,"quality_balance":rq*itr/(1+rts)}
        sc=score(f)
        if not np.isfinite(sc) or sc<V15_THRESHOLD:continue
        if reclaim>=RTH and rxw>=WTH:continue
        j=i+3
        # Historical replay can read row j directly. Live execution reaches the
        # entry boundary before that 1m bar is closed, so use the just-opened
        # Massive bar's timestamp/open without leaking its future high/low/close.
        if j < len(one):
            signal=one.iloc[j].time_ny
            entry_ticker=one.iloc[j].ticker
            entry=float(one.iloc[j].open)
        elif j == len(one) and live_open is not None:
            signal=live_open["time_ny"]
            entry_ticker=live_open["ticker"]
            entry=float(live_open["open"])
        else:
            continue
        if pd.notna(c.next_same_extreme_time) and signal>=c.next_same_extreme_time:continue
        if entry_ticker!=c.ticker:continue
        stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
        risk=entry-stop if c.direction=="LONG" else stop-entry
        if risk<=0:continue
        selected.append({"signal_id":f"{signal.isoformat()}|{c.session}|{c.direction}|{c.time_ny.isoformat()}",
                         "date_et":str(signal.date()),"candidate_time_et":c.time_ny.isoformat(),"entry_time_et":signal.isoformat(),
                         "session":c.session,"direction":c.direction,"ticker":c.ticker,"v15_score":sc,"entry":entry,"stop":stop,"risk_points":risk})
    # Do NOT apply the daily cap statelessly here. In live mode the cap must
    # persist across repeated evaluate() calls/restarts and count only signals
    # that were actually emitted. main() enforces the Option 2B 6/day cap.
    return sorted(selected,key=lambda q:q["entry_time_et"])

def load_logged():
    if not LOG_PATH.exists():return set(),{}
    try:
        q=pd.read_csv(LOG_PATH)
        logged=set(q.signal_id.astype(str))
        counts=q.groupby(q.date_et.astype(str)).size().astype(int).to_dict()
        return logged,counts
    except Exception:
        return set(),{}

def append_signal(x):
    LOG_PATH.parent.mkdir(parents=True,exist_ok=True)
    exists=LOG_PATH.exists()
    with LOG_PATH.open("a",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(x.keys()))
        if not exists:w.writeheader()
        w.writerow(x);f.flush();os.fsync(f.fileno())

async def main():
    key=os.getenv("MASSIVE_API_KEY")
    if not key:sys.exit("MASSIVE_API_KEY is not set.")
    one=bootstrap(key); logged,daily_emitted=load_logged()
    print("="*68);print("THE ICON — OPTION 2B SHADOW LIVE");print("="*68)
    print("Contract:",SYMBOL);print("Bootstrapped closed 1m bars:",len(one));print("Orders: DISABLED")
    print("Signal log:",LOG_PATH);print("Waiting for live closed bars...\n")
    async with websockets.connect(WS_URL,ping_interval=20,ping_timeout=20,max_size=None) as ws:
        await ws.recv();await ws.send(json.dumps({"action":"auth","params":key}))
        while True:
            p=json.loads(await ws.recv()); es=p if isinstance(p,list) else [p]
            if any(e.get("status")=="auth_success" for e in es):break
            if any(e.get("status") in {"auth_failed","not_authorized"} for e in es):sys.exit(f"Auth failed: {es}")
        await ws.send(json.dumps({"action":"subscribe","params":f"AM.{SYMBOL}"}))
        pending=None
        async for raw in ws:
            p=json.loads(raw); es=p if isinstance(p,list) else [p]
            for e in es:
                if e.get("ev")!="AM":continue
                ms=e.get("s",e.get("start"))
                if ms is None:continue
                t=datetime.fromtimestamp(float(ms)/1000,tz=UTC).astimezone(ET)
                row={"time_ny":pd.Timestamp(t),"ticker":SYMBOL,"open":e.get("o",e.get("open")),"high":e.get("h",e.get("high")),"low":e.get("l",e.get("low")),"close":e.get("c",e.get("close")),"volume":e.get("v",e.get("volume",0))}
                if pending is not None and row["time_ny"]>pending["time_ny"]:
                    one=pd.concat([one,pd.DataFrame([pending])],ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
                    print(f"CLOSED 1M | {pending['time_ny'].strftime('%Y-%m-%d %H:%M ET')} | O {pending['open']} H {pending['high']} L {pending['low']} C {pending['close']}",flush=True)
                    for x in evaluate(one, live_open=row):
                        # Never retro-log bootstrap history. A live signal is emitted only at the
                        # just-opened minute proving its entry boundary has arrived prospectively.
                        if x["signal_id"] not in logged and pd.Timestamp(x["entry_time_et"])==row["time_ny"]:
                            day=x["date_et"]
                            if daily_emitted.get(day,0)>=6:
                                continue
                            append_signal(x);logged.add(x["signal_id"])
                            daily_emitted[day]=daily_emitted.get(day,0)+1
                            print("\n"+"!"*68);print("FINAL OPTION 2B SHADOW TRADE — LOGGED BEFORE OUTCOME")
                            print(f"{x['entry_time_et']} | {x['session']} | {x['direction']} {x['ticker']}")
                            print(f"Entry {x['entry']} | Stop {x['stop']} | Risk {x['risk_points']} | V15 {x['v15_score']:.6f}")
                            print("!"*68+"\n",flush=True)
                pending=row

if __name__=="__main__":
    try:asyncio.run(main())
    except KeyboardInterrupt:print("\nShadow live stopped.")
