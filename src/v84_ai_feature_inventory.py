import pandas as pd
from pathlib import Path

print("=== V84 AI FEATURE / CISD INVENTORY ===")
files=[
"data/v3_reversal_features.parquet",
"data/v4_causal_reversal_features.parquet",
"data/v5_structural_location_features.parquet",
"data/v5_winner_mining_features.parquet",
"data/v68_full_causal_feature_table.parquet",
"data/v76_preentry_feature_atlas.parquet",
]
keywords=("cisd","disp","sweep","reclaim","wick","approach","compress","structure","swing","touch","liq","equilibrium","stretch","range","body","direction","session","volume","vol","atr","close_pos")
for f in files:
    p=Path(f)
    if not p.exists():
        print("\nMISSING",f); continue
    d=pd.read_parquet(p)
    hits=[c for c in d.columns if any(k in c.lower() for k in keywords)]
    print(f"\n{f} | rows={len(d)} | cols={len(d.columns)}")
    print("Relevant:",", ".join(hits))

print("\nV83 tells us the current 11-feature model is calibrated but incomplete.")
print("NEXT: use this inventory to build the expanded causal AI feature table, auditing timestamps before any feature is admitted.")
