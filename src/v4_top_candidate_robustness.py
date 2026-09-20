import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_top_candidate_robustness.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&df.outcome.isin(["WIN","LOSS"])].copy()

# Top current candidate: CISD >= .95, displacement >= 1.30 ATR, sweep >= .30 ATR.
z=df[(df.confirm_close_pos>=.95)&(df.disp_atr>=1.30)&(df.sweep_atr>=.30)].sort_values("fill_time").copy()

def stats(x,label):
    n=len(x); w=(x.outcome=="WIN").sum()
    eq=x.result_r.cumsum()
    dd=abs((eq-eq.cummax()).min()) if n else np.nan
    return dict(period=label,trades=n,wins=w,losses=n-w,wr=(w/n*100 if n else np.nan),
                expectancy_r=(x.result_r.mean() if n else np.nan),max_dd_r=dd)

rows=[]
# 5 chronological blocks to expose instability hidden by one 70/30 split.
edges=np.linspace(0, len(z), 6, dtype=int)
blocks=[z.iloc[edges[i]:edges[i+1]].copy() for i in range(5)]
for i,b in enumerate(blocks,1):
    rows.append(stats(b,f"chronological_20pct_{i}"))

# Session and direction checks.
for s,g in z.groupby("session"):
    rows.append(stats(g,f"session_{s}"))
for d,g in z.groupby("direction"):
    rows.append(stats(g,f"direction_{d}"))

rows.append(stats(z,"ALL"))
r=pd.DataFrame(rows)
r.to_csv(OUTFILE,index=False)

print("\n=== TOP 4R CANDIDATE ROBUSTNESS ===")
print("NO_FIB | CISD >= .95 | displacement >= 1.30 ATR | sweep >= .30 ATR")
print("\nChronological blocks:")
print(r[r.period.str.startswith("chronological")].round(2).to_string(index=False))
print("\nSession / direction:")
print(r[~r.period.str.startswith("chronological")].round(2).to_string(index=False))
print("\nSaved:",OUTFILE)
