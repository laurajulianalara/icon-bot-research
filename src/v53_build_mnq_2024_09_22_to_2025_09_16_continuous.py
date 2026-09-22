import pandas as pd, os
IN="data/mnq_2024_09_18_to_2025_09_17_raw_1m.parquet"
O1="data/mnq_2024_09_22_to_2025_09_16_continuous_1m.parquet"
O3="data/mnq_2024_09_22_to_2025_09_16_continuous_3m.parquet"
d=pd.read_parquet(IN)
d["time_utc"]=pd.to_datetime(d.time_utc,utc=True)
d["time_ny"]=pd.to_datetime(d.time_ny,utc=True).dt.tz_convert("America/New_York")
# CME trade date: evening session belongs to following business/trading date.
ny=d.time_ny
trade_date=(ny.dt.normalize()+pd.to_timedelta((ny.dt.hour>=18).astype(int),unit="D")).dt.date
d["trade_date"]=trade_date
vol=d.groupby(["trade_date","ticker"],as_index=False).volume.sum().rename(columns={"volume":"daily_volume"})
front=vol.sort_values(["trade_date","daily_volume"],ascending=[True,False]).drop_duplicates("trade_date").rename(columns={"ticker":"front_ticker"})
d=d.merge(front[["trade_date","front_ticker"]],on="trade_date",how="left")
c=d[d.ticker==d.front_ticker].copy().sort_values("time_utc").drop_duplicates("time_utc").reset_index(drop=True)
c["contract_roll"]=(c.ticker!=c.ticker.shift()).fillna(False)
if len(c): c.loc[0,"contract_roll"]=False
os.makedirs("data",exist_ok=True); c.to_parquet(O1,index=False)
x=c.set_index("time_ny")
g=x.groupby("ticker").resample("3min",origin="start_day").agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"),volume=("volume","sum"),trade_date=("trade_date","first"),contract_roll=("contract_roll","max")).dropna(subset=["open","high","low","close"]).reset_index()
g["time_utc"]=g.time_ny.dt.tz_convert("UTC");g.to_parquet(O3,index=False)
print("\n=== ICON BOT FUNDED — PRIOR YEAR CONTINUOUS DATA ===")
print("1M candles:",f"{len(c):,}");print("3M candles:",f"{len(g):,}")
print("First:",c.time_ny.min());print("Last:",c.time_ny.max())
print("Contracts used:",c.ticker.value_counts().sort_index().to_dict())
print("Contract rolls:",int(c.contract_roll.sum()))
print("Duplicate 1M:",int(c.time_utc.duplicated().sum()))
bad=((c.high<c.low)|(c.high<c.open)|(c.high<c.close)|(c.low>c.open)|(c.low>c.close)).sum()
print("Invalid OHLC:",int(bad));print("Saved:",O1);print("Saved:",O3)
