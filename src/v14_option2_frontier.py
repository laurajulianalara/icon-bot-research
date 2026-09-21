import pandas as pd
import numpy as np

q = pd.read_csv("data/v11_reversal_state_forensics.csv")
q["candidate_time"] = pd.to_datetime(q["candidate_time"], utc=True)
q = q.sort_values("candidate_time").reset_index(drop=True)
q["win"] = (q["outcome"] == "WIN").astype(int)
q["r"] = np.where(q["win"] == 1, 4.0, -1.0)

# Rebuild V12 causal interaction features.
q["reclaim_x_wick"] = q["early_reclaim_atr"] * q["wick_percent"]
q["close_x_reclaim"] = q["m2_close_pos"] * q["early_reclaim_atr"]
q["sweep_minus_reclaim"] = q["sweep_atr"] - q["early_reclaim_atr"]
q["impulse_minus_reclaim"] = q["reversal_impulse"] - q["early_reclaim_atr"]
q["quality_balance"] = (
    q["rejection_quality"] * q["impulse_to_reclaim"] / (1 + q["reclaim_to_sweep"])
)

cut = q["candidate_time"].min() + (
    q["candidate_time"].max() - q["candidate_time"].min()
) * 0.70

def stats(z):
    z = z.sort_values("candidate_time").copy()
    z["d"] = z["candidate_time"].dt.tz_convert("America/New_York").dt.date
    z["n"] = z.groupby("d").cumcount() + 1
    z = z[z["n"] <= 6].copy()

    eq = z["r"].cumsum()
    dd = float((eq.cummax() - eq).max())
    cur = 0
    mx = 0
    for w in z["win"]:
        cur = 0 if w else cur + 1
        mx = max(mx, cur)

    active = z["d"].nunique()
    daily = z.groupby("d").size()
    a = z[z["candidate_time"] < cut]
    b = z[z["candidate_time"] >= cut]

    return [
        len(z),
        len(z) / 365,
        len(z) / active if active else 0,
        100 * z["win"].mean(),
        z["r"].sum(),
        z["r"].mean(),
        dd,
        mx,
        int(daily.max()) if len(daily) else 0,
        100 * a["win"].mean() if len(a) else np.nan,
        100 * b["win"].mean() if len(b) else np.nan,
        min(
            100 * a["win"].mean() if len(a) else np.nan,
            100 * b["win"].mean() if len(b) else np.nan,
        ),
    ]

parts = []
specs = [
    ("rejection_quality", True, 2),
    ("impulse_to_reclaim", True, 2),
    ("reclaim_to_sweep", False, 1),
    ("reversal_impulse", True, 1),
    ("reclaim_x_wick", False, 2),
    ("close_x_reclaim", False, 2),
    ("sweep_minus_reclaim", True, 1),
    ("impulse_minus_reclaim", True, 2),
    ("quality_balance", True, 2),
]

for col, good_high, weight in specs:
    rank = q[col].rank(pct=True)
    component = rank if good_high else 1 - rank
    for _ in range(weight):
        parts.append(component)

q["score"] = pd.concat(parts, axis=1).mean(axis=1)

rows = []
for pct in np.arange(0, 0.46, 0.01):
    threshold = q["score"].quantile(pct)
    z = q[q["score"] >= threshold].copy()
    rows.append([pct, threshold, *stats(z)])

cols = [
    "drop_pct", "score_min", "trades", "calendar_tpd", "active_tpd", "wr",
    "net_r", "expectancy_r", "max_dd_r", "max_loss_streak",
    "max_trades_day", "train_wr", "test_wr", "robust_wr",
]
r = pd.DataFrame(rows, columns=cols)
r.to_csv("data/v14_option2_frontier.csv", index=False)

print("=== OPTION 2 FRONTIER — QUALITY + HARD 6/DAY SAFETY CAP ===")
print("\nTarget active-day frequency 4.0-5.5:")
x = r[(r["active_tpd"] >= 4) & (r["active_tpd"] <= 5.5)].sort_values(
    ["max_dd_r", "robust_wr", "active_tpd"],
    ascending=[True, False, False],
)
print(x.head(40).round(2).to_string(index=False))

print("\nTarget >=55% both train/test, active >=4/day:")
y = r[(r["robust_wr"] >= 55) & (r["active_tpd"] >= 4)].sort_values(
    ["max_dd_r", "robust_wr"],
    ascending=[True, False],
)
print(y.head(30).round(2).to_string(index=False))
print("\nSaved: data/v14_option2_frontier.csv")
