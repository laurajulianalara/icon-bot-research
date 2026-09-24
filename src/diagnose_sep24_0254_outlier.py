#!/usr/bin/env python3
"""Deep diagnostic for Sep 24 02:54 LONG outlier vs six canonical trades.
Diagnostic only. No strategy changes/orders.
"""
from pathlib import Path
import pandas as pd,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live
F=Path("data/reports/2026-09-24_good_vs_bad_trajectory.csv")
E=Path("data/reports/2026-09-24_good_vs_bad_entry_features.csv")
if not F.exists() or not E.exists():raise RuntimeError("Run the two Sep24 good-vs-bad diagnostics first.")
t=pd.read_csv(F);e=pd.read_csv(E);t["entry_time"]=pd.to_datetime(t.entry_time);e["entry_time"]=pd.to_datetime(e.entry_time)
target=pd.Timestamp("2026-09-24 02:54:00",tz=live.TZ)
cols=["risk_pts","cand_range","cand_body","wick_pct","atr1","m1_move_atr","m1_close_pos","m2_move_atr","m2_close_pos","reclaim_atr","rejection_quality","reclaim_x_wick","reversal_impulse"]
good=e[e.type=="GOOD"];x=e[e.entry_time==target].iloc[0]
print("="*120);print("SEP 24 02:54 LONG OUTLIER — DEEP COMPARISON");print("="*120)
print("\nENTRY-TIME FEATURES vs GOOD RANGE")
for c in cols:
 lo,hi=good[c].min(),good[c].max();v=x[c];inside=lo<=v<=hi
 print(f"{c:24s} outlier={v:9.4f} | good range {lo:9.4f} .. {hi:9.4f} | {'INSIDE' if inside else 'OUTSIDE'}")
z=t[t.entry_time==target].iloc[0]
print("\nMINUTE TRAJECTORY")
for k in range(3):
 print(f"+{k}m | fav={z[f'm{k}_fav_R']:.3f}R | adv={z[f'm{k}_adv_R']:.3f}R | close={z[f'm{k}_close_R']:.3f}R | extreme_broken={z[f'm{k}_extreme_broken']} | penetration={z[f'm{k}_extreme_pen_pts']:.2f} pts")
print("\nGOOD TRADE RANGES BY MINUTE")
g=t[t.type=="GOOD"]
for k in range(3):
 print(f"+{k}m | fav_R {g[f'm{k}_fav_R'].min():.3f}..{g[f'm{k}_fav_R'].max():.3f} | adv_R {g[f'm{k}_adv_R'].min():.3f}..{g[f'm{k}_adv_R'].max():.3f} | close_R {g[f'm{k}_close_R'].min():.3f}..{g[f'm{k}_close_R'].max():.3f}")
print("\nKEY FACT")
print("02:54 did NOT break the old extreme in its entry minute, but it DID break it during +1 minute.")
print("This script is descriptive only; it does not create a new filter.")
