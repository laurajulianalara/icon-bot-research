import pandas as pd, numpy as np
tr=pd.read_csv("data/v27_option2a_trades.csv")
bars=pd.read_parquet("data/mnq_continuous_1m.parquet")
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True)

tc=next((c for c in ["timestamp","time","datetime","date"] if c in bars.columns),None)
if tc is None:
    bars.index=pd.to_datetime(bars.index,utc=True); bars=bars.sort_index()
else:
    bars[tc]=pd.to_datetime(bars[tc],utc=True); bars=bars.sort_values(tc).set_index(tc)

# V31 must use the actual schema produced by the research engine.
print("Trade columns:",list(tr.columns))
entry_col=next((c for c in ["entry","entry_price","entry_px","entry_level","entryPrice"] if c in tr.columns),None)
stop_col=next((c for c in ["stop","stop_price","stop_px","stop_level","sl","sl_price","stopPrice"] if c in tr.columns),None)
side_col=next((c for c in ["side","direction","dir","trade_side"] if c in tr.columns),None)
# If explicit risk/stop is absent, derive 1R from a 4R target where available.
target_col=next((c for c in ["target","target_price","target_px","tp","tp_price","targetPrice"] if c in tr.columns),None)
risk_col=next((c for c in ["risk_points","risk","risk_distance","risk_pts"] if c in tr.columns),None)
if entry_col is None or side_col is None or (stop_col is None and target_col is None and risk_col is None):
    raise RuntimeError("SCHEMA|"+",".join(tr.columns))

rows=[]
for _,r in tr.iterrows():
    t=r["candidate_time"]; entry=float(r[entry_col])
    if stop_col is not None: risk=abs(entry-float(r[stop_col]))
    elif risk_col is not None: risk=abs(float(r[risk_col]))
    else: risk=abs(float(r[target_col])-entry)/4.0
    if risk<=0: continue
    w=bars.loc[t:t+pd.Timedelta(hours=4)]
    if w.empty: continue
    side=str(r[side_col]).upper(); is_long=side in ["LONG","BUY","BULL","1","1.0"]
    mfe=((w["high"].max()-entry) if is_long else (entry-w["low"].min()))/risk
    rows.append([t,r.get("session",""),r.get("outcome",""),mfe])

o=pd.DataFrame(rows,columns=["time","session","outcome","mfe_r"])
print("=== OPTION 2A EXPANSION STUDY — 4H FORWARD MFE ===")
print("Trades measured:",len(o))
print(f"Average max expansion: {o.mfe_r.mean():.2f}R | Median: {o.mfe_r.median():.2f}R")
for rr in [4,5,6,8,10,12,15,20]:
    print(f">= {rr:2d}R: {(o.mfe_r>=rr).sum():4d} trades | {100*(o.mfe_r>=rr).mean():5.2f}%")
w=o[o.outcome=="WIN"]
print("\nWINNERS ONLY")
print(f"Count {len(w)} | Avg max {w.mfe_r.mean():.2f}R | Median {w.mfe_r.median():.2f}R")
for rr in [5,6,8,10,12,15,20]:
    print(f">= {rr:2d}R: {(w.mfe_r>=rr).sum():4d} | {100*(w.mfe_r>=rr).mean():5.2f}% of winners")
print("\nBY SESSION")
print(o.groupby("session").mfe_r.agg(["count","mean","median","max"]).round(2).to_string())
o.to_csv("data/v31_option2a_expansion_mfe.csv",index=False)
