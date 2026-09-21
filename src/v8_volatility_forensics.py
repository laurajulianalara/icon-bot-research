import pandas as pd
import numpy as np

ONE="data/mnq_continuous_1m.parquet"; BASE="data/v7_base_trade_quality.parquet"; OUT="data/v8_volatility_forensics.csv"
one=pd.read_parquet(ONE).sort_values("time_ny").reset_index(drop=True);one["time_ny"]=pd.to_datetime(one.time_ny)
d=pd.read_parquet(BASE).sort_values("candidate_time").reset_index(drop=True);d["candidate_time"]=pd.to_datetime(d.candidate_time)
q=d[(d.early_reclaim_atr<=.90)&(d.m2_close_pos<=.80)&(d.wick_percent<=.60)&(d.m2_move_atr<=.15)&(d.m2_dir_bars5<=4)].copy()
q["win"]=(q.outcome=="WIN").astype(int)
grp=q.win.cumsum(); sizes=q.assign(loss=1-q.win).groupby(grp).loss.transform("sum")
q["class"]=np.where(q.win.eq(1),"WIN",np.where(sizes.ge(3),"STREAK_LOSS","NORMAL_LOSS"))

# 1m realized TR/ATR known before candidate; compare absolute and relative-to-recent regime.
one["tr"]=pd.concat([one.high-one.low,(one.high-one.close.shift()).abs(),(one.low-one.close.shift()).abs()],axis=1).max(axis=1)
one["atr20"]=one.tr.rolling(20).mean()
one["atr60"]=one.tr.rolling(60).mean()
one["atr240"]=one.tr.rolling(240).mean()
one["vol_ratio_20_60"]=one.atr20/one.atr60
one["vol_ratio_20_240"]=one.atr20/one.atr240
one["range20"]=one.high.rolling(20).max()-one.low.rolling(20).min()
one["range60"]=one.high.rolling(60).max()-one.low.rolling(60).min()
one["range_ratio"]=one.range20/(one.range60/3)
feat=one[["time_ny","atr20","atr60","atr240","vol_ratio_20_60","vol_ratio_20_240","range_ratio"]].rename(columns={"time_ny":"candidate_time"})
q=pd.merge_asof(q.sort_values("candidate_time"),feat.sort_values("candidate_time"),on="candidate_time",direction="backward")

print("=== VOLATILITY FORENSICS: WIN vs NORMAL LOSS vs STREAK LOSS ===")
features=["atr20","vol_ratio_20_60","vol_ratio_20_240","range_ratio"]
for f in features:
 print("\n",f)
 print(q.groupby("class")[f].agg(["count","mean","median"]).round(3).to_string())

# Within each session, use percentile bins so Asia/London/NY volatility scales are comparable.
q["session_vol_pct"]=q.groupby("session").atr20.rank(pct=True)
q["vol_bin"]=pd.cut(q.session_vol_pct,[0,.2,.4,.6,.8,1],labels=["LOWEST20","LOW20-40","MID40-60","HIGH60-80","HIGHEST20"],include_lowest=True)
tab=q.groupby("vol_bin",observed=True).agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()),streak_losses=("class",lambda x:(x=="STREAK_LOSS").sum()))
tab["streak_loss_pct"]=100*tab.streak_losses/tab.trades
print("\n=== SESSION-NORMALIZED VOLATILITY BINS ===")
print(tab.round(2).to_string())
print("\n=== BY SESSION + VOLATILITY BIN ===")
z=q.groupby(["session","vol_bin"],observed=True).agg(trades=("win","size"),wr=("win",lambda x:100*x.mean()),streak_loss_pct=("class",lambda x:100*(x=="STREAK_LOSS").mean()))
print(z.round(2).to_string())
q.to_csv(OUT,index=False)
print("\nSaved:",OUT)
