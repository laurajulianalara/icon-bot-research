import pandas as pd
from pathlib import Path

TARGETS={953,958,1911}
print("=== V74 LOCATE EXACT BENCHMARK TRADE SETS ===")

hits=[]
for p in sorted(Path(".").rglob("*")):
    if not p.is_file() or any(x in str(p) for x in [".git/","__pycache__"]): continue
    if p.suffix.lower() not in [".parquet",".csv"]: continue
    try:
        d=pd.read_parquet(p) if p.suffix.lower()==".parquet" else pd.read_csv(p)
    except Exception:
        continue
    n=len(d)
    if n in TARGETS:
        hits.append((str(p),n,list(d.columns)))
        print(f"EXACT HIT: {p} | rows={n}")
        print("columns:",", ".join(map(str,d.columns)))
    # Also identify files containing likely year-separated benchmark subsets.
    tcol=next((c for c in ["candidate_time","fill_time","time_ny","entry_time"] if c in d.columns),None)
    if tcol and 500<=n<=10000:
        try:
            t=pd.to_datetime(d[tcol],errors="coerce")
            yr=t.dt.year.value_counts().sort_index()
            # print only plausible trade/result datasets
            if any(c in d.columns for c in ["outcome","result_r","entry","risk"]):
                print(f"CANDIDATE: {p} | rows={n} | years={yr.to_dict()}")
        except Exception: pass

if not hits:
    print("\nNo standalone 953/958-row files found.")
    print("That means the benchmark populations must be reconstructed from the saved research pipeline.")
else:
    print(f"\nExact-hit files found: {len(hits)}")

print("\nNEXT: reconstruct/verify the exact 953 and 958 timestamps before attaching any new features. We will not approximate the reference population.")
