import pandas as pd
import numpy as np

INFILE = "data/v3_reversal_features.parquet"
OUTFILE = "data/v4_confirmed_changes_scan.csv"

# Confirmed removals: volume, absorption, FVG/IFVG are NOT used.
CISD_CLOSE_MIN = [0.80, 0.85, 0.90]
DISP_MIN = [0.75, 1.00, 1.25, 1.50]
ENTRIES = ["NO_FIB","FIB_500","FIB_618","FIB_705","FIB_786"]

print("\nLoading cached reversal trades...")
df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df["rr"]==4.0)&(df["max_cisd_bars"]==5)&df["outcome"].isin(["WIN","LOSS"])].copy()

# chronological 70/30 split based on actual fills
cut=df["fill_time"].min()+(df["fill_time"].max()-df["fill_time"].min())*.70
rows=[]

def metrics(x):
    if x.empty:return None
    wins=(x.outcome=="WIN").sum()
    eq=x.result_r.cumsum()
    dd=(eq-eq.cummax()).min()
    return len(x),wins/len(x)*100,x.result_r.mean(),abs(dd)

for entry in ENTRIES:
    base=df[df.entry==entry].sort_values("fill_time")
    for cisd in CISD_CLOSE_MIN:
        for disp in DISP_MIN:
            z=base[(base.confirm_close_pos>=cisd)&(base.disp_atr>=disp)]
            tr=z[z.fill_time<cut]
            va=z[z.fill_time>=cut]
            a=metrics(tr); b=metrics(va)
            if not a or not b:continue
            rows.append(dict(entry=entry,cisd_close_min=cisd,displacement_min_atr=disp,
                train_trades=a[0],train_wr=a[1],train_exp_r=a[2],train_dd_r=a[3],
                valid_trades=b[0],valid_wr=b[1],valid_exp_r=b[2],valid_dd_r=b[3],
                robust_wr=min(a[1],b[1])))

r=pd.DataFrame(rows).sort_values(["robust_wr","valid_trades"],ascending=[False,False])
r.to_csv(OUTFILE,index=False)

print("\n=== V4 CONFIRMED-CHANGES SCAN: 4R ONLY ===")
print("Removed from filtering: volume, absorption, FVG, IFVG")
print("Testing CISD close:",CISD_CLOSE_MIN)
print("Testing displacement ATR:",DISP_MIN)
print("\nTOP 25:")
print(r.head(25).round(2).to_string(index=False))
print("\nSaved:",OUTFILE)
