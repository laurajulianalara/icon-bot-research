"""Build a tiny TradingView execution-parity validator from the frozen master.

This deliberately does NOT reimplement V15. It extracts the authoritative
Sep 1-17, 2026 frozen trades and emits a Pine strategy that submits those
known entries/stops on the 3-minute chart. Use it only to validate
TradingView's broker-emulator execution against Benchmark V1.
"""
from pathlib import Path
import pandas as pd

SRC = Path("data/ICON_MASTER_1911_TRADE_LEVEL.csv")
OUT = Path("src/icon_tv_execution_validator.pine")
TZ = "America/New_York"
START = pd.Timestamp("2026-09-01 00:00:00", tz=TZ)
END = pd.Timestamp("2026-09-18 00:00:00", tz=TZ)

df = pd.read_csv(SRC)
df["candidate_time"] = pd.to_datetime(df["candidate_time"], utc=True).dt.tz_convert(TZ)
df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True).dt.tz_convert(TZ)
df = df[(df.candidate_time >= START) & (df.candidate_time < END)].copy()
df = df.sort_values(["entry_time", "direction"]).reset_index(drop=True)

assert len(df) == 50, f"Expected 50 frozen trades, found {len(df)}"

# Entry timestamps are encoded as Unix milliseconds. We submit on the candidate
# bar close so process_orders_on_close=false fills the market order on the next
# 3m open, matching the canonical T+3 entry.
def ms(ts):
    return int(ts.tz_convert("UTC").timestamp() * 1000)

times = ",".join(str(ms(x)) for x in df["entry_time"])
stops = ",".join(format(float(x), ".10g") for x in df["stop"])
dirs = ",".join("1" if x == "LONG" else "-1" for x in df["direction"])

pine = f'''//@version=6
strategy("THE ICON — TV EXECUTION PARITY VALIDATOR", overlay=true, pyramiding=0,
     process_orders_on_close=false, calc_on_order_fills=true, calc_on_every_tick=false,
     use_bar_magnifier=true, default_qty_type=strategy.fixed, default_qty_value=1,
     initial_capital=1000000, margin_long=1, margin_short=1)

rr = input.int(4, "RR to validate", minval=1, maxval=6)
showMarks = input.bool(true, "Show frozen entry markers")

var array<int> entryTimes = array.from({times})
var array<float> frozenStops = array.from({stops})
var array<int> directions = array.from({dirs})
var int nextTrade = 0
var float activeStop = na
var float activeTarget = na
var int expectedTrades = array.size(entryTimes)

// On a 3m chart, time_close equals the next bar's opening timestamp.
// Submit one bar before the frozen entry so the market order fills at that open.
bool due = nextTrade < expectedTrades and time_close == array.get(entryTimes, nextTrade)

if due and strategy.position_size == 0
    int d = array.get(directions, nextTrade)
    activeStop := array.get(frozenStops, nextTrade)
    if d == 1
        strategy.entry("V Long", strategy.long)
    else
        strategy.entry("V Short", strategy.short)
    nextTrade += 1

// Recalculate target from TradingView's actual fill, exactly as deployment must.
if strategy.position_size != 0
    bool isLong = strategy.position_size > 0
    float ep = strategy.position_avg_price
    float risk = isLong ? ep - activeStop : activeStop - ep
    activeTarget := isLong ? ep + rr * risk : ep - rr * risk
    if risk > 0
        if isLong
            strategy.exit("V Long Exit", "V Long", stop=activeStop, limit=activeTarget)
        else
            strategy.exit("V Short Exit", "V Short", stop=activeStop, limit=activeTarget)

if strategy.position_size == 0 and strategy.position_size[1] != 0
    activeStop := na
    activeTarget := na

plotshape(showMarks and due, title="Frozen Signal", style=shape.circle,
     location=location.abovebar, size=size.tiny, text="F")

if barstate.islast and timeframe.in_seconds() != 180
    runtime.error("Run this validator on the 3-minute MNQ continuous chart.")
'''

OUT.write_text(pine)
print("CREATED", OUT)
print("FROZEN TRADES:", len(df))
print("FIRST:", df.entry_time.iloc[0])
print("LAST: ", df.entry_time.iloc[-1])
print("SIZE:", OUT.stat().st_size, "bytes")
print("\nExpected frozen September results:")
print("1R: 47W / 3L  = 94%")
print("2R: 44W / 6L  = 88%")
print("3R: 39W / 11L = 78%")
print("4R: 34W / 16L = 68%")
print("5R: 30W / 20L = 60%")
print("6R: 27W / 23L = 54%")
print("\nNext: paste src/icon_tv_execution_validator.pine into TradingView on MNQ 3m.")
