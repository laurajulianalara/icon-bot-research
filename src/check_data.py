import pandas as pd

FILE = "data/MNQU6_test.parquet"

df = pd.read_parquet(FILE)

print("\n=== MNQ DATA QUALITY CHECK ===\n")

print("Total candles:", len(df))
print("First NY timestamp:", df["time_ny"].min())
print("Last NY timestamp:", df["time_ny"].max())

print("\nDuplicate timestamps:")
print(df["time_utc"].duplicated().sum())

print("\nMissing values:")
print(df.isna().sum())

bad_ohlc = df[
    (df["high"] < df["low"]) |
    (df["high"] < df["open"]) |
    (df["high"] < df["close"]) |
    (df["low"] > df["open"]) |
    (df["low"] > df["close"])
]

print("\nInvalid OHLC candles:")
print(len(bad_ohlc))

print("\nZero-volume candles:")
print((df["volume"] == 0).sum())

# Put candles in chronological order
df = df.sort_values("time_utc")

# Measure gaps between consecutive candles
df["gap_minutes"] = (
    df["time_utc"].diff().dt.total_seconds() / 60
)

gaps = df[df["gap_minutes"] > 1]

print("\nGaps larger than 1 minute:")
print(len(gaps))

print("\nLargest gaps:")
print(
    gaps[
        ["time_ny", "gap_minutes"]
    ].sort_values("gap_minutes", ascending=False).head(10)
)

print("\n=== CHECK COMPLETE ===")