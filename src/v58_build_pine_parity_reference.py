import pandas as pd
from pathlib import Path

TRADES = Path("data/v56_icon_bot_funded_prior_year_trades.csv")
OUT = Path("data/icon_bot_funded_parity_reference.csv")

d = pd.read_csv(TRADES)
d["candidate_time"] = pd.to_datetime(d["candidate_time"], utc=True)
d["candidate_time_et"] = d["candidate_time"].dt.tz_convert("America/New_York")
keep = [c for c in ["candidate_time_et","session","direction","entry","risk","early_reclaim_atr","wick_percent","reclaim_x_wick","m1_move_atr","m1_close_pos","m2_move_atr","m2_close_pos","m2_dir_bars5","outcome_4r"] if c in d.columns]
d[keep].sort_values("candidate_time_et").to_csv(OUT,index=False)
print("ICON BOT FUNDED PARITY REFERENCE")
print("Trades:",len(d))
print("First:",d.candidate_time_et.min())
print("Last:",d.candidate_time_et.max())
print("Saved:",OUT)
