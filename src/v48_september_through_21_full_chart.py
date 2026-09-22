import pandas as pd
import numpy as np

BASE = "data/v27_option2a_trades.csv"
NEW = "data/sep18_sep21_option2a_all_sessions.csv"
RISK_DOLLARS = 300

base = pd.read_csv(BASE)
new = pd.read_csv(NEW)

# Locked historical Option 2A through Sep 17
time_col = next(c for c in ["entry_time","signal_time","time_ny","candidate_time"] if c in base.columns)
base[time_col] = pd.to_datetime(base[time_col], utc=True).dt.tz_convert("America/New_York")
sep = base[(base[time_col].dt.year == 2026) & (base[time_col].dt.month == 9) &
           (base[time_col].dt.day <= 17)].copy()

# Use canonical max-R column already stored in locked trade file if present.
maxr_col = next((c for c in ["max_rr","mfe_r","max_r","mfe"] if c in sep.columns), None)
if maxr_col is None:
    raise ValueError("Locked V27 file has no max-R column; exact RR replay required.")

sep = sep.rename(columns={time_col:"entry_time", maxr_col:"max_rr"})
sep["date"] = sep["entry_time"].dt.date

new["entry_time"] = pd.to_datetime(new["entry_time"], utc=True).dt.tz_convert("America/New_York")
new["date"] = new["entry_time"].dt.date
keep = ["date","entry_time","max_rr"]
alltr = pd.concat([sep[keep], new[keep]], ignore_index=True).sort_values("entry_time")

print("\n=== SEPTEMBER 2026 OPTION 2A — THROUGH SEP 21 ===")
print("Risk: $300/trade")
print()
print(f"{'DATE':<12}{'TRADES':>7}  {'1:1 W/L WR P&L':<25}{'1:2 W/L WR P&L':<25}{'1:3 W/L WR P&L':<25}{'1:4 W/L WR P&L':<25}")
print("-"*120)

for d,g in alltr.groupby("date"):
    parts=[]
    for rr in range(1,5):
        w=int((g.max_rr>=rr).sum()); l=len(g)-w
        wr=100*w/len(g)
        pnl=w*(rr*RISK_DOLLARS)-l*RISK_DOLLARS
        parts.append(f"{w}W/{l}L {wr:5.1f}% {pnl:+$,.0f}")
    print(f"{pd.Timestamp(d).strftime('%b %d'):<12}{len(g):>7}  " + "".join(f"{p:<25}" for p in parts))

print("-"*120)
print(f"TOTAL TRADES: {len(alltr)}")
for rr in range(1,5):
    w=int((alltr.max_rr>=rr).sum()); l=len(alltr)-w
    wr=100*w/len(alltr)
    pnl=w*(rr*RISK_DOLLARS)-l*RISK_DOLLARS
    print(f"1:{rr} | {w}W/{l}L | WR {wr:.2f}% | P&L {pnl:+,.0f} USD")
