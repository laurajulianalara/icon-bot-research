import pandas as pd
import numpy as np

DATA_1M="data/mnq_continuous_1m.parquet"
OLD="data/v3_reversal_features.parquet"

print("\n=== 3M CONFIRMATION TIMING AUDIT ===")
one=pd.read_parquet(DATA_1M)
old=pd.read_parquet(OLD)
one["time_ny"]=pd.to_datetime(one["time_ny"])
old["fill_time"]=pd.to_datetime(old["fill_time"])
old["candidate_time"]=pd.to_datetime(old["candidate_time"])

# The 3m dataset was built with pandas resample defaults (left-labeled bins).
# A bar stamped T contains the interval [T,T+3m), so its OHLC is only known at T+3m.
# Reconstruct confirmation timestamp from candidate + cisd_bars*3m.
old["confirm_label_time"]=old["candidate_time"]+pd.to_timedelta(old["max_cisd_bars"]*3,unit="m")
old["signal_available_time"]=old["confirm_label_time"]+pd.Timedelta(minutes=3)

z=old[(old.rr==4.0)&(old.max_cisd_bars==5)&(old.entry=="NO_FIB")&old.outcome.isin(["WIN","LOSS"])].copy()
bad=z[z.fill_time<z.signal_available_time]

print("4R / max_cisd=5 / NO_FIB resolved rows:",f"{len(z):,}")
print("Rows entering before confirmation bar closed:",f"{len(bad):,}")
print("Contamination rate:",f"{(len(bad)/len(z)*100 if len(z) else 0):.2f}%")

if len(bad):
    print("\nCONFIRMED: current V3 cache allows entries before the full 3m confirmation candle is available.")
    print("Next step: rebuild the trade cache with earliest entry >= confirmation timestamp + 3 minutes.")
else:
    print("\nNo early-entry contamination detected in this slice.")

print("\nThis audit does NOT modify any existing data or strategy files.")
