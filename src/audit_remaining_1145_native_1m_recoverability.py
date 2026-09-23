import pandas as pd, numpy as np

print("=== REMAINING 1,145 — NATIVE 1M RECOVERABILITY AUDIT (FIXED) ===")
a=pd.read_csv("data/original_1911_exact_live_future_rr_audit.csv")
if "future_dependent" not in a.columns:
    raise RuntimeError("Expected future_dependent column not found. Columns: "+", ".join(a.columns))
fd=a["future_dependent"]
if fd.dtype==object:
    flag=fd.astype(str).str.lower().isin(["true","1","yes"])
else:
    flag=fd.astype(bool)
bad=a[flag].copy()
print("Future-dependent reference rows:",len(bad))
if len(bad)!=1145:
    print("WARNING: expected 1,145 from exact audit; found",len(bad))

ot="candidate_time"
mt="mapped_1m_candidate_time"
dc="direction"
bad[ot]=pd.to_datetime(bad[ot],utc=True,errors="coerce")
bad[mt]=pd.to_datetime(bad[mt],utc=True,errors="coerce")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

rows=[]
for _,r in bad.iterrows():
    T=r[ot]; mapped=r[mt]; i=idx.get(T)
    if i is None: continue
    direction=str(r[dc]).upper()
    entry_i=i+3
    if entry_i>=len(one): continue
    # Was the mapped native 1m extreme itself already printed by the old T+3 entry boundary?
    mi=idx.get(mapped)
    mapped_known=(mi is not None and mi<=entry_i)
    mapped_offset=(mi-i) if mi is not None else np.nan

    # Find the most extreme price that actually ARRIVED from original T through T+3.
    window=one.iloc[i:entry_i+1]
    if direction=="SHORT":
        rel=int(np.argmax(window.high.to_numpy()))
        latest_extreme_i=i+rel
        arrived_extreme=float(window.high.iloc[rel])
    else:
        rel=int(np.argmin(window.low.to_numpy()))
        latest_extreme_i=i+rel
        arrived_extreme=float(window.low.iloc[rel])

    next_i=latest_extreme_i+1
    rows.append({
        "original_time":T,"mapped_1m_candidate_time":mapped,"direction":direction,
        "mapped_offset_min":mapped_offset,"mapped_known_by_Tplus3":mapped_known,
        "arrived_extreme_time":one.iloc[latest_extreme_i].t,
        "arrived_extreme_offset_min":latest_extreme_i-i,
        "arrived_extreme":arrived_extreme,
        "next_open_offset_min":next_i-i,
        "next_open_exists":next_i<len(one)
    })

out=pd.DataFrame(rows)
print("Mapped original timestamps to native 1m:",len(out),"/",len(bad))
if len(out):
    print("\nMAPPED REFERENCE EXTREME OFFSET")
    print(out.mapped_offset_min.value_counts(dropna=False).sort_index().to_string())
    print("\nMapped reference extreme known by original T+3 boundary:",
          int(out.mapped_known_by_Tplus3.sum()),"/",len(out))
    print("\nACTUAL MOST-EXTREME BAR ARRIVED BY T+3 — OFFSET")
    print(out.arrived_extreme_offset_min.value_counts().sort_index().to_string())
    print("\nNext-open exists after arrived extreme:",int(out.next_open_exists.sum()),"/",len(out))
out.to_csv("data/remaining_1145_native_1m_recoverability.csv",index=False)
print("\nSaved data/remaining_1145_native_1m_recoverability.csv")
print("This audit tests timing recoverability only; it does not yet certify selection or RR.")
