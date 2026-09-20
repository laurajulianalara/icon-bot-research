import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MASSIVE_API_KEY")

if not API_KEY:
    raise ValueError("MASSIVE_API_KEY was not found in .env")

CONTRACT_FILE = "data/mnq_contracts.parquet"
OUTPUT_FILE = "data/mnq_all_contracts.parquet"

RESEARCH_START = pd.Timestamp("2024-06-10")
RESEARCH_END = pd.Timestamp("2026-09-18")

REQUEST_DELAY = 13  # stays under free 5 calls/minute limit


def download_contract(ticker, start_date, end_date):

    url = f"https://api.massive.com/futures/v1/aggs/{ticker}"

    params = {
        "resolution": "1min",
        "window_start.gte": start_date.strftime("%Y-%m-%d"),
        "window_start.lte": end_date.strftime("%Y-%m-%d"),
        "limit": 50000,
        "sort": "window_start.asc",
        "apiKey": API_KEY,
    }

    all_results = []

    while True:

        print(
            f"Downloading {ticker}: "
            f"{start_date.date()} → {end_date.date()}"
        )

        response = requests.get(
            url,
            params=params,
            timeout=90
        )

        if response.status_code == 429:

            print("Rate limit reached — waiting 65 seconds...")
            time.sleep(65)
            continue

        if response.status_code != 200:

            print(
                f"ERROR {ticker}:",
                response.status_code,
                response.text
            )

            return pd.DataFrame()

        data = response.json()

        results = data.get("results", [])

        all_results.extend(results)

        next_url = data.get("next_url")

        if not next_url:
            break

        print(
            f"{ticker}: another page exists..."
        )

        time.sleep(REQUEST_DELAY)

        url = next_url

        params = {
            "apiKey": API_KEY
        }

    if not all_results:
        return pd.DataFrame()

    rows = []

    for candle in all_results:

        timestamp = candle.get("window_start")

        if timestamp is None:
            continue

        rows.append({
            "time_utc": pd.to_datetime(
                timestamp,
                unit="ns",
                utc=True
            ),
            "ticker": ticker,
            "session_end_date": candle.get(
                "session_end_date"
            ),
            "open": candle.get("open"),
            "high": candle.get("high"),
            "low": candle.get("low"),
            "close": candle.get("close"),
            "volume": candle.get("volume"),
            "transactions": candle.get(
                "transactions"
            ),
            "dollar_volume": candle.get(
                "dollar_volume"
            ),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = (
        df
        .drop_duplicates(subset=["time_utc"])
        .sort_values("time_utc")
        .reset_index(drop=True)
    )

    df["time_ny"] = (
        df["time_utc"]
        .dt.tz_convert("America/New_York")
    )

    df["session_end_date"] = pd.to_datetime(
        df["session_end_date"]
    )

    return df


# ---------------------------------------------------------
# LOAD CONTRACT LIST
# ---------------------------------------------------------

contracts = pd.read_parquet(CONTRACT_FILE)

contracts["first_trade_date"] = pd.to_datetime(
    contracts["first_trade_date"]
)

contracts["last_trade_date"] = pd.to_datetime(
    contracts["last_trade_date"]
)

contracts = contracts.sort_values(
    "last_trade_date"
).reset_index(drop=True)

print("\n=== CONTRACTS TO DOWNLOAD ===\n")

print(
    contracts[
        [
            "ticker",
            "first_trade_date",
            "last_trade_date"
        ]
    ].to_string(index=False)
)

print()


# ---------------------------------------------------------
# DOWNLOAD EACH CONTRACT
# ---------------------------------------------------------

frames = []

for i, contract in contracts.iterrows():

    ticker = contract["ticker"]

    start_date = max(
        RESEARCH_START,
        contract["first_trade_date"]
    )

    end_date = min(
        RESEARCH_END,
        contract["last_trade_date"]
    )

    if start_date > end_date:
        continue

    df = download_contract(
        ticker,
        start_date,
        end_date
    )

    if df.empty:

        print(f"{ticker}: NO DATA")

    else:

        print(
            f"{ticker}: {len(df):,} candles saved in memory"
        )

        print(
            "   ",
            df["time_ny"].iloc[0],
            "→",
            df["time_ny"].iloc[-1]
        )

        frames.append(df)

    if i < len(contracts) - 1:

        print(
            f"Waiting {REQUEST_DELAY} seconds "
            "for free API limit...\n"
        )

        time.sleep(REQUEST_DELAY)


# ---------------------------------------------------------
# COMBINE RAW CONTRACT DATA
# ---------------------------------------------------------

if not frames:
    raise ValueError("No MNQ data was downloaded.")

all_data = pd.concat(
    frames,
    ignore_index=True
)

all_data = (
    all_data
    .sort_values(["time_utc", "ticker"])
    .reset_index(drop=True)
)

columns = [
    "time_utc",
    "time_ny",
    "session_end_date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "transactions",
    "dollar_volume",
]

all_data = all_data[columns]

os.makedirs(
    "data",
    exist_ok=True
)

all_data.to_parquet(
    OUTPUT_FILE,
    index=False
)


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

print("\n===================================")
print(" FULL MNQ DOWNLOAD COMPLETE")
print("===================================\n")

print(
    "Total candles:",
    f"{len(all_data):,}"
)

print(
    "Contracts:",
    all_data["ticker"].nunique()
)

print(
    "First NY timestamp:",
    all_data["time_ny"].min()
)

print(
    "Last NY timestamp:",
    all_data["time_ny"].max()
)

print(
    "\nCandles per contract:\n"
)

print(
    all_data
    .groupby("ticker")
    .size()
    .to_string()
)

print(
    f"\nSaved: {OUTPUT_FILE}"
)

print(
    "\nNEXT: build continuous MNQ1!-style "
    "series using volume-based contract rolls."
)