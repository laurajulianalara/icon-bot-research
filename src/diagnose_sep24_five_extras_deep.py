#!/usr/bin/env python3
"""Deep trace the five Sep-24 causal extras. Diagnostic only; no strategy changes."""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY=pd.Timestamp("2026-09-24",tz=live.TZ)
TARGETS=[
("02:18","LONDON","SHORT"),("02:54","LONDON","LONG"),("04:21","LONDON","LONG"),
("04:48","LONDON","LONG"),("09:36","NYAM","SHORT")]
NEED=live.NEED

def norm(x):
 x=x.copy();x["time_ny"]=pd.to_datetime(x.time_ny)
 x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ) if x.time_ny.dt.tz is None else x.time_ny.dt.tz_convert(live.TZ)
 return x[NEED]

pieces=[norm(pd.read_parquet(live.HIST))]
for p in Path("data").glob("mnq_*_1m.parquet"):
 try: pieces.append(norm(pd.read_parquet(p)))
 except: pass
one=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny")
one=one[(one.time_ny>=DAY-pd.Timedelta(days=3))&(one.time_ny<DAY+pd.Timedelta(days=1))].reset_index(drop=True)

print("="*100);print("SEP 24 FIVE-EXTRA DEEP TRACE — 3M COMPLETION / SUPERSESSION");print("DIAGNOSTIC ONLY — NO STRATEGY CHANGES");print("="*100)
for hhmm,sess,direction in TARGETS:
 et=DAY+pd.Timedelta(hours=int(hhmm[:2]),minutes=int(hhmm[3:]))
 # entry-time context vs two minutes later/full available day
 contexts=[("AT ENTRY",et),("+1 MIN",et+pd.Timedelta(minutes=1)),("+2 MIN",et+pd.Timedelta(minutes=2))]
 print("\n"+"-"*100);print(f"{hhmm} {sess} {direction}")
 for label,cut in contexts:
  ctx=one[one.time_ny<=cut].copy()
  cand=live.build_candidates(ctx)
  # signal entry E corresponds candidate 3 minutes earlier
  ct=et-pd.Timedelta(minutes=3)
  q=cand[(cand.time_ny==ct)&(cand.session==sess)&(cand.direction==direction)] if not cand.empty else cand
  selected=live.evaluate(ctx)
  hits=[x for x in selected if pd.Timestamp(x["entry_time_et"])==et and x["session"]==sess and x["direction"]==direction]
  print(f"  {label:8} through {cut.strftime('%H:%M')} | candidate {ct.strftime('%H:%M')} exists={not q.empty} | selected={bool(hits)}")
  if not q.empty:
   r=q.iloc[0]
   nxt=r.next_same_extreme_time
   print(f"             candidate extreme={r.extreme} | next_same_extreme_time={nxt if pd.notna(nxt) else 'NONE'}")
 # Show the 3m buckets around entry and any same-direction candidates that appear by +2
 ctx=one[one.time_ny<=et+pd.Timedelta(minutes=2)].copy()
 z=ctx.set_index("time_ny")
 three=z.resample("3min",label="left",closed="left").agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),n=("close","count")).reset_index()
 near=three[(three.time_ny>=et-pd.Timedelta(minutes=6))&(three.time_ny<=et+pd.Timedelta(minutes=3))]
 print("  3M buckets visible by +2:")
 for _,r in near.iterrows():print(f"    {r.time_ny.strftime('%H:%M')} n={int(r.n)} O={r.open} H={r.high} L={r.low} C={r.close}")
 cand=live.build_candidates(ctx)
 if not cand.empty:
  same=cand[(cand.date==DAY.date())&(cand.session==sess)&(cand.direction==direction)]
  print("  Same-direction candidates known by +2:")
  for _,r in same.tail(6).iterrows():print(f"    {r.time_ny.strftime('%H:%M')} extreme={r.extreme} next={r.next_same_extreme_time if pd.notna(r.next_same_extreme_time) else 'NONE'}")
print("\n"+"="*100)
print("READ THIS: If the original candidate's next_same_extreme_time changes from NONE at entry to the entry-time")
print("3m bucket at +2, and selected flips True -> False, supersession is using a 3m candle that was unfinished at entry.")
