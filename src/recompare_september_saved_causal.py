import pandas as pd

HIST = "data/reports/2026-09_trades.csv"
CAUSAL = "data/reports/2026-09_true_bar_by_bar.csv"

def norm_time(s):
    return pd.to_datetime(s, utc=True)

hist = pd.read_csv(HIST)
causal = pd.read_csv(CAUSAL)

def pick_time(df, choices):
    for c in choices:
        if c in df.columns:
            return c
    raise KeyError(f"No time column found. Columns: {list(df.columns)}")

def pick_dir(df):
    for c in ["direction", "side"]:
        if c in df.columns:
            return c
    raise KeyError(f"No direction column found. Columns: {list(df.columns)}")

ht = pick_time(hist, ["entry_time", "entry_time_et", "signal_time", "signal_time_et"])
ct = pick_time(causal, ["entry_time", "entry_time_et", "signal_time", "signal_time_et"])
hd = pick_dir(hist)
cd = pick_dir(causal)

hist["_t"] = norm_time(hist[ht])
causal["_t"] = norm_time(causal[ct])
hist["_d"] = hist[hd].astype(str).str.upper()
causal["_d"] = causal[cd].astype(str).str.upper()

hkeys = set(zip(hist["_t"], hist["_d"]))
ckeys = set(zip(causal["_t"], causal["_d"]))

matched = hkeys & ckeys
hist_only = hkeys - ckeys
causal_only = ckeys - hkeys

print("=" * 60)
print("SEPTEMBER OPTION 2B — FAST RECOMPARE")
print("=" * 60)
print(f"Corrected historical trades: {len(hkeys)}")
print(f"Saved causal trades:        {len(ckeys)}")
print(f"Matched:                    {len(matched)}")
print(f"Historical-only:            {len(hist_only)}")
print(f"Causal-only extras:         {len(causal_only)}")

six = [
    ("2026-09-03 22:15:00", "SHORT"),
    ("2026-09-03 22:27:00", "SHORT"),
    ("2026-09-10 15:21:00", "LONG"),
    ("2026-09-14 16:00:00", "LONG"),
    ("2026-09-14 21:18:00", "SHORT"),
    ("2026-09-15 00:00:00", "LONG"),
]

print("\nSIX PREVIOUS REPORT OMISSIONS:")
for ts, direction in six:
    t = pd.Timestamp(ts, tz="America/New_York").tz_convert("UTC")
    key = (t, direction)
    print(f"{ts} ET | {direction:5s} | historical={'YES' if key in hkeys else 'NO '} | causal={'YES' if key in ckeys else 'NO '} | matched={'YES' if key in matched else 'NO'}")

if hist_only:
    print("\nHISTORICAL-ONLY:")
    for t, d in sorted(hist_only):
        print(t.tz_convert("America/New_York"), d)

print("\nDone — no bar-by-bar replay was performed.")
