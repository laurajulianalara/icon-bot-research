import pandas as pd
import numpy as np

# ============================================================
# SETTINGS
# ============================================================

DATA_3M = "data/mnq_continuous_3m.parquet"
CANDIDATES = "data/reversal_candidates.parquet"
OUTPUT = "data/reversal_analysis.parquet"

# Search up to 10 x 3-minute candles after an extreme for CISD
MAX_CISD_BARS = 10

# Measure reversal potential for 30 x 3-minute candles
FORWARD_BARS = 30

FIB_LEVELS = [0.618, 0.705, 0.786]


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading data...")

df = pd.read_parquet(DATA_3M)
candidates = pd.read_parquet(CANDIDATES)

df["time_ny"] = pd.to_datetime(df["time_ny"])
candidates["time_ny"] = pd.to_datetime(
    candidates["time_ny"]
)

df = (
    df
    .sort_values("time_ny")
    .reset_index(drop=True)
)

candidates = (
    candidates
    .sort_values("time_ny")
    .reset_index(drop=True)
)

print(
    "Candidates:",
    f"{len(candidates):,}"
)


# ============================================================
# MAP TIMESTAMP TO 3M INDEX
# ============================================================

time_to_index = pd.Series(
    df.index.values,
    index=df["time_ny"]
).to_dict()


# ============================================================
# ANALYZE EACH CANDIDATE
# ============================================================

print("Analyzing CISD + reversal behavior...")

results = []

total = len(candidates)

for n, candidate in candidates.iterrows():

    if n % 2500 == 0:
        print(
            f"Processing {n:,} / {total:,}"
        )

    candidate_time = candidate["time_ny"]

    if candidate_time not in time_to_index:
        continue

    idx = time_to_index[candidate_time]

    direction = candidate["direction"]

    extreme = candidate["extreme"]

    extreme_open = candidate["open"]

    session = candidate["session"]

    ticker = candidate["ticker"]

    # --------------------------------------------------------
    # FIND CISD
    #
    # LONG:
    # close above opening price of bearish delivery candle
    #
    # SHORT:
    # close below opening price of bullish delivery candle
    # --------------------------------------------------------

    cisd_found = False
    cisd_idx = None
    cisd_price = None
    cisd_bars = None

    search_end = min(
        idx + MAX_CISD_BARS + 1,
        len(df)
    )

    # Start with extreme candle open as delivery reference.
    delivery_reference = extreme_open

    for j in range(
        idx + 1,
        search_end
    ):

        row = df.iloc[j]

        # Do not cross contracts
        if row["ticker"] != ticker:
            break

        # Do not cross into another named session
        minutes = (
            row["time_ny"].hour * 60
            + row["time_ny"].minute
        )

        if session == "ASIA":
            valid_time = minutes >= 20 * 60

        elif session == "LONDON":
            valid_time = (
                2 * 60
                <= minutes
                < 5 * 60
            )

        elif session == "NYAM":
            valid_time = (
                9 * 60 + 30
                <= minutes
                < 12 * 60 + 30
            )

        elif session == "NYPM":
            valid_time = (
                13 * 60 + 30
                <= minutes
                < 17 * 60
            )

        else:
            valid_time = False

        if not valid_time:
            break

        # Update delivery reference using opposing candles
        if direction == "LONG":

            # bearish candle contributing to downward delivery
            if row["close"] < row["open"]:
                delivery_reference = row["open"]

            if row["close"] > delivery_reference:

                cisd_found = True
                cisd_idx = j
                cisd_price = delivery_reference
                cisd_bars = j - idx
                break

        else:

            # bullish candle contributing to upward delivery
            if row["close"] > row["open"]:
                delivery_reference = row["open"]

            if row["close"] < delivery_reference:

                cisd_found = True
                cisd_idx = j
                cisd_price = delivery_reference
                cisd_bars = j - idx
                break

    # --------------------------------------------------------
    # IF NO CISD
    # --------------------------------------------------------

    if not cisd_found:

        results.append({
            **candidate.to_dict(),

            "cisd": False,
            "cisd_time": pd.NaT,
            "cisd_price": np.nan,
            "cisd_bars": np.nan,

            "reversal_leg_end": np.nan,

            "fib_618": np.nan,
            "fib_705": np.nan,
            "fib_786": np.nan,

            "fib_618_touched": False,
            "fib_705_touched": False,
            "fib_786_touched": False,

            "mfe_points": np.nan,
            "mae_points": np.nan,
        })

        continue

    cisd_row = df.iloc[cisd_idx]

    # --------------------------------------------------------
    # REVERSAL LEG
    #
    # Extreme -> CISD confirmation move
    # --------------------------------------------------------

    leg = df.iloc[
        idx:cisd_idx + 1
    ]

    if direction == "LONG":

        reversal_leg_end = leg["high"].max()

        leg_size = (
            reversal_leg_end - extreme
        )

        fib_618 = (
            reversal_leg_end
            - leg_size * 0.618
        )

        fib_705 = (
            reversal_leg_end
            - leg_size * 0.705
        )

        fib_786 = (
            reversal_leg_end
            - leg_size * 0.786
        )

    else:

        reversal_leg_end = leg["low"].min()

        leg_size = (
            extreme - reversal_leg_end
        )

        fib_618 = (
            reversal_leg_end
            + leg_size * 0.618
        )

        fib_705 = (
            reversal_leg_end
            + leg_size * 0.705
        )

        fib_786 = (
            reversal_leg_end
            + leg_size * 0.786
        )


    # --------------------------------------------------------
    # FORWARD WINDOW
    # --------------------------------------------------------

    forward_end = min(
        cisd_idx + FORWARD_BARS + 1,
        len(df)
    )

    future = df.iloc[
        cisd_idx + 1:forward_end
    ].copy()

    future = future[
        future["ticker"] == ticker
    ]

    if future.empty:

        fib_618_touched = False
        fib_705_touched = False
        fib_786_touched = False

        mfe = np.nan
        mae = np.nan

    else:

        if direction == "LONG":

            fib_618_touched = (
                future["low"] <= fib_618
            ).any()

            fib_705_touched = (
                future["low"] <= fib_705
            ).any()

            fib_786_touched = (
                future["low"] <= fib_786
            ).any()

            mfe = (
                future["high"].max()
                - extreme
            )

            mae = (
                extreme
                - future["low"].min()
            )

        else:

            fib_618_touched = (
                future["high"] >= fib_618
            ).any()

            fib_705_touched = (
                future["high"] >= fib_705
            ).any()

            fib_786_touched = (
                future["high"] >= fib_786
            ).any()

            mfe = (
                extreme
                - future["low"].min()
            )

            mae = (
                future["high"].max()
                - extreme
            )


    # --------------------------------------------------------
    # ABSORPTION PROXY FLAGS
    # --------------------------------------------------------

    relative_volume = candidate[
        "relative_volume"
    ]

    wick_percent = candidate[
        "wick_percent"
    ]

    range_vs_atr = candidate[
        "range_vs_atr"
    ]

    volume_12 = (
        relative_volume >= 1.2
    )

    volume_15 = (
        relative_volume >= 1.5
    )

    volume_20 = (
        relative_volume >= 2.0
    )

    wick_30 = (
        wick_percent >= 0.30
    )

    wick_40 = (
        wick_percent >= 0.40
    )

    wick_50 = (
        wick_percent >= 0.50
    )

    absorption_basic = (
        volume_12
        and wick_30
    )

    absorption_strong = (
        volume_15
        and wick_40
    )


    # --------------------------------------------------------
    # SAVE RESULT
    # --------------------------------------------------------

    results.append({
        **candidate.to_dict(),

        "cisd": True,
        "cisd_time": cisd_row["time_ny"],
        "cisd_price": cisd_price,
        "cisd_bars": cisd_bars,

        "reversal_leg_end": reversal_leg_end,

        "fib_618": fib_618,
        "fib_705": fib_705,
        "fib_786": fib_786,

        "fib_618_touched": fib_618_touched,
        "fib_705_touched": fib_705_touched,
        "fib_786_touched": fib_786_touched,

        "volume_12": volume_12,
        "volume_15": volume_15,
        "volume_20": volume_20,

        "wick_30": wick_30,
        "wick_40": wick_40,
        "wick_50": wick_50,

        "absorption_basic": absorption_basic,
        "absorption_strong": absorption_strong,

        "mfe_points": mfe,
        "mae_points": mae,
    })


# ============================================================
# RESULTS
# ============================================================

results = pd.DataFrame(results)

results.to_parquet(
    OUTPUT,
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print("\n===================================")
print(" REVERSAL ANALYSIS COMPLETE")
print("===================================\n")

print(
    "Total candidates:",
    f"{len(results):,}"
)

cisd_count = int(
    results["cisd"].sum()
)

print(
    "CISD confirmed:",
    f"{cisd_count:,}"
)

print(
    "CISD rate:",
    f"{cisd_count / len(results) * 100:.1f}%"
)

confirmed = results[
    results["cisd"] == True
]

if not confirmed.empty:

    print("\nAverage bars to CISD:")

    print(
        round(
            confirmed["cisd_bars"].mean(),
            2
        )
    )

    print("\nFib retracement frequency:")

    print(
        "0.618:",
        f"{confirmed['fib_618_touched'].mean() * 100:.1f}%"
    )

    print(
        "0.705:",
        f"{confirmed['fib_705_touched'].mean() * 100:.1f}%"
    )

    print(
        "0.786:",
        f"{confirmed['fib_786_touched'].mean() * 100:.1f}%"
    )

    print("\nAbsorption:")

    print(
        "Basic:",
        f"{confirmed['absorption_basic'].mean() * 100:.1f}%"
    )

    print(
        "Strong:",
        f"{confirmed['absorption_strong'].mean() * 100:.1f}%"
    )

    print("\nCISD by session:")

    print(
        confirmed["session"]
        .value_counts()
        .to_string()
    )

print(
    f"\nSaved: {OUTPUT}"
)

print(
    "\nNEXT: actual trade simulator + "
    "2.5R / 3R / 4R optimization."
)