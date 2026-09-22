import pandas as pd, numpy as np
from pathlib import Path

print("=== V86 SELECTED EXTREME AI FEATURE EXPANSION ===")
base=pd.read_parquet("data/v85_selected_vs_preceding_extremes.parquet")
print("V85 comparison rows:",len(base))

# Inventory richer historical feature tables. We only admit columns that are
# present before/at confirmation; outcome/future/exit/target fields are banned.
paths=[
"data/v5_structural_location_features.parquet",
"data/v5_winner_mining_features.parquet",
"data/v76_preentry_feature_atlas.parquet",
"data/v68_full_causal_feature_table.parquet",
]
ban=("outcome","win_","target","exit","result","future","next_","hindsight","invalid","label","pnl","mae","mfe")
wanted=("cisd","disp","sweep","approach","compress","structure","swing","touch","liq","equilibrium","stretch","range","body","reclaim","wick","atr","directional","close_pos","progress")

for p in paths:
    q=Path(p)
    if not q.exists():
        print("MISSING:",p); continue
    d=pd.read_parquet(q)
    candidates=[c for c in d.columns if any(k in c.lower() for k in wanted) and not any(b in c.lower() for b in ban)]
    print("\n",p,"rows",len(d))
    print("Candidate pre-entry fields:")
    print(", ".join(candidates))

print("\nV85 FACT PATTERN TO BUILD AROUND:")
print("Selected extremes showed materially LOWER early reclaim, m2 close position, wick %,")
print("m2 move ATR, and reclaim×wick than the preceding rejected extremes.")
print("\nNEXT BUILD TARGET:")
print("Create strict timestamp-audited CISD + displacement + sweep + approach/structure features")
print("for BOTH selected and rejected extremes, then retrain WAIT/ENTER on those differences.")
