import pandas as pd, numpy as np

print("=== +2 LIVE DECISION FEASIBILITY — FULL 1,911 ===")

rem=pd.read_csv("data/remaining_1145_native_1m_recoverability.csv")
rem["original_time"]=pd.to_datetime(rem["original_time"],utc=True,errors="coerce")
rem["arrived_extreme_time"]=pd.to_datetime(rem["arrived_extreme_time"],utc=True,errors="coerce")
one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

# Key question after the prior audit:
# By T+2, 1128/1145 hindsight-dependent rows already have the final T..T+3 extreme.
# Quantify the 17 exceptions and whether a simple causal rule can detect/avoid them.
rows=[]
for _,x in rem.iterrows():
    i=idx.get(x.original_time)
    if i is None or i+3>=len(one): continue
    direction=str(x.direction).upper()
    b0,b1,b2,b3=[one.iloc[i+k] for k in range(4)]
    vals=[b0.high,b1.high,b2.high,b3.high] if direction=="SHORT" else [b0.low,b1.low,b2.low,b3.low]
    best2=max(vals[:3]) if direction=="SHORT" else min(vals[:3])
    final=max(vals) if direction=="SHORT" else min(vals)
    late=(final!=best2)
    # completed T+2 information only
    rng=max(b2.high-b2.low,0.25)
    if direction=="SHORT":
        close_reversal=(b2.high-b2.close)/rng
        continuation=(b2.high-best2)/rng
    else:
        close_reversal=(b2.close-b2.low)/rng
        continuation=(best2-b2.low)/rng
    rows.append({"late_t3":late,"close_reversal_t2":close_reversal,
                 "body_pct_t2":abs(b2.close-b2.open)/rng,
                 "range_t2":rng,
                 "t2_dir":np.sign(b2.close-b2.open)})

d=pd.DataFrame(rows)
print("Rows:",len(d))
print("Final extreme already present by T+2:",int((~d.late_t3).sum()),f"({100*(~d.late_t3).mean():.2f}%)")
print("New final extreme appears at T+3:",int(d.late_t3.sum()),f"({100*d.late_t3.mean():.2f}%)")
print("\nT+2 observable comparison:")
for c in ["close_reversal_t2","body_pct_t2","range_t2"]:
    a=d.loc[~d.late_t3,c]; b=d.loc[d.late_t3,c]
    print(f"{c}: stable median={a.median():.4f} | late-T3 median={b.median():.4f}")

print("\nINTERPRETATION")
print("If the 17 late-T3 rows are not causally distinguishable at T+2, then a fixed wait-through-T+2 rule is already the practical ceiling: it gets 1128/1145 (98.52%) of this cohort's correct extreme without waiting an extra minute.")
print("Next step after this audit is a full-stream state-machine backtest, because reference-only rows cannot prove live deployability.")
