import pandas as pd
from pathlib import Path

CAND=Path("data/reversal_candidates.parquet")
ONE=Path("data/mnq_continuous_1m.parquet")

c=pd.read_parquet(CAND).sort_values("time_ny").reset_index(drop=True)
o=pd.read_parquet(ONE).sort_values("time_ny").reset_index(drop=True)
for d in (c,o): d["time_ny"]=pd.to_datetime(d["time_ny"])
c["next_same_extreme_time"]=c.groupby(["session_id","direction"],sort=False).time_ny.shift(-1)
c["signal_time"]=c.time_ny+pd.Timedelta(minutes=3)
c["invalidated_by_rule"]=c.next_same_extreme_time.notna() & (c.signal_time>=c.next_same_extreme_time)
c["same_bar_future_dependency"]=c.next_same_extreme_time.eq(c.signal_time)

print("=== CAUSAL TIMING AUDIT — FULL HISTORY ===")
print("Candidates:",len(c))
print("Invalidated by next-same-extreme rule:",int(c.invalidated_by_rule.sum()))
print("Exactly at signal time (future dependency):",int(c.same_bar_future_dependency.sum()))
print("Percent of all candidates:",round(100*c.same_bar_future_dependency.mean(),2),"%")
print()
print("IMPORTANT:")
print("A Pine order at signal_time OPEN cannot know whether the 3-minute bar")
print("starting at signal_time will later create another same-direction extreme.")
print("If this count is non-zero, that invalidation rule must be handled causally")
print("before we demand exact live Pine parity.")
