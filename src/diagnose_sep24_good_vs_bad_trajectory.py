#!/usr/bin/env python3
"""Sep24 GOOD vs BAD trajectory diagnostic from entry through +2 minutes.
Diagnostic only. No strategy changes/orders. Uses post-entry bars ONLY for analysis,
not as an entry-time filter.
"""
from pathlib import Path
import pandas as pd,numpy as np,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live
DAY=pd.Timestamp("2026-09-24",tz=live.TZ);END=DAY+pd.Timedelta(days=1)
SIG=Path("data/reports/2026-09-24_true_bar_by_bar.csv")
def norm(x):
 x=x.copy();x["time_ny"]=pd.to_datetime(x.time_ny);x["time_ny"]=x.time_ny.dt.tz_localize(live.TZ) if x.time_ny.dt.tz is None else x.time_ny.dt.tz_convert(live.TZ);return x[live.NEED]
pieces=[norm(pd.read_parquet(live.HIST))]
for p in Path("data").glob("mnq_*_1m.parquet"):
 try:
  x=norm(pd.read_parquet(p))
  if ((x.time_ny>=DAY)&(x.time_ny<END)).any():pieces.append(x)
 except:pass
one=pd.concat(pieces,ignore_index=True).drop_duplicates(["time_ny","ticker"],keep="last").sort_values("time_ny").reset_index(drop=True)
one["atr1"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
idx={t:i for i,t in enumerate(one.time_ny)}
tr=pd.read_csv(SIG);tr["entry_time"]=pd.to_datetime(tr.entry_time_et)
rep=pd.read_csv("data/reports/2026-09_trades.csv");rep["entry_time"]=pd.to_datetime(rep.entry_time)
rep["entry_time"]=rep.entry_time.dt.tz_localize(live.TZ) if rep.entry_time.dt.tz is None else rep.entry_time.dt.tz_convert(live.TZ)
canon=set(zip(rep.entry_time,rep.session,rep.direction));rows=[]
for _,t in tr.sort_values("entry_time").iterrows():
 et=t.entry_time;i=idx[et];entry=float(t.entry);stop=float(t.stop);risk=abs(entry-stop);sg=1 if t.direction=="LONG" else -1
 rec={"entry_time":et,"type":"GOOD" if (et,t.session,t.direction) in canon else "BAD_EXTRA","session":t.session,"direction":t.direction,"entry":entry,"stop":stop,"risk_pts":risk}
 for k in range(3):
  b=one.iloc[i+k];a=float(b.atr1)
  favorable=(float(b.high)-entry) if sg==1 else (entry-float(b.low))
  adverse=(entry-float(b.low)) if sg==1 else (float(b.high)-entry)
  close_move=(float(b.close)-entry)*sg
  old_extreme=stop+.25 if sg==1 else stop-.25
  penetration=(old_extreme-float(b.low)) if sg==1 else (float(b.high)-old_extreme)
  rng=float(b.high-b.low)
  closepos=(float(b.close-b.low)/rng) if rng>0 else .5
  if sg==-1:closepos=1-closepos
  rec.update({f"m{k}_fav_pts":favorable,f"m{k}_adv_pts":adverse,f"m{k}_fav_R":favorable/risk if risk else np.nan,f"m{k}_adv_R":adverse/risk if risk else np.nan,f"m{k}_close_R":close_move/risk if risk else np.nan,f"m{k}_extreme_pen_pts":penetration,f"m{k}_extreme_broken":penetration>0,f"m{k}_close_pos":closepos,f"m{k}_range_atr":rng/a if a else np.nan})
 rows.append(rec)
r=pd.DataFrame(rows);pd.set_option("display.max_columns",None);pd.set_option("display.width",280)
print("="*160);print("SEP 24 — GOOD vs BAD: ENTRY → +1 → +2 MINUTE TRAJECTORY");print("Post-entry data is diagnostic only. Goal: find earliest causal separation before full 3m confirmation.");print("="*160);print(r.round(4).to_string(index=False))
nums=[c for c in r.columns if c.startswith(("m0_","m1_","m2_"))]
print("\nGROUP AVERAGES");print(r.groupby("type")[nums].mean(numeric_only=True).round(4).to_string())
print("\nPERFECT SINGLE-FEATURE SEPARATION BY TIME (today only; NOT a proposed filter)")
for k in range(3):
 found=False
 for f in [x for x in nums if x.startswith(f"m{k}_") and not x.endswith("_broken")]:
  g=r[r.type=="GOOD"][f].dropna();b=r[r.type=="BAD_EXTRA"][f].dropna()
  if len(g) and len(b):
   if g.min()>b.max():print(f"+{k}m {f}: GOOD > BAD | good_min={g.min():.4f} bad_max={b.max():.4f}");found=True
   elif g.max()<b.min():print(f"+{k}m {f}: GOOD < BAD | good_max={g.max():.4f} bad_min={b.min():.4f}");found=True
 if not found:print(f"+{k}m: no perfect numeric single-feature separator")
print("\nEXTREME BREAK COUNTS")
for k in range(3):
 for typ,g in r.groupby("type"):print(f"+{k}m {typ}: {int(g[f'm{k}_extreme_broken'].sum())}/{len(g)} broke prior candidate extreme")
out=Path("data/reports/2026-09-24_good_vs_bad_trajectory.csv");r.to_csv(out,index=False);print("\nSaved:",out)
