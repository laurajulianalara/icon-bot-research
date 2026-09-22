import pandas as pd

v7=pd.read_parquet("data/v7_base_trade_quality.parquet").copy()
cand=pd.read_parquet("data/reversal_candidates.parquet").copy()
v7["candidate_time"]=pd.to_datetime(v7["candidate_time"])
cand["time_ny"]=pd.to_datetime(cand["time_ny"])

q=v7[
    (v7.early_reclaim_atr<=.90)&
    (v7.m2_close_pos<=.80)&
    (v7.wick_percent<=.60)&
    (v7.m2_move_atr<=.15)&
    (v7.m2_dir_bars5<=4)
].copy()
q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
final=q[(q.early_reclaim_atr<.576132)|(q.reclaim_x_wick<.183258)].copy()

cand=cand.sort_values("time_ny")
cand["next_same_extreme_time"]=cand.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
cand["signal_time"]=cand.time_ny+pd.Timedelta(minutes=3)
cand["future_invalidated"]=cand.next_same_extreme_time.notna() & (cand.signal_time>=cand.next_same_extreme_time)

m=final.merge(
    cand[["time_ny","session","direction","future_invalidated"]],
    left_on=["candidate_time","session","direction"],
    right_on=["time_ny","session","direction"],how="left"
)

print("=== ICON BOT POPULATION RECONCILIATION ===")
print("Raw candidates:",len(cand))
print("Saved V7 base trades:",len(v7))
print("Pre-Option2 population:",len(q))
print("Final saved population:",len(final))
print("Final matched to raw candidates:",int(m.future_invalidated.notna().sum()))
print("Final marked future-invalidated:",int(m.future_invalidated.fillna(False).sum()))
print()
print("V63/V64 produced 8,642+ setups because they rebuilt filters directly from ALL raw candidates.")
print("V7 contains only candidates that already survived its execution/invalidation pipeline.")
print("Therefore V66 could not contain a rejected comparison group; those rows had already been removed before V7 was saved.")
print()
print("NEXT: rebuild the full pre-entry feature table from raw candidates BEFORE any future-dependent invalidation, then label kept/rejected.")
