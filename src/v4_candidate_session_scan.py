import pandas as pd
import numpy as np

INFILE="data/v3_reversal_features.parquet"
OUTFILE="data/v4_candidate_session_scan.csv"

df=pd.read_parquet(INFILE)
df["fill_time"]=pd.to_datetime(df["fill_time"])
df=df[(df.rr==4.0)&(df.max_cisd_bars==5)&(df.entry=="NO_FIB")&df.outcome.isin(["WIN","LOSS"])].copy()

# Keep the confirmed candidate logic. Compare session combinations only.
z=df[(df.confirm_close_pos>=.95)&(df.disp_atr>=1.30)&(df.sweep_atr>=.30)].sort_values("fill_time").copy()
cut=z.fill_time.min()+(z.fill_time.max()-z.fill_time.min())*.70

session_sets=[
 ["ASIA"],["LONDON"],["NYAM"],["NYPM"],
 ["ASIA","NYAM"],["ASIA","NYPM"],["NYAM","NYPM"],
 ["ASIA","NYAM","NYPM"],["ASIA","LONDON","NYAM","NYPM"]
]

def m(x):
    if x.empty:return (0,np.nan,np.nan,np.nan)
    eq=x.result_r.cumsum()
    dd=abs((eq-eq.cummax()).min())
    return len(x),(x.outcome=="WIN").mean()*100,x.result_r.mean(),dd

rows=[]
for ss in session_sets:
    q=z[z.session.isin(ss)]
    tr=q[q.fill_time<cut]; va=q[q.fill_time>=cut]
    a=m(tr); b=m(va)
    rows.append(dict(sessions="+".join(ss),train_trades=a[0],train_wr=a[1],train_exp_r=a[2],train_dd_r=a[3],
                     valid_trades=b[0],valid_wr=b[1],valid_exp_r=b[2],valid_dd_r=b[3],
                     robust_wr=min(a[1],b[1]) if a[0] and b[0] else np.nan))
r=pd.DataFrame(rows).sort_values(["robust_wr","valid_trades"],ascending=[False,False])
r.to_csv(OUTFILE,index=False)
print("\n=== V4 SESSION ROBUSTNESS SCAN — 4R ===")
print("Core: NO_FIB | CISD >= .95 | displacement >= 1.30 ATR | sweep >= .30 ATR")
print(r.round(2).to_string(index=False))
print("\nSaved:",OUTFILE)
