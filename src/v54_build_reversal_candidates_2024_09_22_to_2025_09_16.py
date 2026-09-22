import pandas as pd
import numpy as np

# ============================================================
# SETTINGS
# ============================================================

DATA_3M = "data/mnq_2024_09_22_to_2025_09_16_continuous_3m.parquet"
OUTPUT = "data/reversal_candidates_2024_09_22_to_2025_09_16.parquet"

SESSIONS = {
    "ASIA": ("20:00", "00:00"),
    "LONDON": ("02:00", "05:00"),
    "NYAM": ("09:30", "12:30"),
    "NYPM": ("13:30", "17:00"),
}

FIB_LEVELS = [
    0.618,
    0.705,
    0.786,
]


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading 3-minute MNQ data...")

df = pd.read_parquet(DATA_3M)

df["time_ny"] = pd.to_datetime(df["time_ny"])

df = (
    df
    .sort_values("time_ny")
    .reset_index(drop=True)
)

print("Candles:", f"{len(df):,}")


# ============================================================
# BASIC FEATURES
# ============================================================

print("Calculating market features...")

df["range"] = df["high"] - df["low"]

df["body"] = (
    df["close"] - df["open"]
).abs()

df["upper_wick"] = (
    df["high"]
    - df[["open", "close"]].max(axis=1)
)

df["lower_wick"] = (
    df[["open", "close"]].min(axis=1)
    - df["low"]
)

df["bullish"] = (
    df["close"] > df["open"]
)

df["bearish"] = (
    df["close"] < df["open"]
)


# ============================================================
# ATR
# ============================================================

previous_close = df["close"].shift(1)

true_range = pd.concat(
    [
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs(),
    ],
    axis=1
).max(axis=1)

df["atr_20"] = (
    true_range
    .rolling(20)
    .mean()
)


# ============================================================
# RELATIVE VOLUME
# ============================================================

df["volume_avg_20"] = (
    df["volume"]
    .rolling(20)
    .mean()
)

df["relative_volume"] = (
    df["volume"]
    / df["volume_avg_20"]
)


# ============================================================
# ABSORPTION PROXIES
# ============================================================

df["range_vs_atr"] = (
    df["range"]
    / df["atr_20"]
)

df["body_percent"] = np.where(
    df["range"] > 0,
    df["body"] / df["range"],
    0
)

df["lower_wick_percent"] = np.where(
    df["range"] > 0,
    df["lower_wick"] / df["range"],
    0
)

df["upper_wick_percent"] = np.where(
    df["range"] > 0,
    df["upper_wick"] / df["range"],
    0
)


# ============================================================
# SESSION ASSIGNMENT
# ============================================================

def get_session(timestamp):

    minutes = (
        timestamp.hour * 60
        + timestamp.minute
    )

    # Asia 20:00 → midnight
    if 20 * 60 <= minutes:
        return "ASIA"

    # London 02:00 → 05:00
    if 2 * 60 <= minutes < 5 * 60:
        return "LONDON"

    # NY AM 09:30 → 12:30
    if (
        9 * 60 + 30
        <= minutes
        < 12 * 60 + 30
    ):
        return "NYAM"

    # NY PM 13:30 → 17:00
    if (
        13 * 60 + 30
        <= minutes
        < 17 * 60
    ):
        return "NYPM"

    return None


df["session"] = (
    df["time_ny"]
    .apply(get_session)
)

session_df = df[
    df["session"].notna()
].copy()


# ============================================================
# UNIQUE SESSION INSTANCE
# ============================================================

session_df["session_date"] = (
    session_df["time_ny"].dt.date
)

# Asia belongs to the session that STARTS that evening.
session_df["session_id"] = (
    session_df["session_date"].astype(str)
    + "_"
    + session_df["session"]
)


# ============================================================
# IDENTIFY EVERY NEW SESSION EXTREME
# ============================================================

print("Finding session-extreme candidates...")

candidates = []

for session_id, group in session_df.groupby(
    "session_id",
    sort=False
):

    group = (
        group
        .sort_values("time_ny")
        .reset_index()
    )

    if len(group) < 3:
        continue

    running_high = None
    running_low = None

    for i in range(len(group)):

        row = group.iloc[i]

        if running_high is None:

            running_high = row["high"]
            running_low = row["low"]
            continue

        new_high = (
            row["high"] > running_high
        )

        new_low = (
            row["low"] < running_low
        )

        # ------------------------------------------
        # NEW SESSION LOW = BULLISH REVERSAL CANDIDATE
        # ------------------------------------------

        if new_low:

            candidates.append({
                "time_ny": row["time_ny"],
                "session_id": session_id,
                "session": row["session"],
                "ticker": row["ticker"],

                "direction": "LONG",

                "extreme": row["low"],

                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],

                "volume": row["volume"],
                "relative_volume": row["relative_volume"],

                "atr": row["atr_20"],
                "range_vs_atr": row["range_vs_atr"],

                "body_percent": row["body_percent"],
                "wick_percent": row["lower_wick_percent"],

                "previous_session_low": running_low,
                "previous_session_high": running_high,

                "sweep_distance": (
                    running_low - row["low"]
                ),
            })

        # ------------------------------------------
        # NEW SESSION HIGH = BEARISH REVERSAL CANDIDATE
        # ------------------------------------------

        if new_high:

            candidates.append({
                "time_ny": row["time_ny"],
                "session_id": session_id,
                "session": row["session"],
                "ticker": row["ticker"],

                "direction": "SHORT",

                "extreme": row["high"],

                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],

                "volume": row["volume"],
                "relative_volume": row["relative_volume"],

                "atr": row["atr_20"],
                "range_vs_atr": row["range_vs_atr"],

                "body_percent": row["body_percent"],
                "wick_percent": row["upper_wick_percent"],

                "previous_session_low": running_low,
                "previous_session_high": running_high,

                "sweep_distance": (
                    row["high"] - running_high
                ),
            })

        running_high = max(
            running_high,
            row["high"]
        )

        running_low = min(
            running_low,
            row["low"]
        )


# ============================================================
# CANDIDATE DATAFRAME
# ============================================================

candidates = pd.DataFrame(candidates)

if candidates.empty:
    raise ValueError(
        "No reversal candidates were found."
    )

candidates = candidates.sort_values(
    "time_ny"
).reset_index(drop=True)


# ============================================================
# SAVE
# ============================================================

candidates.to_parquet(
    OUTPUT,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("\n===================================")
print(" REVERSAL CANDIDATE SCAN COMPLETE")
print("===================================\n")

print(
    "Candidates:",
    f"{len(candidates):,}"
)

print("\nBy direction:")

print(
    candidates["direction"]
    .value_counts()
    .to_string()
)

print("\nBy session:")

print(
    candidates["session"]
    .value_counts()
    .to_string()
)

days = (
    candidates["time_ny"]
    .dt.date
    .nunique()
)

print(
    "\nTrading days:",
    days
)

print(
    "Candidates/day:",
    round(
        len(candidates) / days,
        2
    )
)

print(
    "\nAverage relative volume:",
    round(
        candidates["relative_volume"].mean(),
        2
    )
)

print(
    "Average wick %:",
    round(
        candidates["wick_percent"].mean() * 100,
        1
    ),
    "%"
)

print(
    f"\nSaved: {OUTPUT}"
)

print(
    "\nNEXT: CISD + absorption + Fib outcome engine."
)