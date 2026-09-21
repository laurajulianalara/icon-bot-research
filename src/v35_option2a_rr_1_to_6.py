import pandas as pd
tr=pd.read_csv("data/v27_option2a_trades.csv")
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True)

# IMPORTANT: The locked Option 2A file already contains the canonical 4R outcome.
# For lower targets, every canonical 4R winner necessarily reached 1R/2R/3R first.
# For canonical 4R losses, we may only count a lower-R win if its MFE BEFORE the
# canonical loss/exit is known. The current CSV does not store that path.
#
# For 5R/6R, likewise, a 4R winner must be replayed from its canonical exit state;
# restarting every trade at candidate_time is invalid and caused the 69 false wins.
#
# This script therefore audits what can be stated exactly from the locked dataset
# and refuses to print fake "accurate" 1R-6R figures.
print("=== OPTION 2A RR ACCURACY AUDIT ===")
print("Trades:",len(tr))
print("Locked 4R wins:",int((tr.outcome=="WIN").sum()))
print("Locked 4R losses:",int((tr.outcome=="LOSS").sum()))
print(f"Locked 4R WR: {100*(tr.outcome=='WIN').mean():.2f}%")
print("\nSTATUS")
print("4R: EXACT from locked Option 2A")
print("1R-3R: require original per-trade pre-exit path/outcome replay")
print("5R-6R: require continuation replay from the canonical 4R trade path")
print("\nDo NOT use V35 numbers; its replay restarts trades from candidate_time and does not reproduce the canonical engine.")
