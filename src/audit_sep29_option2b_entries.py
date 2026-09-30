#!/usr/bin/env python3
"""Read-only Option 2B entry diagnostic for 2026-09-29 ET only.

Fetches Sep 29 MNQZ6 1-minute bars directly from Massive, uses prior local
historical bars only as warm-up context, and replays the existing Option 2B
shadow-live evaluator unchanged. Prints candidate 3m candle, T+1, T+2 and
T+3 entry bar. No strategy/filter/threshold/execution changes.
"""
from pathlib import Path
import os, sys, requests
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ; NEED=live.NEED; NUMERIC=live.NUMERIC
DAY=pd.Timestamp("2026-09-29",tz=TZ)
END=DAY+pd.Timedelta(days=1)
SYMBOL=os.getenv("ICON_MNQ_SYMBOL","MNQZ6")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

def fetch_massive_day():
    key=os.getenv("MASSIVE_API_KEY")
    if not key:
        sys.exit("MASSIVE_API_KEY is not set.")
    url=f"https://api.massive.com/futures/v1/aggs/{SYMBOL}"
    params={
        "resolution":"1min",
        "window_start.gte":DAY.tz_convert("UTC").isoformat(),
        "window_start.lt":END.tz_convert("UTC").isoformat(),
        "limit":50000,
        "sort":"window_start.asc",
        "apiKey":key,
    }
    r=requests.get(url,params=params,timeout=60)
    r.raise_for_status()
    rows=[]
    for x in r.json().get("results",[]):
        ns=x.get("window_start")
        if ns is None: continue
        t=pd.to_datetime(ns,unit="ns",utc=True).tz_convert(TZ)
        rows.append({
            "time_ny":t,"ticker":SYMBOL,
            "open":x.get("open"),"high":x.get("high"),
            "low":x.get("low"),"close":x.get("close"),
            "volume":x.get("volume",0),
        })
    q=pd.DataFrame(rows,columns=NEED)
    for c in NUMERIC:
        q[c]=pd.to_numeric(q[c],errors="coerce")
    return q.sort_values("time_ny").drop_duplicates(["time_ny","ticker"],keep="last").reset_index(drop=True)

# Warm-up history only; Sep 29 itself comes from Massive.
h=pd.read_parquet(live.HIST)[NEED].copy()
h["time_ny"]=et(h.time_ny)
for c in NUMERIC:
    h[c]=pd.to_numeric(h[c],errors="coerce")
h=h[(h.time_ny<DAY)&(h.time_ny>=DAY-pd.Timedelta(days=5))].copy()

today=fetch_massive_day()
if today.empty:
    sys.exit(f"Massive returned 0 one-minute bars for {SYMBOL} on 2026-09-29 ET.")

print(f"Massive Sep 29 bars fetched: {len(today)}")
print(f"First bar: {today.time_ny.min()}")
print(f"Last bar:  {today.time_ny.max()}")

one=(pd.concat([h,today],ignore_index=True)
     .drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))

boundaries=sorted(t for t in today.time_ny if t.minute%3==0)

# One evaluation only — no 460 repeated full-history evaluations.
all_signals=live.evaluate(one)
day_signals=sorted(
    [x for x in all_signals if DAY <= pd.Timestamp(x["entry_time_et"]) < END],
    key=lambda z:pd.Timestamp(z["entry_time_et"])
)[:6]
emitted={
    (pd.Timestamp(x["entry_time_et"]),str(x["session"]),str(x["direction"]),pd.Timestamp(x["candidate_time_et"])):x
    for x in day_signals
}

def bar_at(ts):
    q=one[one.time_ny==ts]
    return None if q.empty else q.iloc[-1]

def print_bar(label,b):
    if b is None:
        print(f"  {label:<18} MISSING"); return
    d="BULL" if float(b.close)>float(b.open) else ("BEAR" if float(b.close)<float(b.open) else "DOJI")
    print(f"  {label:<18} {b.time_ny.strftime('%H:%M')}  O={float(b.open):.2f} H={float(b.high):.2f} L={float(b.low):.2f} C={float(b.close):.2f} V={float(b.volume):.0f}  {d}")

print("\n"+"="*96)
print("OPTION 2B — SEPTEMBER 29 ENTRY DIAGNOSTIC — MASSIVE 1M")
print("="*96)
print("Decision boundaries checked:",len(boundaries))
print("Trades emitted:",len(emitted))

for n,x in enumerate(sorted(emitted.values(),key=lambda z:pd.Timestamp(z["entry_time_et"])),1):
    ct=pd.Timestamp(x["candidate_time_et"]); entry_t=pd.Timestamp(x["entry_time_et"])
    cparts=[bar_at(ct+pd.Timedelta(minutes=k)) for k in range(3)]
    valid=[b for b in cparts if b is not None]
    co=float(valid[0].open); ch=max(float(b.high) for b in valid)
    cl=min(float(b.low) for b in valid); cc=float(valid[-1].close)
    cv=sum(float(b.volume) for b in valid)
    cd="BULL" if cc>co else ("BEAR" if cc<co else "DOJI")
    extreme=float(x["stop"])+.25 if x["direction"]=="LONG" else float(x["stop"])-.25

    print("\n"+"-"*96)
    print(f"TRADE {n} | {x['session']} | {x['direction']}")
    print(f"Candidate 3m: {ct.strftime('%H:%M')}–{(ct+pd.Timedelta(minutes=2)).strftime('%H:%M')} | O={co:.2f} H={ch:.2f} L={cl:.2f} C={cc:.2f} V={cv:.0f} {cd}")
    print(f"Candidate extreme: {extreme:.2f}")
    print("Candidate 1m components:")
    for k,b in enumerate(cparts): print_bar(f"candidate +{k}m",b)
    print("Post-candidate confirmation / entry:")
    print_bar("T+1 confirm",bar_at(ct+pd.Timedelta(minutes=3)))
    print_bar("T+2 confirm",bar_at(ct+pd.Timedelta(minutes=4)))
    print_bar("T+3 ENTRY",bar_at(entry_t))
    print(f"  Actual entry price: {float(x['entry']):.2f} | Stop: {float(x['stop']):.2f} | V15: {float(x['v15_score']):.6f}")

print("\nREAD-ONLY. Sep 29 fetched directly from Massive; Option 2B evaluator unchanged.")
