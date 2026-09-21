import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv(".env")
API_KEY = os.getenv("MASSIVE_API_KEY")
if not API_KEY:
    raise ValueError("MASSIVE_API_KEY was not found in .env")

ticker = "MNQZ6"
url = f"https://api.massive.com/futures/v1/aggs/{ticker}"
params = {
    "resolution": "1min",
    "window_start.gte": "2026-09-18",
    "window_start.lte": "2026-09-19",
    "limit": 50000,
    "sort": "window_start.asc",
    "apiKey": API_KEY,
}

r = requests.get(url, params=params, timeout=90)
print("STATUS:", r.status_code)
if r.status_code != 200:
    print(r.text)
    raise SystemExit(1)

rows = r.json().get("results", [])
out = []
for c in rows:
    ts = c.get("window_start")
    if ts is None:
        continue
    out.append({
        "time_utc": pd.to_datetime(ts, unit="ns", utc=True),
        "ticker": ticker,
        "open": c.get("open"),
        "high": c.get("high"),
        "low": c.get("low"),
        "close": c.get("close"),
        "volume": c.get("volume"),
    })

df = pd.DataFrame(out)
if df.empty:
    print("NO DATA RETURNED")
    raise SystemExit

df["time_ny"] = df["time_utc"].dt.tz_convert("America/New_York")
date = pd.Timestamp("2026-09-18").date()
df = df[df["time_ny"].dt.date == date].copy()
print("SEPT 18 CANDLES:", len(df))
print("FIRST:", df["time_ny"].min())
print("LAST:", df["time_ny"].max())
df.to_parquet("data/mnq_sep18_2026_1m.parquet", index=False)
print("SAVED: data/mnq_sep18_2026_1m.parquet")
