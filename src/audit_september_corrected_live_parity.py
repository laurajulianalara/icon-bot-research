#!/usr/bin/env python3
"""THE ICON — September corrected-live parity audit.

READ-ONLY. Uses the frozen September report as benchmark and evaluates only
benchmark entry boundaries plus every 3-minute session boundary in September.
Counts exact benchmark matches, missing benchmark trades, and causal extras.
No strategy thresholds or market data are changed.
"""
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ=live.TZ
NEED=live.NEED
REPORT=Path("data/reports/2026-09_trades.csv")

def et(s):
    x=pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

# Assemble cached data only.
frames=[]
h=pd.read_parquet(live.HIST)[NEED].copy(); h["time_ny"]=et(h.time_ny); frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q=pd.read_parquet(p)
        if not set(NEED).issubset(q.columns): continue
        q=q[NEED].copy(); q["time_ny"]=et(q.time_ny); frames.append(q)
    except Exception: pass
one=(pd.concat(frames,ignore_index=True)
     .drop_duplicates(["time_ny","ticker"],keep="last")
     .sort_values("time_ny").reset_index(drop=True))
one=one[(one.time_ny>=pd.Timestamp("2026-08-28",tz=TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=TZ))].copy()

if not REPORT.exists():
    raise SystemExit("Missing frozen benchmark: data/reports/2026-09_trades.csv")
b=pd.read_csv(REPORT)
b["entry_time"]=et(b["entry_time"])
b["candidate_time"]=et(b["candidate_time"])
b=b[(b.entry_time.dt.year==2026)&(b.entry_time.dt.month==9)].copy()
print("="*86)
print("THE ICON — SEPTEMBER CORRECTED-LIVE PARITY AUDIT")
print("="*86)
print("Frozen benchmark trades:",len(b))

# Exact identity deliberately excludes price floats; prices are checked separately.
def key_b(r):
    return (pd.Timestamp(r.entry_time),str(r.session),str(r.direction),pd.Timestamp(r.candidate_time))
def key_s(x):
    return (pd.Timestamp(x["entry_time_et"]),str(x["session"]),str(x["direction"]),pd.Timestamp(x["candidate_time_et"]))

bench={key_b(r):r for _,r in b.iterrows()}
bench_times=set(b.entry_time)

# Candidate signals can only enter at 3-minute boundaries. Evaluate every such
# session boundary, not every minute, while preserving true causal data.
sep=one[(one.time_ny>=pd.Timestamp("2026-09-01",tz=TZ))&
        (one.time_ny<pd.Timestamp("2026-10-01",tz=TZ))].copy()
boundaries=[t for t in sep.time_ny if t.minute%3==0 and live.session_name(t) is not None]
# Also force every frozen benchmark boundary in case a timestamp is unusual.
boundaries=sorted(set(boundaries)|bench_times)

emitted={}
daily_count={}
for n,t in enumerate(boundaries,1):
    pos=one.index[one.time_ny==t]
    if len(pos)==0: continue
    p=int(pos[-1])
    closed=one.loc[:p-1,NEED].tail(6500).copy()
    op=one.loc[p,NEED].to_dict()
    for x in live.evaluate(closed,live_open=op):
        if pd.Timestamp(x["entry_time_et"])!=t: continue
        day=str(x["date_et"])
        # Mirror live main(): only actually emitted final signals consume cap.
        if daily_count.get(day,0)>=6: continue
        k=key_s(x)
        if k in emitted: continue
        emitted[k]=x
        daily_count[day]=daily_count.get(day,0)+1
    if n%500==0: print(f"Checked {n}/{len(boundaries)} boundaries...")

ek=set(emitted); bk=set(bench)
matched=sorted(ek&bk)
missing=sorted(bk-ek)
extras=sorted(ek-bk)

price_mismatch=[]
for k in matched:
    r=bench[k]; x=emitted[k]
    if abs(float(r.entry)-float(x["entry"]))>1e-9 or abs(float(r.stop)-float(x["stop"]))>1e-9:
        price_mismatch.append((k,float(r.entry),float(x["entry"]),float(r.stop),float(x["stop"])))

print("\n"+"="*86)
print("RESULT")
print("="*86)
print("Historical benchmark:",len(bk))
print("Causal/live emitted:",len(ek))
print("MATCHED:",len(matched))
print("MISSING:",len(missing))
print("EXTRAS:",len(extras))
print("MATCHED PRICE/STOP MISMATCHES:",len(price_mismatch))

if missing:
    print("\nFIRST 20 MISSING")
    for k in missing[:20]: print(k)
if extras:
    print("\nFIRST 20 EXTRAS")
    for k in extras[:20]:
        x=emitted[k]
        print(k,"entry",x["entry"],"stop",x["stop"],"v15",round(float(x["v15_score"]),6))
if price_mismatch:
    print("\nPRICE/STOP MISMATCHES")
    for x in price_mismatch[:20]: print(x)

if len(matched)==75 and not missing and not extras and not price_mismatch:
    print("\n🎉 EXACT 75/75 CAUSAL PARITY.")
elif len(matched)==75 and not missing:
    print("\nALL 75 BENCHMARK TRADES SURVIVE. Remaining work is extras only.")
else:
    print("\nParity not complete yet. Use missing/extras above for the next focused patch.")

print("\nREAD-ONLY: no strategy thresholds, reports, or market data changed.")
