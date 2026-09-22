import pandas as pd
from pathlib import Path

REF=Path("data/icon_bot_funded_parity_reference.csv")
OUT=Path("data/icon_bot_funded_parity_sep2025.csv")
d=pd.read_csv(REF)
t=pd.to_datetime(d["candidate_time_et"], utc=True).dt.tz_convert("America/New_York")
z=d[(t>=pd.Timestamp("2025-09-01",tz="America/New_York"))&(t<pd.Timestamp("2025-10-01",tz="America/New_York"))].copy()
z.insert(0,"parity_id",range(1,len(z)+1))
z.to_csv(OUT,index=False)
print("SEPTEMBER 2025 PARITY SET")
print("Trades:",len(z))
print(z[["parity_id","candidate_time_et","session","direction"]].to_string(index=False))
print("Saved:",OUT)
