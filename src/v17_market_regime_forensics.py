import pandas as pd, numpy as np
tr=pd.read_csv("data/v15_option2_loss_forensics.csv")
tr["candidate_time"]=pd.to_datetime(tr.candidate_time,utc=True)
tr=tr.sort_values("candidate_time").reset_index(drop=True)
tr["win"]=(tr.outcome=="WIN").astype(int)
raw=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
# detect timestamp column
tc=next((c for c in ["timestamp","time","datetime","date"] if c in raw.columns),None)
if tc is None: raise ValueError(f"No timestamp column. Columns: {list(raw.columns)}")
raw[tc]=pd.to_datetime(raw[tc],utc=True)
raw=raw.sort_values(tc).set_index(tc)
# causal ATR
prev=raw.close.shift(1)
raw["tr"]=np.maximum(raw.high-raw.low,np.maximum((raw.high-prev).abs(),(raw.low-prev).abs()))
raw["atr20"]=raw.tr.rolling(20,min_periods=10).mean()
def features(t):
 h=raw.loc[:t].tail(61)
 if len(h)<31:return {}
 out={}
 atr=h.atr20.iloc[-1]
 for n in [15,30,60]:
  x=h.tail(n)
  ret=x.close.iloc[-1]-x.open.iloc[0]
  path=x.close.diff().abs().sum()
  rng=x.high.max()-x.low.min()
  out[f"ret{n}_atr"]=ret/atr if atr else np.nan
  out[f"eff{n}"]=abs(ret)/path if path else 0
  out[f"loc{n}"]=(x.close.iloc[-1]-x.low.min())/rng if rng else .5
  out[f"range{n}_atr"]=rng/atr if atr else np.nan
  out[f"upfrac{n}"]=(x.close.diff()>0).mean()
 return out
F=pd.DataFrame([features(t) for t in tr.candidate_time])
q=pd.concat([tr,F],axis=1)
print("=== V17 PRE-ENTRY MARKET REGIME FORENSICS ===")
print(f"Trades {len(q)} | WR {100*q.win.mean():.2f}%")
cols=[c for c in q.columns if any(c.startswith(p) for p in ["ret","eff","loc","range","upfrac"])]
rows=[]
for c in cols:
 a=q[q.win==1][c];b=q[q.win==0][c];sd=q[c].std();e=(b.mean()-a.mean())/sd if sd else 0
 rows.append([c,a.mean(),b.mean(),e])
r=pd.DataFrame(rows,columns=["feature","win_mean","loss_mean","effect_loss_minus_win"]).sort_values("effect_loss_minus_win",key=lambda s:s.abs(),ascending=False)
print(r.round(3).to_string(index=False))
print("\nWR by quintile for strongest features:")
for c in r.head(8).feature:
 try:
  b=pd.qcut(q[c],5,duplicates="drop")
  x=q.groupby(b,observed=True).win.agg(["count","mean"]);x["mean"]*=100
  print("\n",c);print(x.round(2).to_string())
 except: pass
q.to_csv("data/v17_market_regime_forensics.csv",index=False)
print("\nSaved: data/v17_market_regime_forensics.csv")
