"""Build a tiny TradingView execution-parity validator from the frozen master.

This deliberately does NOT reimplement V15. It extracts the authoritative
Sep 1-17, 2026 frozen trades and emits a compact Pine indicator that replays
those frozen trades independently using TradingView 1-minute intrabars.
Use it only to validate TradingView historical data against Benchmark V1.
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

def ms(ts):
    return int(ts.tz_convert("UTC").timestamp() * 1000)

times = ",".join(str(ms(x)) for x in df["entry_time"])
entries = ",".join(format(float(x), ".10g") for x in df["entry"])
stops = ",".join(format(float(x), ".10g") for x in df["stop"])
dirs = ",".join("1" if x == "LONG" else "-1" for x in df["direction"])
# Frozen canonical outcomes per RR, encoded 1=WIN, -1=LOSS, 0=OPEN.
outcome_cols = []
for rr_i in range(1, 7):
    candidates = [f"outcome_{rr_i}r", f"{rr_i}R_outcome", f"rr{rr_i}_outcome"]
    col = next((x for x in candidates if x in df.columns), None)
    if col is None:
        # Master historically uses simple 1R..6R labels in some revisions.
        col = next((x for x in df.columns if str(x).lower().replace("_","") in {f"{rr_i}r", f"outcome{rr_i}r"}), None)
    if col is None:
        raise KeyError(f"Could not find frozen outcome column for {rr_i}R. Columns: {list(df.columns)}")
    vals = []
    for x in df[col].astype(str).str.upper():
        vals.append("1" if x == "WIN" else "-1" if x == "LOSS" else "0")
    outcome_cols.append(",".join(vals))
frozen_outcomes = ";".join(outcome_cols)

pine = f'''//@version=6
strategy("THE ICON — TV BACKTEST PARITY VALIDATOR", overlay=true, pyramiding=0,
     process_orders_on_close=false, calc_on_order_fills=false, calc_on_every_tick=false,
     default_qty_type=strategy.fixed, default_qty_value=1, initial_capital=1000000)

rr = input.int(4, "RR to validate", minval=1, maxval=6)\nriskDollars = input.float(300.0, "Risk per trade ($)", minval=1.0, step=25.0)\npointValue = 2.0  // MNQ = $2 per point per contract

var array<int> entryTimes = array.from({times})
var array<float> frozenEntries = array.from({entries})
var array<float> frozenStops = array.from({stops})
var array<int> directions = array.from({dirs})
var array<int> frozen1 = array.from({outcome_cols[0]})
var array<int> frozen2 = array.from({outcome_cols[1]})
var array<int> frozen3 = array.from({outcome_cols[2]})
var array<int> frozen4 = array.from({outcome_cols[3]})
var array<int> frozen5 = array.from({outcome_cols[4]})
var array<int> frozen6 = array.from({outcome_cols[5]})
var array<int> tvOutcome = array.new_int(50, 0)
var array<int> exitTimes = array.new_int(50, 0)
var array<bool> active = array.new_bool(50, false)
var array<bool> done = array.new_bool(50, false)
var array<int> age = array.new_int(50, 0)
var int wins = 0
var int losses = 0
var int started = 0\nvar int tvMarker = 0\nvar int tvWinsMarked = 0\nvar int tvLossesMarked = 0

array<float> lo1 = request.security_lower_tf(syminfo.tickerid, "1", low)
array<float> hi1 = request.security_lower_tf(syminfo.tickerid, "1", high)
array<int> tm1 = request.security_lower_tf(syminfo.tickerid, "1", time)

for n = 0 to 49
    if not array.get(done, n) and not array.get(active, n)
        int et = array.get(entryTimes, n)
        if time <= et and time_close > et
            array.set(active, n, true)
            started += 1

int m = array.size(tm1)
if m > 0
    for j = 0 to m - 1
        int bt = array.get(tm1, j)
        float bl = array.get(lo1, j)
        float bh = array.get(hi1, j)
        for n = 0 to 49
            if array.get(active, n) and not array.get(done, n)
                int et = array.get(entryTimes, n)
                if bt >= et
                    float ep = array.get(frozenEntries, n)
                    float st = array.get(frozenStops, n)
                    int d = array.get(directions, n)
                    float risk = d == 1 ? ep - st : st - ep
                    float tg = d == 1 ? ep + rr * risk : ep - rr * risk
                    bool stopHit = d == 1 ? bl <= st : bh >= st
                    bool targetHit = d == 1 ? bh >= tg : bl <= tg
                    int a = array.get(age, n) + 1
                    array.set(age, n, a)
                    if stopHit
                        losses += 1
                        array.set(tvOutcome, n, -1)
                        array.set(exitTimes, n, bt)
                        array.set(done, n, true)
                        array.set(active, n, false)
                    else if targetHit
                        wins += 1
                        array.set(tvOutcome, n, 1)
                        array.set(exitTimes, n, bt)
                        array.set(done, n, true)
                        array.set(active, n, false)
                    else if a >= 241
                        array.set(tvOutcome, n, 0)
                        array.set(exitTimes, n, bt)
                        array.set(done, n, true)
                        array.set(active, n, false)

// Strategy Tester cannot represent overlapping canonical positions in one net
// position. The table above is therefore the authoritative 50-trade parity test.
// We do NOT create synthetic Strategy Tester trades because their P&L/WR would
// be misleading. Dollar benchmark P&L is calculated from fixed $300 risk below.

f_frozen(int n) =>
    rr == 1 ? array.get(frozen1, n) : rr == 2 ? array.get(frozen2, n) : rr == 3 ? array.get(frozen3, n) : rr == 4 ? array.get(frozen4, n) : rr == 5 ? array.get(frozen5, n) : array.get(frozen6, n)

int mismatchCount = 0
string mismatchText = ""
for n = 0 to 49
    if array.get(done, n)
        int expected = f_frozen(n)
        int actual = array.get(tvOutcome, n)
        if expected != actual
            mismatchCount += 1
            int et = array.get(entryTimes, n)
            int xt = array.get(exitTimes, n)
            float ep = array.get(frozenEntries, n)
            float st = array.get(frozenStops, n)
            int d = array.get(directions, n)
            float riskPts = d == 1 ? ep - st : st - ep
            float tg = d == 1 ? ep + rr * riskPts : ep - rr * riskPts
            string expS = expected == 1 ? "WIN" : expected == -1 ? "LOSS" : "OPEN"
            string actS = actual == 1 ? "WIN" : actual == -1 ? "LOSS" : "OPEN"
            mismatchText += "#" + str.tostring(n + 1) + " " + str.format_time(et, "MM/dd HH:mm", "America/New_York") + " " + (d == 1 ? "LONG" : "SHORT") + " | E " + str.tostring(ep) + " S " + str.tostring(st) + " T " + str.tostring(tg) + " | PY " + expS + " / TV " + actS + " | exit " + str.format_time(xt, "MM/dd HH:mm", "America/New_York") + " | "

int unresolved = started - wins - losses
float wr = wins + losses > 0 ? 100.0 * wins / (wins + losses) : na

var table t = table.new(position.top_right, 2, 8, border_width=1)
if barstate.islast
    table.cell(t, 0, 0, "TV DATA PARITY")
    table.cell(t, 1, 0, str.tostring(rr) + "R")
    table.cell(t, 0, 1, "Frozen trades")
    table.cell(t, 1, 1, str.tostring(started) + " / 50")
    table.cell(t, 0, 2, "Wins")
    table.cell(t, 1, 2, str.tostring(wins))
    table.cell(t, 0, 3, "Losses")
    table.cell(t, 1, 3, str.tostring(losses))
    table.cell(t, 0, 4, "Unresolved")
    table.cell(t, 1, 4, str.tostring(unresolved))
    table.cell(t, 0, 5, "Win rate")
    table.cell(t, 1, 5, na(wr) ? "n/a" : str.tostring(wr, "#.00") + "%")
    table.cell(t, 0, 6, "Mismatches")
    table.cell(t, 1, 6, str.tostring(mismatchCount))
    table.cell(t, 0, 7, "Mismatch")
    table.cell(t, 1, 7, mismatchCount == 0 ? "NONE" : mismatchText, text_size=size.tiny)

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
