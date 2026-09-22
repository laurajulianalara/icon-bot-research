import os,time,requests,pandas as pd
from dotenv import load_dotenv
load_dotenv()
KEY=os.getenv("MASSIVE_API_KEY")
if not KEY: raise ValueError("MASSIVE_API_KEY missing")
START=pd.Timestamp("2024-09-18"); END=pd.Timestamp("2025-09-17")
OUT="data/mnq_2024_09_18_to_2025_09_17_raw_1m.parquet"
# MNQ quarterly contracts spanning the frozen holdout year. Querying extra adjacent contracts is intentional;
# continuous builder will select the active contract later.
months=[("Z",24),("H",25),("M",25),("U",25),("Z",25)]
tickers=[f"MNQ{m}{str(y)[-1]}" for m,y in months]

def dl(t):
 url=f"https://api.massive.com/futures/v1/aggs/{t}"; rows=[]
 params={"resolution":"1min","window_start.gte":START.strftime("%Y-%m-%d"),"window_start.lte":END.strftime("%Y-%m-%d"),"limit":50000,"sort":"window_start.asc","apiKey":KEY}
 while True:
  q=requests.get(url,params=params,timeout=90)
  if q.status_code==429: time.sleep(65); continue
  if q.status_code!=200: print(t,"ERROR",q.status_code,q.text[:300]); return pd.DataFrame()
  d=q.json(); rows+=d.get("results",[]); nxt=d.get("next_url")
  if not nxt: break
  url=nxt; params={"apiKey":KEY}; time.sleep(13)
 if not rows:return pd.DataFrame()
 z=pd.DataFrame({"time_utc":[pd.to_datetime(x["window_start"],unit="ns",utc=True) for x in rows],
 "ticker":t,"open":[x.get("open") for x in rows],"high":[x.get("high") for x in rows],
 "low":[x.get("low") for x in rows],"close":[x.get("close") for x in rows],
 "volume":[x.get("volume",0) for x in rows]})
 z["time_ny"]=z.time_utc.dt.tz_convert("America/New_York")
 return z.drop_duplicates("time_utc").sort_values("time_utc")

fs=[]
for n,t in enumerate(tickers):
 print("Downloading",t,START.date(),"->",END.date(),flush=True)
 x=dl(t)
 print(t,f"{len(x):,} candles", (x.time_ny.min() if len(x) else ""), "->", (x.time_ny.max() if len(x) else ""),flush=True)
 if len(x):fs.append(x)
 if n<len(tickers)-1:time.sleep(13)
if not fs:raise ValueError("No prior-year data downloaded")
d=pd.concat(fs,ignore_index=True).sort_values(["time_utc","ticker"])
os.makedirs("data",exist_ok=True);d.to_parquet(OUT,index=False)
print("\nPRIOR-YEAR RAW DOWNLOAD COMPLETE")
print("Candles:",f"{len(d):,}","Contracts:",d.ticker.nunique())
print("First:",d.time_ny.min(),"Last:",d.time_ny.max())
print("Saved:",OUT)
print("\nNEXT: build isolated continuous series, candidates, then run frozen Icon Bot Funded rules.")
