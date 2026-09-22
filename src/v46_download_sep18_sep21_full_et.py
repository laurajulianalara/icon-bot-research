import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv(".env")
API_KEY = os.getenv("MASSIVE_API_KEY")
if not API_KEY:
    raise ValueError("MASSIVE_API_KEY was not found in .env")

TICKER = "MNQZ6"
DATES = ["2026-09-18", "2026-09-21"]
url = f"https://api.massive.com/futures/v1/aggs/{TICKER}"

for d in DATES:
    day = pd.Timestamp(d, tz="America/New_York")
    start_utc = day.tz_convert("UTC")
    end_utc = (day + pd.Timedelta(days=1)).tz_convert("UTC")

    params = {
        "resolution": "1min",
        "window_start.gte": start_utc.isoformat(),
        "window_start.lt": end_utc.isoformat(),
        "limit": 50000,
        "sort": "window_start.asc",
        "apiKey": API_KEY,
    }

    r = requests.get(url, params=params, timeout=90)
    print(f"\n{d} STATUS:", r.status_code)
    if r.status_code != 200:
        print(r.text)
        continue

    rows = r.json().get("results", [])
    out = []
    for x in rows:
        ts = x.get("window_start")
        if ts is None:
            continue
        out.append({
            "time_utc": pd.to_datetime(ts, unit="ns", utc=True),
            "ticker": TICKER,
            "open": x.get("open"),
            "high": x.get("high"),
            "low": x.get("low"),
            "close": x.get("close"),
            "volume": x.get("volume"),
        })

    df = pd.DataFrame(out)
    if df.empty:
        print("NO DATA RETURNED")
        continue

    df["time_ny"] = df["time_utc"].dt.tz_convert("America/New_York")
    target = pd.Timestamp(d).date()
    df = df[df["time_ny"].dt.date == target].copy()

    print("CANDLES:", len(df))
    print("FIRST:", df["time_ny"].min())
    print("LAST:", df["time_ny"].max())

    asia = df[
        (df["time_ny"].dt.hour >= 20)
        & (df["time_ny"].dt.hour < 24)
    ]
    print("ASIA 20:00-24:00 CANDLES:", len(asia))
    if not asia.empty:
        print("ASIA FIRST:", asia["time_ny"].min())
        print("ASIA LAST:", asia["time_ny"].max())

    tag = pd.Timestamp(d).strftime("%b%d").lower()
    path = f"data/mnq_{tag}_2026_full_et_1m.parquet"
    df.to_parquet(path, index=False)
    print("SAVED:", path)
