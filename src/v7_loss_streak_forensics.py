import pandas as pd
import numpy as np

IN="data/v7_base_trade_quality.parquet"; OUT="data/v7_loss_streak_forensics.csv"
d=pd.read_parquet(IN).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)
q=d[(d.early_reclaim_atr<=.90)&(d.m2_close_pos<=.80)&(d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)].copy()
q["win"]=(q.outcome=="WIN").astype(int);q["date"]=q.candidate_time.dt.date
# Identify losses that belong to streaks of 3+ consecutive losses.
grp=q.win.cumsum();sizes=q.assign(loss=1-q.win).groupby(grp).loss.transform("sum")
q["bad_streak_loss"]=(q.win.eq(0)&sizes.ge(3))
features=["early_reclaim_atr","m2_close_pos","wick_percent","m2_move_atr","m2_dir_bars5","early_adverse_atr","m1_close_pos","m2_body_atr","sr_dist_atr","sweep_atr","sr_strength_050","sr_touches_030"]
rows=[]
bad=q[q.bad_streak_loss]; normal=q[~q.bad_streak_loss]
for f in features:
 a=bad[f].dropna();b=normal[f].dropna()
 if len(a) and len(b):
  p=np.sqrt((a.var()+b.var())/2);eff=(a.mean()-b.mean())/p if p>0 else 0
  rows.append((f,len(a),a.mean(),b.mean(),eff,abs(eff)))
r=pd.DataFrame(rows,columns=["feature","streak_n","streak_mean","other_mean","effect","abs_effect"]).sort_values("abs_effect",ascending=False)
r.drop(columns="abs_effect").to_csv(OUT,index=False)
print("=== LOSS-STREAK FORENSICS (3+ CONSECUTIVE LOSSES) ===")
print("Finalist trades:",len(q),"| losses inside 3+ streaks:",len(bad))
print("\nFEATURE DIFFERENCES:")
print(r.drop(columns="abs_effect").round(3).to_string(index=False))
print("\nSESSION CONCENTRATION:")
print(pd.crosstab(q.session,q.bad_streak_loss,normalize="columns").mul(100).round(2).to_string())
print("\nMONTH CONCENTRATION:")
tmp=q.assign(month=q.candidate_time.dt.strftime("%Y-%m"))
print(pd.crosstab(tmp.month,tmp.bad_streak_loss,normalize="columns").mul(100).round(2).to_string())
# Examine trade position/day load: are streak losses later in overtraded days?
q["trade_num_day"]=q.groupby("date").cumcount()+1;q["day_total"]=q.groupby("date").win.transform("size")
print("\nTRADE POSITION / DAY LOAD:")
print(q.groupby("bad_streak_loss")[["trade_num_day","day_total"]].mean().round(2).to_string())
print("\nSaved:",OUT)
