#!/usr/bin/env python3
"""September 2026 causal research: Option 2B candidates + exhaustion confirmation.

RESEARCH ONLY. Does not modify production Option 2B.

Rules for this first pass:
- Existing Option 2B candidate/filter logic must qualify causally at candidate completion.
- Exhaustion candle = final 1m bar of the 3m extreme candidate.
- Exhaustion volume >= 1.50x median volume of prior 20 completed 1m bars.
- Exhaustion candle can NEVER be the entry.
- Within next 6 completed 1m bars, require reversal structure:
    LONG: confirmation closes above top of exhaustion BODY and above prior bar high.
    SHORT: confirmation closes below bottom of exhaustion BODY and below prior bar low.
- Entry = next 1m bar OPEN after confirmation closes.
- Stop = candidate extreme +/- 0.25.
- Outcomes tested 1R..6R, same-bar stop conservatively wins priority over target.
- Max 6 accepted trades/day.
"""
from pathlib import Path
import os,sys,requests
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ; NEED=live.NEED; NUMERIC=live.NUMERIC
START=pd.Timestamp("2026-09-01",tz=TZ); END=pd.Timestamp("2026-10-01",tz=TZ)
SYMBOL=os.getenv("ICON_MNQ_SYMBOL","MNQZ6")
VOL_MULT=1.50; LOOKBACK=20; MAX_CONFIRM=6

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

def fetch_month():
    key=os.getenv("MASSIVE_API_KEY")
    if not key: sys.exit("MASSIVE_API_KEY is not set.")
    url=f"https://api.massive.com/futures/v1/aggs/{SYMBOL}"
    params={"resolution":"1min","window_start.gte":START.tz_convert("UTC").isoformat(),
            "window_start.lt":END.tz_convert("UTC").isoformat(),"limit":50000,
            "sort":"window_start.asc","apiKey":key}
    rows=[]; next_url=url
    while next_url:
        r=requests.get(next_url,params=params if next_url==url else {"apiKey":key},timeout=90)
        r.raise_for_status(); js=r.json()
        for x in js.get("results",[]):
            ns=x.get("window_start")
            if ns is None: continue
            rows.append({"time_ny":pd.to_datetime(ns,unit="ns",utc=True).tz_convert(TZ),
                         "ticker":SYMBOL,"open":x.get("open"),"high":x.get("high"),
                         "low":x.get("low"),"close":x.get("close"),"volume":x.get("volume",0)})
        next_url=js.get("next_url")
        params={}
    q=pd.DataFrame(rows,columns=NEED)
    for c in NUMERIC:q[c]=pd.to_numeric(q[c],errors="coerce")
    return q.drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)

def qualifying_candidates(one):
    # Build candidates once, then reproduce evaluator filters using only bars available
    # through the completed 3m candidate. No next_same_extreme_time hindsight gate.
    pc=one.close.shift(1)
    one=one.copy()
    one["atr1"]=pd.concat([one.high-one.low,(one.high-pc).abs(),(one.low-pc).abs()],axis=1).max(axis=1).rolling(20).mean()
    cand=live.build_candidates(one)
    idx=pd.Series(one.index,index=one.time_ny).to_dict(); out=[]
    for _,c in cand.iterrows():
        i=idx.get(c.time_ny)
        if i is None or i<20 or i+2>=len(one):continue
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
           "reclaim_x_wick":rxw,"close_x_reclaim":vals["m2_close_pos"]*reclaim,
           "sweep_minus_reclaim":sa-reclaim,"impulse_minus_reclaim":ri-reclaim,
           "quality_balance":rq*itr/(1+rts)}
        sc=live.score(f)
        if not np.isfinite(sc) or sc<live.V15_THRESHOLD:continue
        if reclaim>=live.RTH and rxw>=live.WTH:continue
        out.append((c,i,sc))
    return out

def main():
    print("Fetching September 2026 MNQ 1m from Massive...")
    month=fetch_month()
    print("Bars fetched:",len(month))
    # Local prior bars only for warm-up context.
    h=pd.read_parquet(live.HIST)[NEED].copy();h["time_ny"]=et(h.time_ny)
    for c in NUMERIC:h[c]=pd.to_numeric(h[c],errors="coerce")
    h=h[(h.time_ny<START)&(h.time_ny>=START-pd.Timedelta(days=5))]
    one=pd.concat([h,month],ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)

    accepted=[]; perday={}
    for c,i,sc in qualifying_candidates(one):
        # Candidate 3m consists i,i+1,i+2. Exhaustion = final minute i+2.
        exi=i+2
        if exi>=len(one):continue
        ex=one.iloc[exi]
        prior=one.iloc[max(0,exi-LOOKBACK):exi]
        med=float(prior.volume.median()) if len(prior) else np.nan
        if not np.isfinite(med) or med<=0 or float(ex.volume)<VOL_MULT*med:continue

        body_top=max(float(ex.open),float(ex.close)); body_bot=min(float(ex.open),float(ex.close))
        conf_i=None
        for j in range(exi+1,min(exi+1+MAX_CONFIRM,len(one))):
            b=one.iloc[j]; prev=one.iloc[j-1]
            if live.session_name(b.time_ny)!=c.session:break
            if c.direction=="LONG":
                ok=float(b.close)>body_top and float(b.close)>float(prev.high)
            else:
                ok=float(b.close)<body_bot and float(b.close)<float(prev.low)
            if ok:
                conf_i=j;break
        if conf_i is None or conf_i+1>=len(one):continue
        ent=one.iloc[conf_i+1]
        if live.session_name(ent.time_ny)!=c.session:continue
        day=str(ent.time_ny.date())
        if not (START<=ent.time_ny<END) or perday.get(day,0)>=6:continue
        entry=float(ent.open)
        stop=float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
        risk=entry-stop if c.direction=="LONG" else stop-entry
        if risk<=0:continue
        accepted.append({"entry_i":conf_i+1,"date":day,"session":c.session,"direction":c.direction,
                         "candidate":c.time_ny,"exhaustion":ex.time_ny,"confirmation":one.iloc[conf_i].time_ny,
                         "entry_time":ent.time_ny,"entry":entry,"stop":stop,"risk":risk,
                         "ex_volume":float(ex.volume),"vol_ratio":float(ex.volume)/med,"v15":sc})
        perday[day]=perday.get(day,0)+1

    print("\nRULES")
    print(f"Volume spike: exhaustion volume >= {VOL_MULT:.2f}x prior {LOOKBACK}-bar median")
    print(f"Confirmation window: next {MAX_CONFIRM} completed 1m bars")
    print("LONG confirmation: close > exhaustion body top AND > prior 1m high")
    print("SHORT confirmation: close < exhaustion body bottom AND < prior 1m low")
    print("Entry: next 1m OPEN after confirmation")
    print("Same-bar stop/target: STOP first (conservative)")
    print("\nAccepted trades:",len(accepted))

    print("\nRR   Trades   Wins   Losses    WR%      PnL(R)    PnL@$300   MaxDD(R)   MaxDD@$300")
    for R in range(1,7):
        wins=losses=0; pnl=[]; equity=peak=ddmax=0.0
        for t in accepted:
            target=t["entry"]+(R*t["risk"] if t["direction"]=="LONG" else -R*t["risk"])
            result=None
            # Outcome until session end; no future signal info used for entry.
            for k in range(t["entry_i"],len(one)):
                b=one.iloc[k]
                if live.session_name(b.time_ny)!=t["session"] or str(b.time_ny.date())!=t["date"]:break
                if t["direction"]=="LONG":
                    hitS=float(b.low)<=t["stop"]; hitT=float(b.high)>=target
                else:
                    hitS=float(b.high)>=t["stop"]; hitT=float(b.low)<=target
                if hitS: result=-1;break
                if hitT: result=R;break
            if result is None: result=0
            pnl.append(result)
            if result>0:wins+=1
            elif result<0:losses+=1
            equity+=result;peak=max(peak,equity);ddmax=max(ddmax,peak-equity)
        wr=100*wins/(wins+losses) if wins+losses else 0
        pr=sum(pnl)
        print(f"{R:>2}R  {len(accepted):>6} {wins:>6} {losses:>8} {wr:>7.2f} {pr:>11.2f} {pr*300:>11.0f} {ddmax:>10.2f} {ddmax*300:>12.0f}")

    print("\nFIRST 30 ACCEPTED ENTRIES")
    for t in accepted[:30]:
        print(f"{t['entry_time']} | {t['session']:<6} {t['direction']:<5} | ex {t['exhaustion'].strftime('%H:%M')} volx {t['vol_ratio']:.2f} | confirm {t['confirmation'].strftime('%H:%M')} | entry {t['entry']:.2f} stop {t['stop']:.2f} risk {t['risk']:.2f}")

if __name__=="__main__":main()
