import pandas as pd

INPUT_FILE = "data/mnq_all_contracts.parquet"

OUTPUT_1M = "data/mnq_continuous_1m.parquet"
OUTPUT_3M = "data/mnq_continuous_3m.parquet"


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading MNQ contracts...")

df = pd.read_parquet(INPUT_FILE)

df["time_utc"] = pd.to_datetime(
    df["time_utc"],
    utc=True
)

df["time_ny"] = pd.to_datetime(
    df["time_ny"],
    utc=True
).dt.tz_convert("America/New_York")

df["session_end_date"] = pd.to_datetime(
    df["session_end_date"]
).dt.date

df = df.sort_values(
    ["session_end_date", "time_utc", "ticker"]
).reset_index(drop=True)


# ============================================================
# DETERMINE DOMINANT CONTRACT BY SESSION VOLUME
# ============================================================

print("Calculating dominant contract by session volume...")

daily_volume = (
    df.groupby(
        ["session_end_date", "ticker"],
        as_index=False
    )["volume"]
    .sum()
)

daily_volume = daily_volume.rename(
    columns={
        "volume": "daily_volume"
    }
)

front_contract = (
    daily_volume
    .sort_values(
        ["session_end_date", "daily_volume"],
        ascending=[True, False]
    )
    .drop_duplicates(
        subset=["session_end_date"],
        keep="first"
    )
)

front_contract = front_contract[
    [
        "session_end_date",
        "ticker",
        "daily_volume"
    ]
].rename(
    columns={
        "ticker": "front_ticker"
    }
)


# ============================================================
# BUILD CONTINUOUS 1-MINUTE SERIES
# ============================================================

print("Building continuous 1-minute series...")

df = df.merge(
    front_contract[
        [
            "session_end_date",
            "front_ticker"
        ]
    ],
    on="session_end_date",
    how="left"
)

continuous = df[
    df["ticker"] == df["front_ticker"]
].copy()

continuous = (
    continuous
    .sort_values("time_utc")
    .drop_duplicates(
        subset=["time_utc"],
        keep="first"
    )
    .reset_index(drop=True)
)

continuous["contract_roll"] = (
    continuous["ticker"]
    != continuous["ticker"].shift(1)
)

if len(continuous) > 0:
    continuous.loc[
        continuous.index[0],
        "contract_roll"
    ] = False

continuous["contract_roll"] = (
    continuous["contract_roll"]
    .fillna(False)
    .astype(bool)
)


# ============================================================
# SAVE 1-MINUTE DATA
# ============================================================

continuous.to_parquet(
    OUTPUT_1M,
    index=False
)


# ============================================================
# BUILD 3-MINUTE STRATEGY CANDLES
# ============================================================

print("Building 3-minute strategy candles...")

continuous_for_3m = continuous.copy()

continuous_for_3m = continuous_for_3m.set_index(
    "time_ny"
)

three_minute = (
    continuous_for_3m
    .groupby("ticker")
    .resample(
        "3min",
        origin="start_day"
    )
    .agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "transactions": "sum",
        "dollar_volume": "sum",
        "session_end_date": "first",
        "contract_roll": "max",
    })
)

three_minute = (
    three_minute
    .dropna(
        subset=[
            "open",
            "high",
            "low",
            "close"
        ]
    )
    .reset_index()
)

three_minute["contract_roll"] = (
    three_minute["contract_roll"]
    .fillna(False)
    .astype(bool)
)

three_minute["time_utc"] = (
    three_minute["time_ny"]
    .dt.tz_convert("UTC")
)

three_minute = three_minute[
    [
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
        "contract_roll",
    ]
]

three_minute = (
    three_minute
    .sort_values("time_utc")
    .reset_index(drop=True)
)


# ============================================================
# SAVE 3-MINUTE DATA
# ============================================================

three_minute.to_parquet(
    OUTPUT_3M,
    index=False
)


# ============================================================
# QUALITY CHECK
# ============================================================

duplicate_1m = continuous["time_utc"].duplicated().sum()
duplicate_3m = three_minute["time_utc"].duplicated().sum()

invalid_1m = (
    (continuous["high"] < continuous["low"])
    |
    (continuous["high"] < continuous["open"])
    |
    (continuous["high"] < continuous["close"])
    |
    (continuous["low"] > continuous["open"])
    |
    (continuous["low"] > continuous["close"])
).sum()

invalid_3m = (
    (three_minute["high"] < three_minute["low"])
    |
    (three_minute["high"] < three_minute["open"])
    |
    (three_minute["high"] < three_minute["close"])
    |
    (three_minute["low"] > three_minute["open"])
    |
    (three_minute["low"] > three_minute["close"])
).sum()


# ============================================================
# CONTRACT ROLL SUMMARY
# ============================================================

rolls_1m = continuous[
    continuous["contract_roll"] == True
].copy()

rolls_3m = three_minute[
    three_minute["contract_roll"] == True
].copy()


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n===================================")
print(" CONTINUOUS MNQ DATASET COMPLETE")
print("===================================\n")

print(
    "1-minute candles:",
    f"{len(continuous):,}"
)

print(
    "3-minute candles:",
    f"{len(three_minute):,}"
)

print(
    "\nFirst:",
    three_minute["time_ny"].min()
)

print(
    "Last:",
    three_minute["time_ny"].max()
)

print("\nContracts used:")

print(
    three_minute["ticker"]
    .value_counts()
    .sort_index()
    .to_string()
)

print("\n=== QUALITY CHECK ===")

print(
    "Duplicate 1M timestamps:",
    duplicate_1m
)

print(
    "Duplicate 3M timestamps:",
    duplicate_3m
)

print(
    "Invalid 1M OHLC candles:",
    invalid_1m
)

print(
    "Invalid 3M OHLC candles:",
    invalid_3m
)

print("\n=== CONTRACT ROLLS ===")

if rolls_1m.empty:

    print("No contract rolls detected.")

else:

    print(
        rolls_1m[
            [
                "time_ny",
                "ticker",
                "session_end_date"
            ]
        ].to_string(index=False)
    )

print(
    "\nTotal contract rolls:",
    len(rolls_1m)
)

print(
    f"\nSaved 1M: {OUTPUT_1M}"
)

print(
    f"Saved 3M: {OUTPUT_3M}"
)

print(
    "\nREADY FOR STRATEGY RESEARCH."
)