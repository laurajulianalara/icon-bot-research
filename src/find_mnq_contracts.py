import os
import re
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MASSIVE_API_KEY")

if not API_KEY:
    raise ValueError("MASSIVE_API_KEY was not found in .env")

URL = "https://api.massive.com/futures/v1/contracts"

# Quarterly MNQ outright format:
# MNQH5, MNQM5, MNQU5, MNQZ5, etc.
OUTRIGHT_PATTERN = re.compile(r"^MNQ[HMUZ]\d+$")

# Dates spread across our research period.
# This avoids getting trapped in the first 1,000 historical records.
SEARCH_DATES = [
    "2024-06-10",
    "2024-09-15",
    "2024-12-15",
    "2025-03-15",
    "2025-06-15",
    "2025-09-15",
    "2025-12-15",
    "2026-03-15",
    "2026-06-15",
    "2026-09-18",
]

all_contracts = {}

for search_date in SEARCH_DATES:

    params = {
        "product_code": "MNQ",
        "date": search_date,
        "limit": 1000,
        "apiKey": API_KEY,
    }

    response = requests.get(
        URL,
        params=params,
        timeout=30
    )

    print(
        f"{search_date} | Status: {response.status_code}"
    )

    if response.status_code != 200:
        print(response.text)
        continue

    results = response.json().get("results", [])

    for contract in results:

        ticker = contract.get("ticker")

        if not ticker:
            continue

        # Reject spreads
        if "-" in ticker:
            continue

        # Keep only quarterly MNQ outrights
        if not OUTRIGHT_PATTERN.fullmatch(ticker):
            continue

        all_contracts[ticker] = {
            "ticker": ticker,
            "first_trade_date": contract.get(
                "first_trade_date"
            ),
            "last_trade_date": contract.get(
                "last_trade_date"
            ),
            "active": contract.get("active"),
        }

rows = list(all_contracts.values())

df = pd.DataFrame(rows)

if not df.empty:

    df["first_trade_date"] = pd.to_datetime(
        df["first_trade_date"]
    )

    df["last_trade_date"] = pd.to_datetime(
        df["last_trade_date"]
    )

    research_start = pd.Timestamp("2024-06-10")
    research_end = pd.Timestamp("2026-09-19")

    df = df[
        (df["last_trade_date"] >= research_start)
        &
        (df["first_trade_date"] <= research_end)
    ]

    df = (
        df
        .drop_duplicates(subset=["ticker"])
        .sort_values("last_trade_date")
        .reset_index(drop=True)
    )

print("\n=== MNQ CONTRACTS FOR BACKTEST ===\n")

if df.empty:

    print("No contracts found.")

else:

    print(
        df[
            [
                "ticker",
                "first_trade_date",
                "last_trade_date",
                "active",
            ]
        ].to_string(index=False)
    )

print("\nContracts found:", len(df))

os.makedirs(
    "data",
    exist_ok=True
)

df.to_parquet(
    "data/mnq_contracts.parquet",
    index=False
)

print("\nSaved: data/mnq_contracts.parquet")