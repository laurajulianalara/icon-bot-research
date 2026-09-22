import pandas as pd
from pathlib import Path

print("=== V87 RICH FEATURE CAUSALITY AUDIT ===")
paths=["data/v5_structural_location_features.parquet","data/v5_winner_mining_features.parquet"]
fields=["cisd","disp","sweep","approach3_atr","approach5_atr","approach10_atr","pre30_range_atr",
"pre10_avg_range_atr","pre10_avg_body_atr","pre5_directional_bars","prior_touch_count",
"distance_equilibrium_atr","extreme_progress_atr","sr_dist_atr2","sr_touch_cluster",
"equal_liq_cluster","swept_prior_swing","sweep_depth2_atr","reclaim_prior_swing_atr",
"failed_cont_progress_atr","progress_vs_travel","approach_compression","approach_directional5",
"structure_edge_pos","stretch20_atr"]
for p in paths:
 d=pd.read_parquet(p)
 print("\n",p,"rows",len(d))
 for f in fields:
  if f in d:
   x=d[f]
   print(f"{f:28s} nonnull={x.notna().mean()*100:6.2f}% unique={x.nunique(dropna=True):6d}")
print("\nIMPORTANT: presence is not proof of causality. V88 must reconstruct/verify each admitted feature at the exact decision cutoff from continuous candles.")
print("NEXT: rebuild the strongest CISD/structure fields directly from continuous 1m/3m data, then retrain WAIT/ENTER and compare against the 73.13% baseline.")
