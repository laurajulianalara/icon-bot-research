import pandas as pd, numpy as np

print("=== V107 ORIGINAL 1,911 LIVE-FEASIBILITY CHECK ===")
d=pd.read_parquet("data/v106_meaningful_reversal_sequence.parquet").copy()
d["candidate_time"]=pd.to_datetime(d["candidate_time"],utc=True)
d["decision_time"]=pd.to_datetime(d["decision_time"],utc=True)

ref=d[d["is_reference"].astype(int)==1].copy()
print("Reference extremes represented:",ref["candidate_time"].nunique(),"/ 1911")
print()
print("QUESTION: If we wait 0-8 completed 1m candles, how many original trades are still alive,")
print("and what RR outcomes are physically available from the next 1m open?")
print()

rows=[]
for delay in range(9):
    x=ref[ref["delay_min"]==delay].copy()
    n=x["candidate_time"].nunique()
    vals=[100*x[f"win_{r}R"].mean() if len(x) else np.nan for r in range(1,7)]
    rows.append([delay,n]+vals)
    print(f"minute {delay}: alive={n:4d} ({100*n/1911:5.1f}%) | "
          + " ".join(f"{r}R={vals[r-1]:5.1f}%" for r in range(1,7)))

print()
print("BEST LEGITIMATE ENTRY MINUTE PER ORIGINAL TRADE (research ceiling only)")
print("This is NOT a tradable rule: it uses hindsight only to measure what was physically available.")
for R in range(1,7):
    # A reference counts if ANY still-valid timestamp-locked snapshot from minute 0-8 could enter and hit R.
    g=ref.groupby("candidate_time")[f"win_{R}R"].max()
    wins=int(g.sum()); n=len(g)
    print(f"{R}R ceiling: {wins:4d}/{n:4d} = {100*wins/n:5.2f}%")

print()
print("EARLIEST LIVE-AVAILABLE WINNING ENTRY DELAY")
for R in [1,2,3,4,5,6]:
    w=ref[ref[f"win_{R}R"]==1].groupby("candidate_time")["delay_min"].min()
    if len(w):
        print(f"{R}R: winners={len(w):4d} median_delay={w.median():.1f}m p75={w.quantile(.75):.1f}m")

print()
print("IMPORTANT: Ceiling numbers only prove the move was available after a live-valid timestamp.")
print("They do NOT prove we can identify those trades live. If ceiling is weak, stop chasing old numbers.")
print("If ceiling is strong, next step is simple causal-rule feasibility before any AI/model.")
