import pandas as pd
from pathlib import Path

print("=== V73 FULL REFERENCE POPULATION AUDIT ===")

files=list(Path("data").glob("*.parquet"))
print("Parquet files:",len(files))

for p in sorted(files):
    try:
        d=pd.read_parquet(p)
    except Exception:
        continue
    cols=set(d.columns)
    # Surface likely historical trade/result files, not raw candles.
    score=sum(x in cols for x in ["direction","entry","entry_price","outcome","result","pnl_r","r_multiple","rr"])
    if score>=2 or ("direction" in cols and 500<=len(d)<=5000):
        print(f"\n{p} | rows={len(d)}")
        print("columns:",", ".join(map(str,d.columns.tolist())))

# Known research populations.
for name in ["data/v7_base_trade_quality.parquet","data/v8_pre_option2_population.parquet",
             "data/v9_option2a_final.parquet","data/v68_full_causal_feature_table.parquet"]:
    p=Path(name)
    if p.exists():
        d=pd.read_parquet(p)
        print(f"\nKNOWN {name}: {len(d)} rows")

print("\nNEXT: use the exact saved original + holdout trade files identified above to build one ~1,911-row table, then attach only pre-entry features and 1R-6R outcome labels.")
