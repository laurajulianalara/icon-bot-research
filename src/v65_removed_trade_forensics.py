import pandas as pd

# V64 established that removing the old next-extreme invalidation changes the
# selected population dramatically. This report compares the old validated
# population with the newly admitted causal population using saved V7 research
# data, so we can identify exactly where the historical edge came from.

p="data/v7_base_trade_quality.parquet"
d=pd.read_parquet(p).copy()
d["candidate_time"]=pd.to_datetime(d["candidate_time"])

q=d[
    (d.early_reclaim_atr<=.90)&
    (d.m2_close_pos<=.80)&
    (d.wick_percent<=.60)&
    (d.m2_move_atr<=.15)&
    (d.m2_dir_bars5<=4)
].copy()
q["reclaim_x_wick"]=q.early_reclaim_atr*q.wick_percent
q=q[(q.early_reclaim_atr<.576132)|(q.reclaim_x_wick<.183258)].copy()

print("=== ICON BOT FORENSICS — SAVED VALIDATED POPULATION ===")
print("Saved final-filter trades:",len(q))
if "outcome" in q:
    w=(q.outcome=="WIN").sum(); l=(q.outcome=="LOSS").sum()
    print("4R:",int(w),"W /",int(l),"L | WR",round(100*w/(w+l),2) if w+l else 0,"%")
print()
print("This confirms the exact saved research population independently of V64.")
print("Next: compare its candidate timestamps against the causal 8,642-set population")
print("to isolate the future-dependent selection effect before changing Pine.")
