import pandas as pd
import numpy as np
from itertools import product

# ============================================================
# SETTINGS
# ============================================================

DATA_1M = "data/mnq_continuous_1m.parquet"
DATA_3M = "data/mnq_continuous_3m.parquet"
ANALYSIS = "data/reversal_analysis.parquet"

OUTPUT = "data/strategy_results.csv"

RR_VALUES = [2.5, 3.0, 4.0]

ENTRY_TYPES = [
    "CISD",
    "FIB_618",
    "FIB_705",
    "FIB_786",
]

ABSORPTION_TYPES = [
    "NONE",
    "BASIC",
    "STRONG",
]

VOLUME_FILTERS = [
    0.0,
    1.2,
    1.5,
    2.0,
]

MAX_ENTRY_WAIT_BARS = 10

MNQ_TICK = 0.25

# Stop buffer beyond reversal extreme
STOP_BUFFER = MNQ_TICK


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading research data...")

one = pd.read_parquet(DATA_1M)
three = pd.read_parquet(DATA_3M)
analysis = pd.read_parquet(ANALYSIS)

one["time_ny"] = pd.to_datetime(one["time_ny"])
three["time_ny"] = pd.to_datetime(three["time_ny"])
analysis["time_ny"] = pd.to_datetime(analysis["time_ny"])
analysis["cisd_time"] = pd.to_datetime(analysis["cisd_time"])

one = one.sort_values("time_ny").reset_index(drop=True)
three = three.sort_values("time_ny").reset_index(drop=True)

analysis = analysis[
    analysis["cisd"] == True
].copy()

analysis = analysis.sort_values(
    "cisd_time"
).reset_index(drop=True)

print(
    "Confirmed CISD candidates:",
    f"{len(analysis):,}"
)


# ============================================================
# PREPARE 1-MINUTE DATA
# ============================================================

one = one.set_index("time_ny")


# ============================================================
# TRADE SIMULATION
# ============================================================

def simulate_trade(
    candidate,
    entry_type,
    rr,
):

    direction = candidate["direction"]
    ticker = candidate["ticker"]

    extreme = candidate["extreme"]

    cisd_time = candidate["cisd_time"]

    if pd.isna(cisd_time):
        return None

    # --------------------------------------------------------
    # ENTRY PRICE
    # --------------------------------------------------------

    if entry_type == "CISD":

        entry = candidate["cisd_price"]

        # Enter after confirmation.
        entry_start = cisd_time

    elif entry_type == "FIB_618":

        entry = candidate["fib_618"]
        entry_start = cisd_time

    elif entry_type == "FIB_705":

        entry = candidate["fib_705"]
        entry_start = cisd_time

    elif entry_type == "FIB_786":

        entry = candidate["fib_786"]
        entry_start = cisd_time

    else:
        return None

    if pd.isna(entry):
        return None

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    if direction == "LONG":

        stop = extreme - STOP_BUFFER
        risk = entry - stop

        if risk <= 0:
            return None

        target = entry + risk * rr

    else:

        stop = extreme + STOP_BUFFER
        risk = stop - entry

        if risk <= 0:
            return None

        target = entry - risk * rr

    # --------------------------------------------------------
    # ENTRY WINDOW
    #
    # 10 x 3-minute bars = 30 minutes
    # --------------------------------------------------------

    entry_deadline = (
        entry_start
        + pd.Timedelta(
            minutes=MAX_ENTRY_WAIT_BARS * 3
        )
    )

    try:

        entry_window = one.loc[
            entry_start:entry_deadline
        ]

    except KeyError:

        return None

    entry_window = entry_window[
        entry_window["ticker"] == ticker
    ]

    if entry_window.empty:
        return None

    # --------------------------------------------------------
    # FIND ENTRY
    # --------------------------------------------------------

    fill_time = None

    if entry_type == "CISD":

        # CISD market-style entry:
        # first available 1-minute candle after confirmation.

        future_entry = entry_window[
            entry_window.index > cisd_time
        ]

        if future_entry.empty:
            return None

        fill_time = future_entry.index[0]

        # Use next 1M open to avoid entering
        # before CISD candle actually closed.
        entry = future_entry.iloc[0]["open"]

        if direction == "LONG":

            risk = entry - stop

            if risk <= 0:
                return None

            target = entry + risk * rr

        else:

            risk = stop - entry

            if risk <= 0:
                return None

            target = entry - risk * rr

    else:

        for timestamp, bar in entry_window.iterrows():

            if timestamp <= cisd_time:
                continue

            if (
                bar["low"] <= entry
                <= bar["high"]
            ):

                fill_time = timestamp
                break

    if fill_time is None:
        return None

    # --------------------------------------------------------
    # SIMULATE AFTER ENTRY
    # --------------------------------------------------------

    trade_end = (
        fill_time
        + pd.Timedelta(hours=4)
    )

    trade_data = one.loc[
        fill_time:trade_end
    ]

    trade_data = trade_data[
        trade_data["ticker"] == ticker
    ]

    if trade_data.empty:
        return None

    mfe = 0.0
    mae = 0.0

    outcome = "OPEN"
    exit_time = trade_data.index[-1]

    for timestamp, bar in trade_data.iterrows():

        if direction == "LONG":

            favorable = (
                bar["high"] - entry
            )

            adverse = (
                entry - bar["low"]
            )

            mfe = max(
                mfe,
                favorable
            )

            mae = max(
                mae,
                adverse
            )

            stop_hit = (
                bar["low"] <= stop
            )

            target_hit = (
                bar["high"] >= target
            )

        else:

            favorable = (
                entry - bar["low"]
            )

            adverse = (
                bar["high"] - entry
            )

            mfe = max(
                mfe,
                favorable
            )

            mae = max(
                mae,
                adverse
            )

            stop_hit = (
                bar["high"] >= stop
            )

            target_hit = (
                bar["low"] <= target
            )

        # If both occur in same 1-minute candle,
        # use conservative assumption: LOSS.

        if stop_hit and target_hit:

            outcome = "LOSS"
            exit_time = timestamp
            break

        if stop_hit:

            outcome = "LOSS"
            exit_time = timestamp
            break

        if target_hit:

            outcome = "WIN"
            exit_time = timestamp
            break

    if outcome == "OPEN":

        outcome = "TIMEOUT"

    if outcome == "WIN":
        result_r = rr

    elif outcome == "LOSS":
        result_r = -1.0

    else:
        result_r = 0.0

    return {
        "fill_time": fill_time,
        "exit_time": exit_time,
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_points": risk,
        "outcome": outcome,
        "result_r": result_r,
        "mfe_r": (
            mfe / risk
            if risk > 0
            else np.nan
        ),
        "mae_r": (
            mae / risk
            if risk > 0
            else np.nan
        ),
    }


# ============================================================
# STRATEGY COMBINATIONS
# ============================================================

combinations = list(
    product(
        ENTRY_TYPES,
        RR_VALUES,
        ABSORPTION_TYPES,
        VOLUME_FILTERS,
    )
)

print(
    "\nStrategy combinations:",
    len(combinations)
)

print(
    "Running actual trade simulations...\n"
)


# ============================================================
# TEST COMBINATIONS
# ============================================================

strategy_results = []

for combo_number, combo in enumerate(
    combinations,
    start=1
):

    (
        entry_type,
        rr,
        absorption_type,
        volume_filter,
    ) = combo

    candidates = analysis.copy()

    # --------------------------------------------------------
    # ABSORPTION FILTER
    # --------------------------------------------------------

    if absorption_type == "BASIC":

        candidates = candidates[
            candidates["absorption_basic"] == True
        ]

    elif absorption_type == "STRONG":

        candidates = candidates[
            candidates["absorption_strong"] == True
        ]

    # --------------------------------------------------------
    # VOLUME FILTER
    # --------------------------------------------------------

    if volume_filter > 0:

        candidates = candidates[
            candidates["relative_volume"]
            >= volume_filter
        ]

    trades = []

    for _, candidate in candidates.iterrows():

        trade = simulate_trade(
            candidate,
            entry_type,
            rr,
        )

        if trade is None:
            continue

        trade["session"] = candidate["session"]
        trade["direction"] = candidate["direction"]

        trades.append(trade)

    if not trades:
        continue

    trades = pd.DataFrame(trades)

    # --------------------------------------------------------
    # REMOVE OVERLAPPING SIGNALS
    #
    # Only one trade at a time.
    # --------------------------------------------------------

    trades = trades.sort_values(
        "fill_time"
    ).reset_index(drop=True)

    accepted = []

    current_exit = None

    for _, trade in trades.iterrows():

        if (
            current_exit is not None
            and trade["fill_time"]
            <= current_exit
        ):
            continue

        accepted.append(trade)

        current_exit = trade["exit_time"]

    trades = pd.DataFrame(accepted)

    if trades.empty:
        continue

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    wins = (
        trades["outcome"] == "WIN"
    ).sum()

    losses = (
        trades["outcome"] == "LOSS"
    ).sum()

    timeouts = (
        trades["outcome"] == "TIMEOUT"
    ).sum()

    resolved = wins + losses

    if resolved == 0:
        continue

    win_rate = (
        wins / resolved
    )

    net_r = (
        trades["result_r"].sum()
    )

    expectancy = (
        trades["result_r"].mean()
    )

    equity = (
        trades["result_r"].cumsum()
    )

    running_peak = (
        equity.cummax()
    )

    drawdown = (
        equity - running_peak
    )

    max_drawdown = abs(
        drawdown.min()
    )

    # Consecutive losses
    max_losing_streak = 0
    current_streak = 0

    for outcome in trades["outcome"]:

        if outcome == "LOSS":

            current_streak += 1

            max_losing_streak = max(
                max_losing_streak,
                current_streak
            )

        elif outcome == "WIN":

            current_streak = 0

    trading_days = (
        trades["fill_time"]
        .dt.date
        .nunique()
    )

    trades_per_day = (
        len(trades) / trading_days
        if trading_days > 0
        else 0
    )

    gross_win_r = (
        trades.loc[
            trades["result_r"] > 0,
            "result_r"
        ].sum()
    )

    gross_loss_r = abs(
        trades.loc[
            trades["result_r"] < 0,
            "result_r"
        ].sum()
    )

    profit_factor = (
        gross_win_r / gross_loss_r
        if gross_loss_r > 0
        else np.nan
    )

    strategy_results.append({
        "entry": entry_type,
        "rr": rr,
        "absorption": absorption_type,
        "volume_filter": volume_filter,

        "trades": len(trades),
        "trades_per_day": trades_per_day,

        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,

        "win_rate": win_rate * 100,

        "net_r": net_r,
        "expectancy_r": expectancy,
        "profit_factor": profit_factor,

        "max_drawdown_r": max_drawdown,

        "max_losing_streak": max_losing_streak,

        "avg_mfe_r": trades["mfe_r"].mean(),
        "avg_mae_r": trades["mae_r"].mean(),
    })

    if combo_number % 25 == 0:

        print(
            f"Completed "
            f"{combo_number}/{len(combinations)}"
        )


# ============================================================
# FINAL RESULTS
# ============================================================

results = pd.DataFrame(
    strategy_results
)

if results.empty:

    raise ValueError(
        "No strategies produced trades."
    )

# Prefer:
# positive expectancy
# reasonable frequency
# controlled drawdown

results["frequency_fit"] = (
    (results["trades_per_day"] >= 3)
    &
    (results["trades_per_day"] <= 8)
)

results = results.sort_values(
    [
        "frequency_fit",
        "expectancy_r",
        "profit_factor",
    ],
    ascending=[
        False,
        False,
        False,
    ]
).reset_index(drop=True)

results.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# DISPLAY
# ============================================================

print("\n===================================")
print(" FIRST STRATEGY TEST COMPLETE")
print("===================================\n")

print(
    "Strategies tested:",
    len(results)
)

print(
    "\nTOP 20 RESULTS:\n"
)

display_columns = [
    "entry",
    "rr",
    "absorption",
    "volume_filter",
    "trades",
    "trades_per_day",
    "win_rate",
    "net_r",
    "expectancy_r",
    "profit_factor",
    "max_drawdown_r",
    "max_losing_streak",
]

print(
    results[
        display_columns
    ]
    .head(20)
    .round(2)
    .to_string(index=False)
)

print(
    f"\nFull results saved: {OUTPUT}"
)

print(
    "\nNEXT: sweep filters + session analysis + "
    "Volume Profile + out-of-sample validation."
)