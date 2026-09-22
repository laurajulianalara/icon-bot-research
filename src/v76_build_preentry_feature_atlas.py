import pandas as pd
import numpy as np

print("=== V76 CAUSAL PRE-ENTRY FEATURE ATLAS ===")
A=pd.read_csv("data/v56_icon_bot_funded_prior_year_trades.csv")
B=pd.read_csv("data/v27_option2a_trades.csv")
bars=pd.read_parquet("data/mnq_continuous_1m.parquet").sort_values("time_ny").reset_index(drop=True)
bars["t"]=pd.to_datetime(bars.time_ny,utc=True,errors="coerce")
idx=pd.Series(bars.index,index=bars.t).to_dict()

def utc(s): return pd.to_datetime(s,utc=True,errors="coerce")
A["t"]=utc(A.candidate_time); A["sample"]="2024-2025"
B["t"]=utc(B.candidate_time); B["sample"]="2025-2026"
ref=pd.concat([A,B],ignore_index=True,sort=False)

# Outcome labels are future information and are LABELS ONLY, never predictors.
def labels(x):
    i=idx[x.t]; j=i+3
    entry=float(x.entry); risk=float(x.risk)
    stop=entry-risk if x.direction=="LONG" else entry+risk
    fut=bars.iloc[j:min(j+241,len(bars))]
    out={}
    for rr in range(1,7):
        target=entry+rr*risk if x.direction=="LONG" else entry-rr*risk
        y=0
        for _,b in fut.iterrows():
            if x.direction=="LONG":
                if b.low<=stop: y=0; break
                if b.high>=target: y=1; break
            else:
                if b.high>=stop: y=0; break
                if b.low<=target: y=1; break
        out[f"win_{rr}r"]=y
    return out

rows=[]
for n,x in ref.iterrows():
    i=idx.get(x.t)
    if i is None or i<31 or i+3>=len(bars): continue

    # IMPORTANT: predictors stop at signal/entry availability (i+2).
    # No bar i+3 or later is used below.
    pre=bars.iloc[i-30:i+3].copy()
    cur=pre.iloc[-1]
    last3=pre.iloc[-3:]
    last5=pre.iloc[-5:]
    last10=pre.iloc[-10:]
    last20=pre.iloc[-20:]
    last30=pre.iloc[-30:]

    def ret(win):
        z=pre.iloc[-win:]
        return float(z.close.iloc[-1]-z.open.iloc[0])
    def rng(z): return float(z.high.max()-z.low.min())
    def avg_range(z): return float((z.high-z.low).mean())
    def avg_body(z): return float((z.close-z.open).abs().mean())

    d={
      "sample":x["sample"],"candidate_time":x.t,"session":x.session,"direction":x.direction,
      "entry":float(x.entry),"risk":float(x.risk),
      "minute_of_day":int(cur.t.hour*60+cur.t.minute),
      "ret_3m":ret(3),"ret_5m":ret(5),"ret_10m":ret(10),"ret_20m":ret(20),"ret_30m":ret(30),
      "range_3m":rng(last3),"range_5m":rng(last5),"range_10m":rng(last10),
      "range_20m":rng(last20),"range_30m":rng(last30),
      "avg_range_5m":avg_range(last5),"avg_range_10m":avg_range(last10),"avg_range_20m":avg_range(last20),
      "avg_body_5m":avg_body(last5),"avg_body_10m":avg_body(last10),"avg_body_20m":avg_body(last20),
      "up_bars_5":int((last5.close>last5.open).sum()),"down_bars_5":int((last5.close<last5.open).sum()),
      "up_bars_10":int((last10.close>last10.open).sum()),"down_bars_10":int((last10.close<last10.open).sum()),
      "close_vs_10m_high":float(last10.high.max()-cur.close),
      "close_vs_10m_low":float(cur.close-last10.low.min()),
      "close_vs_30m_high":float(last30.high.max()-cur.close),
      "close_vs_30m_low":float(cur.close-last30.low.min()),
    }
    # Preserve existing research features only if they were known by entry.
    safe=["m1_move_atr","m1_body_atr","m1_close_pos","m1_dir_bars5",
          "m2_move_atr","m2_body_atr","m2_close_pos","m2_dir_bars5",
          "sr_dist_atr","sr_touches_030","sr_strength_050","sweep_atr",
          "wick_percent","early_adverse_atr","early_reclaim_atr","reclaim_x_wick"]
    for c in safe:
        if c in x.index and pd.notna(x[c]): d[c]=x[c]
    d.update(labels(x))
    rows.append(d)

out=pd.DataFrame(rows)
out.to_parquet("data/v76_preentry_feature_atlas.parquet",index=False)

print("Reference rows:",len(ref))
print("Atlas rows:",len(out))
print("Predictor cutoff: candidate T+2 / BEFORE entry bar T+3")
print("Future outcome columns are labels only: win_1r ... win_6r")
print("\nRR CHECK")
for r in range(1,7):
    for s,g in out.groupby("sample"):
        print(f"{s} 1:{r} | {int(g[f'win_{r}r'].sum())}/{len(g)} | {100*g[f'win_{r}r'].mean():.2f}%")
print("\nSaved: data/v76_preentry_feature_atlas.parquet")
print("NEXT: compare winner-vs-loser pre-entry signatures separately at every RR, then test those signatures causally on the full candidate universe.")
