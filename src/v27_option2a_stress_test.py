import pandas as pd, numpy as np
q=pd.read_csv("data/v21_option2_loss_buckets.csv")
q["candidate_time"]=pd.to_datetime(q.candidate_time,utc=True);q=q.sort_values("candidate_time").reset_index(drop=True)
q["win"]=(q.outcome=="WIN").astype(int);q["r"]=np.where(q.win==1,4.,-1.)
# V26 winner: upper 30% tails of reclaim and reclaim_x_wick, reject only when BOTH bad.
rth=q.early_reclaim_atr.quantile(.70);wth=q.reclaim_x_wick.quantile(.70)
z=q[~((q.early_reclaim_atr>=rth)&(q.reclaim_x_wick>=wth))].copy()
et=z.candidate_time.dt.tz_convert("America/New_York");z["date"]=et.dt.date;z["month"]=et.dt.to_period("M").astype(str)
def maxdd(x):
 e=x.r.cumsum();return float((e.cummax()-e).max())
def streak(x):
 cur=mx=0
 for w in x.win:cur=0 if w else cur+1;mx=max(mx,cur)
 return mx
print("=== V27 OPTION 2A STRESS TEST ===")
print(f"Thresholds: early_reclaim_atr < {rth:.6f} OR reclaim_x_wick < {wth:.6f}")
print(f"Trades {len(z)} | active days {z.date.nunique()} | active TPD {len(z)/z.date.nunique():.2f} | WR {100*z.win.mean():.2f}% | net {z.r.sum():.0f}R | exp {z.r.mean():.2f}R | DD {maxdd(z):.0f}R | streak {streak(z)}")
print("\nMONTHLY")
m=z.groupby("month").apply(lambda x:pd.Series({"trades":len(x),"wr":100*x.win.mean(),"net_r":x.r.sum(),"max_dd_r":maxdd(x),"max_streak":streak(x)}),include_groups=False)
print(m.round(2).to_string())
# 10 chronological folds
print("\n10-FOLD")
parts=np.array_split(z,10)
for i,x in enumerate(parts,1):print(f"{i:2d}: {len(x):3d} trades | WR {100*x.win.mean():5.2f}% | net {x.r.sum():6.0f}R | DD {maxdd(x):.0f}R | streak {streak(x)}")
# daily risk
d=z.groupby("date").apply(lambda x:pd.Series({"trades":len(x),"wins":x.win.sum(),"losses":(1-x.win).sum(),"net_r":x.r.sum(),"dd_r":maxdd(x)}),include_groups=False)
print(f"\nDays >=3R DD {(d.dd_r>=3).sum()} | >=4R {(d.dd_r>=4).sum()} | >=5R {(d.dd_r>=5).sum()} | max trades/day {int(d.trades.max())}")
z.to_csv("data/v27_option2a_trades.csv",index=False);m.to_csv("data/v27_option2a_monthly.csv")
