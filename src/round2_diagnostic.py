import pandas as pd
import numpy as np

RESULTS = "data/strategy_results_v2.csv"
CACHE = "data/v2_trade_cache.parquet"
OUTPUT = "data/round2_diagnostic.csv"

print("\nLoading V2 results + trade cache...")
r = pd.read_csv(RESULTS)
t = pd.read_parquet(CACHE)

# Round 2 target: only 3R/4R, meaningful sample, and usable frequency.
r = r[
    r["rr"].isin([3.0, 4.0]) &
    r["entry"].isin(["FIB_705", "FIB_786"]) &
    (r["trades"] >= 300)
].copy()

print("3R/4R .705/.786 variations:", f"{len(r):,}")
print("Best 3R win rate:", round(r.loc[r["rr"] == 3.0, "win_rate"].max(), 2), "%")
print("Best 4R win rate:", round(r.loc[r["rr"] == 4.0, "win_rate"].max(), 2), "%")
print("Variations already >=50% WR:", int((r["win_rate"] >= 50).sum()))

# Instead of another random sweep, inspect the strongest existing 3R/4R
# families by entry, session, direction and month. This tells us what to
# build into the targeted reversal-quality engine next.
families = []
for rr in [3.0, 4.0]:
    subset = r[r["rr"] == rr].sort_values(
        ["win_rate", "expectancy_r", "profit_factor"], ascending=False
    ).head(12)

    for _, s in subset.iterrows():
        q = t[
            (t["rr"] == s["rr"]) &
            (t["cisd_type"] == s["cisd_type"]) &
            (t["max_cisd_bars"] == s["max_cisd_bars"]) &
            (t["entry"] == s["entry"]) &
            (t["stop_buffer"] == s["stop_buffer"]) &
            (t["relative_volume"] >= s["volume_filter"]) &
            (t["wick_percent"] >= s["wick_filter"]) &
            (t["sweep_atr"] >= s["sweep_atr_filter"])
        ].copy()

        # Reapply one-live-trade rule.
        q = q.sort_values("fill_time")
        accepted, current_exit = [], None
        for _, tr in q.iterrows():
            if current_exit is not None and tr["fill_time"] <= current_exit:
                continue
            accepted.append(tr)
            current_exit = tr["exit_time"]
        if not accepted:
            continue
        q = pd.DataFrame(accepted)
        q["month"] = pd.to_datetime(q["fill_time"]).dt.to_period("M").astype(str)

        for group_type, col in [("SESSION", "session"), ("DIRECTION", "direction"), ("MONTH", "month")]:
            for name, g in q.groupby(col):
                resolved = g[g["outcome"].isin(["WIN", "LOSS"])]
                if len(resolved) == 0:
                    continue
                families.append({
                    "rr": rr,
                    "entry": s["entry"],
                    "cisd_type": s["cisd_type"],
                    "max_cisd_bars": s["max_cisd_bars"],
                    "volume_filter": s["volume_filter"],
                    "wick_filter": s["wick_filter"],
                    "sweep_atr_filter": s["sweep_atr_filter"],
                    "stop_buffer": s["stop_buffer"],
                    "overall_trades": int(s["trades"]),
                    "overall_win_rate": s["win_rate"],
                    "group_type": group_type,
                    "group": name,
                    "group_trades": len(resolved),
                    "group_win_rate": (resolved["outcome"] == "WIN").mean() * 100,
                    "group_expectancy_r": resolved["result_r"].mean(),
                    "group_avg_mfe_r": resolved["mfe_r"].mean(),
                    "group_avg_mae_r": resolved["mae_r"].mean(),
                })

out = pd.DataFrame(families)
out.to_csv(OUTPUT, index=False)

print("\n===================================")
print(" ROUND 2 DIAGNOSTIC COMPLETE")
print("===================================")
print("Saved:", OUTPUT)

for rr in [3.0, 4.0]:
    x = r[r["rr"] == rr].sort_values(["win_rate", "expectancy_r"], ascending=False).head(10)
    print(f"\nTOP {rr:.0f}R EXISTING FAMILIES:")
    print(x[[
        "cisd_type","max_cisd_bars","entry","volume_filter","wick_filter",
        "sweep_atr_filter","stop_buffer","trades","trades_per_day","win_rate",
        "expectancy_r","profit_factor","max_drawdown_r"
    ]].round(2).to_string(index=False))

print("\nThis is a diagnostic, not the new optimizer.")
print("NEXT: use these results to build targeted key-level + reversal-quality features.")
