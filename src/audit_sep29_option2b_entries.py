#!/usr/bin/env python3
"""Read-only Option 2B entry diagnostic for 2026-09-29 ET only.

Uses the existing shadow-live evaluator unchanged. Replays only Sep 29 decision
boundaries causally and prints the candidate 3m candle, T+1, T+2, and T+3 entry
bar for each emitted trade. No strategy/filter/data/execution changes.
"""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ
NEED=live.NEED
DAY=pd.Timestamp("2026-09-29", tz=TZ)
END=DAY+pd.Timedelta(days=1)

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

frames=[]
h=pd.read_parquet(live.HIST)[NEED].copy()
h["time_ny"]=et(h.time_ny)
frames.append(h)

for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(NEED).issubset(q.columns):
            continue
        q=q[NEED].copy()
        q["time_ny"]=et(q.time_ny)
        frames.append(q)
    except Exception:
        pass

one=(pd.concat(frames,ignore_index=True)
     .drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))

# Keep prior bars for ATR/context, but evaluate Sep 29 boundaries only.
one=one[(one.time_ny>=DAY-pd.Timedelta(days=3)) & (one.time_ny<END)].copy().reset_index(drop=True)
today=one[(one.time_ny>=DAY)&(one.time_ny<END)].copy()
boundaries=sorted(t for t in today.time_ny if t.minute%3==0)

emitted={}
daily_count=0

for t in boundaries:
    pos=one.index[one.time_ny==t]
    if len(pos)==0:
        continue
    p=int(pos[-1])
    closed=one.loc[:p-1,NEED].copy()
    op=one.loc[p,NEED].to_dict()

    for x in live.evaluate(closed,live_open=op):
        xt=pd.Timestamp(x["entry_time_et"])
        if xt != t:
            continue
        if daily_count >= 6:
            continue
        ct=pd.Timestamp(x["candidate_time_et"])
        key=(xt,str(x["session"]),str(x["direction"]),ct)
        if key in emitted:
            continue
        emitted[key]=x
        daily_count += 1

def bar_at(ts):
    q=one[one.time_ny==ts]
    return None if q.empty else q.iloc[-1]

def print_bar(label,b):
    if b is None:
        print(f"  {label:<18} MISSING")
        return
    direction="BULL" if float(b.close)>float(b.open) else ("BEAR" if float(b.close)<float(b.open) else "DOJI")
    print(f"  {label:<18} {b.time_ny.strftime('%H:%M')}  O={float(b.open):.2f} H={float(b.high):.2f} L={float(b.low):.2f} C={float(b.close):.2f} V={float(b.volume):.0f}  {direction}")

print("\n"+"="*92)
print("OPTION 2B — SEPTEMBER 29 ENTRY DIAGNOSTIC")
print("="*92)
print("Decision boundaries checked:",len(boundaries))
print("Trades emitted:",len(emitted))

for n,x in enumerate(sorted(emitted.values(),key=lambda z:pd.Timestamp(z["entry_time_et"])),1):
    ct=pd.Timestamp(x["candidate_time_et"])
    etime=pd.Timestamp(x["entry_time_et"])

    # Candidate is a completed 3m candle built from ct, ct+1m, ct+2m.
    cparts=[bar_at(ct+pd.Timedelta(minutes=k)) for k in range(3)]
    valid=[b for b in cparts if b is not None]
    if valid:
        co=float(valid[0].open); ch=max(float(b.high) for b in valid)
        cl=min(float(b.low) for b in valid); cc=float(valid[-1].close)
        cv=sum(float(b.volume) for b in valid)
        cdir="BULL" if cc>co else ("BEAR" if cc<co else "DOJI")
    else:
        co=ch=cl=cc=cv=float("nan"); cdir="MISSING"

    print("\n"+"-"*92)
    print(f"TRADE {n} | {x['session']} | {x['direction']}")
    print(f"Candidate 3m: {ct.strftime('%H:%M')}–{(ct+pd.Timedelta(minutes=2)).strftime('%H:%M')} | O={co:.2f} H={ch:.2f} L={cl:.2f} C={cc:.2f} V={cv:.0f} {cdir}")
    print(f"Candidate extreme: {float(x['stop'])+0.25 if x['direction']=='LONG' else float(x['stop'])-0.25:.2f}")
    print("Candidate 1m components:")
    for k,b in enumerate(cparts):
        print_bar(f"candidate +{k}m",b)

    # Confirmation starts after the 3m candidate has completed.
    t1=ct+pd.Timedelta(minutes=3)
    t2=ct+pd.Timedelta(minutes=4)
    print("Post-candidate confirmation / entry:")
    print_bar("T+1 confirm",bar_at(t1))
    print_bar("T+2 confirm",bar_at(t2))
    print_bar("T+3 ENTRY",bar_at(etime))
    print(f"  Actual entry price: {float(x['entry']):.2f} | Stop: {float(x['stop']):.2f} | V15: {float(x['v15_score']):.6f}")

print("\nREAD-ONLY. Exact existing Option 2B evaluator; Sep 29 only.")
