import pandas as pd
import numpy as np

IN="data/v8_volatility_forensics.csv"; OUT="data/v8_worst_streak_detail.csv"
q=pd.read_csv(IN)
q["candidate_time"]=pd.to_datetime(q["candidate_time"],utc=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
q=q.sort_values("candidate_time").reset_index(drop=True)

# Locate every loss streak and isolate the longest.
runs=[];start=None
for i,w in enumerate(q.win):
    if w==0 and start is None:start=i
    if w==1 and start is not None:
        runs.append((start,i-1,i-start));start=None
if start is not None:runs.append((start,len(q)-1,len(q)-start))
mx=max(x[2] for x in runs)
worst=[x for x in runs if x[2]==mx]
print(f"=== WORST CONSECUTIVE LOSS STREAK(S): {mx} ===")
allrows=[]
for n,(a,b,L) in enumerate(worst,1):
    z=q.iloc[a:b+1].copy()
    z["ny_time"]=z.candidate_time.dt.tz_convert("America/New_York")
    z["ny_date"]=z.ny_time.dt.date
    print(f"\nSTREAK {n}: {z.ny_time.iloc[0]} -> {z.ny_time.iloc[-1]}")
    print(f"Spans {z.ny_date.nunique()} trading date(s)")
    print("By date:")
    print(z.groupby("ny_date").size().to_string())
    print("By session:")
    print(z.groupby("session").size().to_string())
    cols=["ny_time","session","vol_bin","atr20","early_reclaim_atr","wick_percent","m2_close_pos","m2_move_atr","m2_dir_bars5","sr_strength","sweep_atr"]
    print("\nTrades:")
    print(z[cols].round(3).to_string(index=False))
    allrows.append(z)

w=pd.concat(allrows,ignore_index=True);w.to_csv(OUT,index=False)

# Compare the exact worst streak against winners and all other losses.
print("\n=== WORST-STREAK SIGNATURE VS WINNERS ===")
features=["early_reclaim_atr","wick_percent","m2_close_pos","m2_move_atr","m2_dir_bars5","atr20","vol_ratio_20_60","vol_ratio_20_240","range_ratio","sr_strength","sweep_atr"]
for f in features:
    a=w[f].mean(); b=q.loc[q.win.eq(1),f].mean()
    print(f"{f:20s} worst={a:.3f} winners={b:.3f} diff={a-b:+.3f}")
print("\nSaved:",OUT)
