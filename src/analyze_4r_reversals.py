import pandas as pd
import numpy as np

INFILE = "data/v3_reversal_features.parquet"
OUT_SUMMARY = "data/v3_4r_reversal_diagnostic.csv"
OUT_MFE = "data/v3_4r_loser_mfe.csv"

print("\nLoading V3 reversal trade cache...")
df = pd.read_parquet(INFILE)
df["fill_time"] = pd.to_datetime(df["fill_time"])

# 4R only. Use max_cisd_bars=5 as the primary diagnostic family to avoid
# counting the same underlying setup repeatedly across 3/5/8 confirmation windows.
x = df[(df["rr"] == 4.0) & (df["max_cisd_bars"] == 5)].copy()
x = x[x["outcome"].isin(["WIN", "LOSS"])].copy()

print("Resolved 4R trades:", f"{len(x):,}")
print("Entries:", ", ".join(sorted(x["entry"].unique())))

def stats(g):
    if len(g) == 0:
        return None
    wins = (g["outcome"] == "WIN").sum()
    losses = (g["outcome"] == "LOSS").sum()
    return {
        "trades": len(g),
        "wins": int(wins),
        "losses": int(losses),
        "wr": wins / len(g) * 100,
        "avg_mfe_r": g["mfe_r"].mean(),
        "median_mfe_r": g["mfe_r"].median(),
        "avg_mae_r": g["mae_r"].mean(),
    }

rows = []

def add(group_name, group_value, g):
    s = stats(g)
    if s:
        rows.append({"group": group_name, "value": str(group_value), **s})

# Baseline by execution method
for k, g in x.groupby("entry"):
    add("ENTRY", k, g)

# Session and direction
for k, g in x.groupby("session"):
    add("SESSION", k, g)
for k, g in x.groupby("direction"):
    add("DIRECTION", k, g)

# Existing causal feature ranges. These are diagnostics, not strategy rules.
bins = {
    "sr_dist_atr": [-np.inf, .15, .30, .50, 1.0, np.inf],
    "sweep_atr": [-np.inf, 0, .05, .15, .30, np.inf],
    "rejection": [-np.inf, .20, .30, .40, .50, np.inf],
    "relative_volume": [-np.inf, .8, 1.0, 1.2, 1.5, 2.0, np.inf],
    "disp_atr": [-np.inf, .30, .50, .75, 1.0, 1.5, np.inf],
    "confirm_close_pos": [-np.inf, .40, .55, .70, .85, np.inf],
}
for col, edges in bins.items():
    b = pd.cut(x[col], edges, include_lowest=True, duplicates="drop")
    for k, g in x.groupby(b, observed=True):
        add(col.upper(), k, g)

for col in ["fvg", "absorption", "strong_abs"]:
    for k, g in x.groupby(col):
        add(col.upper(), k, g)

summary = pd.DataFrame(rows).sort_values(["group", "wr", "trades"], ascending=[True, False, False])
summary.to_csv(OUT_SUMMARY, index=False)

# Losing-trade MFE: how far eventual losers got before stop.
los = x[x["outcome"] == "LOSS"].copy()
mfe_levels = [0.25, .50, .75, 1.0, 1.5, 2.0, 2.5, 3.0]
mfe_rows = []
for entry, g in los.groupby("entry"):
    for level in mfe_levels:
        n = int((g["mfe_r"] >= level).sum())
        mfe_rows.append({
            "entry": entry,
            "mfe_level_r": level,
            "losers_reaching_level": n,
            "total_losers": len(g),
            "pct_of_losers": n / len(g) * 100 if len(g) else 0,
        })
mfe = pd.DataFrame(mfe_rows)
mfe.to_csv(OUT_MFE, index=False)

print("\n=== 4R BASELINE BY ENTRY ===")
print(summary[summary["group"] == "ENTRY"].round(2).to_string(index=False))

print("\n=== EVENTUAL LOSERS: HOW FAR THEY FIRST GOT INTO PROFIT ===")
print(mfe.round(2).to_string(index=False))

print("\nSaved:")
print(OUT_SUMMARY)
print(OUT_MFE)
print("\nNEXT: push these two small CSVs for winner-vs-loser analysis.")
