import pandas as pd
import numpy as np
from itertools import product

DATA_1M = "data/mnq_continuous_1m.parquet"
DATA_3M = "data/mnq_continuous_3m.parquet"
CANDIDATES = "data/reversal_candidates.parquet"
OUTPUT = "data/strategy_results_v2.csv"
TRADES_OUTPUT = "data/v2_trade_cache.parquet"

# V2: recent market gets priority
LOOKBACK_DAYS = 365
ENTRY_TYPES = ["CISD", "FIB_618", "FIB_705", "FIB_786"]
RR_VALUES = [2.5, 3.0, 4.0]
CISD_TYPES = ["EXTREME_OPEN", "LAST_OPPOSING"]
MAX_CISD_VALUES = [3, 5, 8]
VOLUME_FILTERS = [0.0, 1.2, 1.5, 2.0]
WICK_FILTERS = [0.0, 0.30, 0.40]
SWEEP_ATR_FILTERS = [0.0, 0.05, 0.15]
STOP_BUFFERS = [0.25, 0.50]
MAX_ENTRY_WAIT_MIN = 30
MAX_TRADE_HOURS = 4

print("\nLoading V2 research data...")
one = pd.read_parquet(DATA_1M)
three = pd.read_parquet(DATA_3M)
candidates = pd.read_parquet(CANDIDATES)

for x in (one, three, candidates):
    x["time_ny"] = pd.to_datetime(x["time_ny"])

one = one.sort_values("time_ny").reset_index(drop=True)
three = three.sort_values("time_ny").reset_index(drop=True)
candidates = candidates.sort_values("time_ny").reset_index(drop=True)

end_date = three["time_ny"].max()
start_date = end_date - pd.Timedelta(days=LOOKBACK_DAYS)
one = one[one["time_ny"] >= start_date].copy()
three = three[three["time_ny"] >= start_date].copy()
candidates = candidates[candidates["time_ny"] >= start_date].copy()

print("Primary period:", start_date, "to", end_date)
print("Candidates:", f"{len(candidates):,}")

# Map 3M timestamps and next same-direction candidate inside each session.
three = three.reset_index(drop=True)
time_to_idx = pd.Series(three.index, index=three["time_ny"]).to_dict()
candidates["next_same_extreme_time"] = candidates.groupby(
    ["session_id", "direction"]
)["time_ny"].shift(-1)

def find_cisd(c, cisd_type, max_bars):
    t = c["time_ny"]
    if t not in time_to_idx:
        return None
    idx = time_to_idx[t]
    direction = c["direction"]
    ticker = c["ticker"]
    next_extreme = c["next_same_extreme_time"]
    reference = c["open"]

    for j in range(idx + 1, min(idx + max_bars + 1, len(three))):
        r = three.iloc[j]
        if r["ticker"] != ticker:
            return None

        # Critical V2 fix: old candidate dies when a newer same-direction
        # session extreme forms before confirmation.
        if pd.notna(next_extreme) and r["time_ny"] >= next_extreme:
            return None

        if cisd_type == "LAST_OPPOSING":
            if direction == "LONG" and r["close"] < r["open"]:
                reference = r["open"]
            elif direction == "SHORT" and r["close"] > r["open"]:
                reference = r["open"]

        confirmed = (
            (direction == "LONG" and r["close"] > reference)
            or
            (direction == "SHORT" and r["close"] < reference)
        )
        if confirmed:
            leg = three.iloc[idx:j + 1]
            if direction == "LONG":
                leg_end = leg["high"].max()
                size = leg_end - c["extreme"]
                fibs = {k: leg_end - size * k for k in (0.618, 0.705, 0.786)}
            else:
                leg_end = leg["low"].min()
                size = c["extreme"] - leg_end
                fibs = {k: leg_end + size * k for k in (0.618, 0.705, 0.786)}
            if size <= 0:
                return None
            return {
                "cisd_time": r["time_ny"],
                "cisd_reference": reference,
                "fib_618": fibs[0.618],
                "fib_705": fibs[0.705],
                "fib_786": fibs[0.786],
                "cisd_bars": j - idx,
            }
    return None

one_idx = one.set_index("time_ny")

def simulate(c, conf, entry_type, rr, stop_buffer):
    direction, ticker = c["direction"], c["ticker"]
    ct = conf["cisd_time"]
    stop = c["extreme"] - stop_buffer if direction == "LONG" else c["extreme"] + stop_buffer

    deadline = ct + pd.Timedelta(minutes=MAX_ENTRY_WAIT_MIN)
    window = one_idx.loc[ct:deadline]
    window = window[window["ticker"] == ticker]
    if window.empty:
        return None

    if entry_type == "CISD":
        f = window[window.index > ct]
        if f.empty:
            return None
        fill_time = f.index[0]
        entry = float(f.iloc[0]["open"])
    else:
        key = {"FIB_618":"fib_618","FIB_705":"fib_705","FIB_786":"fib_786"}[entry_type]
        entry = conf[key]
        fill_time = None
        for ts, bar in window.iterrows():
            if ts <= ct:
                continue
            if bar["low"] <= entry <= bar["high"]:
                fill_time = ts
                break
        if fill_time is None:
            return None

    risk = entry - stop if direction == "LONG" else stop - entry
    if risk <= 0:
        return None
    target = entry + risk * rr if direction == "LONG" else entry - risk * rr

    td = one_idx.loc[fill_time:fill_time + pd.Timedelta(hours=MAX_TRADE_HOURS)]
    td = td[td["ticker"] == ticker]
    if td.empty:
        return None

    outcome, exit_time, mfe, mae = "TIMEOUT", td.index[-1], 0.0, 0.0
    for ts, bar in td.iterrows():
        if direction == "LONG":
            favorable, adverse = bar["high"] - entry, entry - bar["low"]
            sh, th = bar["low"] <= stop, bar["high"] >= target
        else:
            favorable, adverse = entry - bar["low"], bar["high"] - entry
            sh, th = bar["high"] >= stop, bar["low"] <= target
        mfe, mae = max(mfe, favorable), max(mae, adverse)
        # Conservative handling of ambiguous 1M bars.
        if sh:
            outcome, exit_time = "LOSS", ts
            break
        if th:
            outcome, exit_time = "WIN", ts
            break

    result_r = rr if outcome == "WIN" else (-1.0 if outcome == "LOSS" else 0.0)
    return {
        "fill_time": fill_time, "exit_time": exit_time, "outcome": outcome,
        "result_r": result_r, "mfe_r": mfe / risk, "mae_r": mae / risk
    }

# Build trade cache once; filters are applied later.
print("\nBuilding V2 trade cache...")
cache = []
total = len(candidates)
for n, (_, c) in enumerate(candidates.iterrows(), 1):
    if n % 1000 == 0:
        print(f"Candidate {n:,}/{total:,}")
    sweep_atr = (c["sweep_distance"] / c["atr"]) if pd.notna(c["atr"]) and c["atr"] > 0 else 0.0

    for cisd_type in CISD_TYPES:
        for max_bars in MAX_CISD_VALUES:
            conf = find_cisd(c, cisd_type, max_bars)
            if conf is None:
                continue
            for entry_type, rr, stop_buffer in product(ENTRY_TYPES, RR_VALUES, STOP_BUFFERS):
                tr = simulate(c, conf, entry_type, rr, stop_buffer)
                if tr is None:
                    continue
                cache.append({
                    **tr,
                    "candidate_time": c["time_ny"], "session": c["session"],
                    "direction": c["direction"], "relative_volume": c["relative_volume"],
                    "wick_percent": c["wick_percent"], "sweep_atr": sweep_atr,
                    "cisd_type": cisd_type, "max_cisd_bars": max_bars,
                    "entry": entry_type, "rr": rr, "stop_buffer": stop_buffer,
                })

cache = pd.DataFrame(cache)
cache.to_parquet(TRADES_OUTPUT, index=False)
print("Cached trades:", f"{len(cache):,}")

# 2*3*4*3*4*3*3*2 = 5,184 controlled variations.
combos = list(product(
    CISD_TYPES, MAX_CISD_VALUES, ENTRY_TYPES, RR_VALUES,
    VOLUME_FILTERS, WICK_FILTERS, SWEEP_ATR_FILTERS, STOP_BUFFERS
))
print("Strategy variations:", f"{len(combos):,}")

eligible_days = max(1, three["time_ny"].dt.date.nunique())
results = []

for num, combo in enumerate(combos, 1):
    cisd_type, max_bars, entry, rr, vol, wick, sweep, stop_buffer = combo
    t = cache[
        (cache["cisd_type"] == cisd_type) &
        (cache["max_cisd_bars"] == max_bars) &
        (cache["entry"] == entry) &
        (cache["rr"] == rr) &
        (cache["stop_buffer"] == stop_buffer) &
        (cache["relative_volume"] >= vol) &
        (cache["wick_percent"] >= wick) &
        (cache["sweep_atr"] >= sweep)
    ].copy()
    if t.empty:
        continue

    # One live trade at a time.
    t = t.sort_values("fill_time")
    accepted, current_exit = [], None
    for _, tr in t.iterrows():
        if current_exit is not None and tr["fill_time"] <= current_exit:
            continue
        accepted.append(tr)
        current_exit = tr["exit_time"]
    if not accepted:
        continue
    t = pd.DataFrame(accepted)

    wins = int((t["outcome"] == "WIN").sum())
    losses = int((t["outcome"] == "LOSS").sum())
    resolved = wins + losses
    if resolved == 0:
        continue

    eq = t["result_r"].cumsum()
    dd = eq - eq.cummax()
    loss_streak = cur = 0
    for o in t["outcome"]:
        if o == "LOSS":
            cur += 1
            loss_streak = max(loss_streak, cur)
        elif o == "WIN":
            cur = 0

    gross_win = t.loc[t["result_r"] > 0, "result_r"].sum()
    gross_loss = abs(t.loc[t["result_r"] < 0, "result_r"].sum())
    tpd = len(t) / eligible_days

    results.append({
        "cisd_type": cisd_type, "max_cisd_bars": max_bars,
        "entry": entry, "rr": rr, "volume_filter": vol,
        "wick_filter": wick, "sweep_atr_filter": sweep,
        "stop_buffer": stop_buffer, "trades": len(t),
        "trades_per_day": tpd, "win_rate": wins / resolved * 100,
        "net_r": t["result_r"].sum(), "expectancy_r": t["result_r"].mean(),
        "profit_factor": gross_win / gross_loss if gross_loss else np.nan,
        "max_drawdown_r": abs(dd.min()), "max_losing_streak": loss_streak,
        "avg_mfe_r": t["mfe_r"].mean(), "avg_mae_r": t["mae_r"].mean(),
        "sweet_spot_4_6": 4 <= tpd <= 6,
        "acceptable_3_8": 3 <= tpd <= 8,
    })
    if num % 500 == 0:
        print(f"Scored {num:,}/{len(combos):,}")

results = pd.DataFrame(results)
results = results.sort_values(
    ["sweet_spot_4_6", "acceptable_3_8", "expectancy_r", "profit_factor"],
    ascending=[False, False, False, False]
).reset_index(drop=True)
results.to_csv(OUTPUT, index=False)

print("\n===================================")
print(" V2 SCAN COMPLETE")
print("===================================")
print("Variations tested:", f"{len(combos):,}")
print("Results produced:", f"{len(results):,}")
print("Period:", start_date, "to", end_date)
print("\nTOP 20:")
cols = ["cisd_type","max_cisd_bars","entry","rr","volume_filter","wick_filter",
        "sweep_atr_filter","stop_buffer","trades","trades_per_day","win_rate",
        "expectancy_r","profit_factor","max_drawdown_r","max_losing_streak"]
print(results[cols].head(20).round(2).to_string(index=False))
print("\nSaved:", OUTPUT)
print("Trade cache:", TRADES_OUTPUT)
print("\nNEXT: validation + session breakdown + Volume Profile on finalists.")
