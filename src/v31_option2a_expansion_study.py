import pandas as pd, numpy as np
tr=pd.read_csv("data/v27_option2a_trades.csv")
bars=pd.read_parquet("data/mnq_continuous_1m.parquet")
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True)

# Normalize time whether parquet stores it as a column or index.
tc=next((c for c in ["timestamp","time","datetime","date"] if c in bars.columns),None)
if tc is None:
    bars.index=pd.to_datetime(bars.index,utc=True)
    bars=bars.sort_index()
else:
    bars[tc]=pd.to_datetime(bars[tc],utc=True)
    bars=bars.sort_values(tc).set_index(tc)

entry_col=next(c for c in ["entry","entry_price","entry_px"] if c in tr.columns)
stop_col=next(c for c in ["stop","stop_price","stop_px"] if c in tr.columns)
side_col=next(c for c in ["side","direction","dir"] if c in tr.columns)

rows=[]
for _,r in tr.iterrows():
    t=r["candidate_time"]; entry=float(r[entry_col]); stop=float(r[stop_col]); risk=abs(entry-stop)
    if risk<=0: continue
    w=bars.loc[t:t+pd.Timedelta(hours=4)]
    if w.empty: continue
    side=str(r[side_col]).upper()
    is_long=side in ["LONG","BUY","BULL","1","1.0"]
    mfe=((w["high"].max()-entry) if is_long else (entry-w["low"].min()))/risk
    rows.append([t,r.get("session",""),r.get("outcome",""),mfe])

o=pd.DataFrame(rows,columns=["time","session","outcome","mfe_r"])
print("=== OPTION 2A EXPANSION STUDY — 4H FORWARD MFE ===")
print("Trades measured:",len(o))
print(f"Average max expansion: {o.mfe_r.mean():.2f}R | Median: {o.mfe_r.median():.2f}R")
for rr in [4,5,6,8,10,12,15,20]:
    print(f">= {rr:2d}R: {(o.mfe_r>=rr).sum():4d} trades | {100*(o.mfe_r>=rr).mean():5.2f}%")
print("\nWINNERS ONLY (trades that reached fixed 4R)")
w=o[o.outcome=="WIN"]
print(f"Count {len(w)} | Avg max {w.mfe_r.mean():.2f}R | Median {w.mfe_r.median():.2f}R")
for rr in [5,6,8,10,12,15,20]:
    print(f">= {rr:2d}R: {(w.mfe_r>=rr).sum():4d} | {100*(w.mfe_r>=rr).mean():5.2f}% of winners")
print("\nBY SESSION")
print(o.groupby("session").mfe_r.agg(["count","mean","median","max"]).round(2).to_string())
o.to_csv("data/v31_option2a_expansion_mfe.csv",index=False)
