import pandas as pd
from pathlib import Path

REF=Path("data/icon_bot_funded_parity_sep2025.csv")
d=pd.read_csv(REF)
d["candidate_time_et"]=pd.to_datetime(d["candidate_time_et"],utc=True).dt.tz_convert("America/New_York")

print("=== ICON BOT FUNDED — PINE PARITY TARGET ===")
print("Period:",d.candidate_time_et.min(),"to",d.candidate_time_et.max())
print("Final qualifying trades:",len(d))
print("\nBY SESSION")
print(d.groupby("session").size().to_string())
print("\nBY DIRECTION")
print(d.groupby("direction").size().to_string())
print("\nBY DAY")
print(d.assign(day=d.candidate_time_et.dt.date).groupby("day").size().to_string())
print("\nUse these totals as the fixed Pine diagnostic target. Do not optimize thresholds.")
