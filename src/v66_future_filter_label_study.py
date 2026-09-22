import pandas as pd
import numpy as np

d=pd.read_parquet("data/v7_base_trade_quality.parquet").copy()
d["candidate_time"]=pd.to_datetime(d["candidate_time"])

# Same pre-entry quality population used in the Icon research.
q=d[
    (d.early_reclaim_atr<=.90)&
    (d.m2_close_pos<=.80)&
    (d.wick_percent<=.60)&
    (d.m2_move_atr<=.15)&
    (d.m2_dir_bars5<=4)
].copy()
q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
q=q[(q.early_reclaim_atr<.576132)|(q.reclaim_x_wick<.183258)].copy()

# Load raw candidates only to recover the hindsight invalidation label.
c=pd.read_parquet("data/reversal_candidates.parquet").copy()
c["time_ny"]=pd.to_datetime(c["time_ny"])
c=c.sort_values("time_ny")
c["next_same_extreme_time"]=c.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)

# V7 signal is candidate time + 3 minutes.
keys=["time_ny","session","direction","next_same_extreme_time"]
m=q.merge(c[keys],left_on=["candidate_time","session","direction"],
          right_on=["time_ny","session","direction"],how="left")
m["signal_time"]=m.candidate_time+pd.Timedelta(minutes=3)
m["hindsight_kept"]=m.next_same_extreme_time.isna() | (m.signal_time<m.next_same_extreme_time)

print("=== PRE-ENTRY SIGNATURE STUDY ===")
print("Final-filter population:",len(m))
print("Hindsight-kept:",int(m.hindsight_kept.sum()))
print("Hindsight-rejected:",int((~m.hindsight_kept).sum()))
print()

features=[x for x in [
    "early_reclaim_atr","wick_percent","reclaim_x_wick",
    "m1_move_atr","m1_close_pos","m2_move_atr","m2_close_pos",
    "m1_dir_bars5","m2_dir_bars5","early_adverse_atr"
] if x in m.columns]

for f in features:
    a=pd.to_numeric(m.loc[m.hindsight_kept,f],errors="coerce").dropna()
    b=pd.to_numeric(m.loc[~m.hindsight_kept,f],errors="coerce").dropna()
    if len(a) and len(b):
        print(f"{f:22s} kept med={a.median():8.4f} rejected med={b.median():8.4f} | kept mean={a.mean():8.4f} rejected mean={b.mean():8.4f}")

print()
print("BY SESSION")
print(pd.crosstab(m.session,m.hindsight_kept,normalize="index").rename(columns={False:"rejected_pct",True:"kept_pct"}).round(4)*100)
print()
print("Goal: identify observable pre-entry features that separate the setups the old hindsight rule kept from those it rejected.")
