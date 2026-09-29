#!/usr/bin/env python3
"""THE ICON — September strict-causal outcome report.

Research/reporting only. Replays the current Option 2B live evaluator causally,
applies the same 6 FINAL trades/day cap, then measures each selected trade at
1R..6R using the canonical 241-minute, stop-first outcome rule.

Selection never uses post-entry outcome data. No strategy/filter/threshold/
session/execution changes.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

TZ = live.TZ
NEED = live.NEED
RISK_DOLLARS = 300

def et(s):
    x = pd.to_datetime(s)
    return x.dt.tz_localize(TZ) if x.dt.tz is None else x.dt.tz_convert(TZ)

# Assemble exactly the same local data sources as the strict causal rerun.
frames = []
h = pd.read_parquet(live.HIST)[NEED].copy()
h["time_ny"] = et(h.time_ny)
frames.append(h)
for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q = pd.read_parquet(p)
        if not set(NEED).issubset(q.columns):
            continue
        q = q[NEED].copy()
        q["time_ny"] = et(q.time_ny)
        frames.append(q)
    except Exception:
        pass

one = (
    pd.concat(frames, ignore_index=True)
    .drop_duplicates(["time_ny", "ticker"], keep="last")
    .sort_values("time_ny")
    .reset_index(drop=True)
)
one = one[
    (one.time_ny >= pd.Timestamp("2026-08-28", tz=TZ))
    & (one.time_ny < pd.Timestamp("2026-10-01", tz=TZ))
].copy().reset_index(drop=True)

sep = one[
    (one.time_ny >= pd.Timestamp("2026-09-01", tz=TZ))
    & (one.time_ny < pd.Timestamp("2026-10-01", tz=TZ))
].copy()
boundaries = sorted(set(t for t in sep.time_ny if t.minute % 3 == 0))

# Strict causal selection.
emitted = {}
daily_cap = {}
future_violations = []
for n, t in enumerate(boundaries, 1):
    pos = one.index[one.time_ny == t]
    if len(pos) == 0:
        continue
    p = int(pos[-1])
    closed = one.loc[: p - 1, NEED].tail(6500).copy()

    # Deliberately expose ONLY fields the live evaluator needs at the just-opened
    # entry boundary. No entry-bar high/low/close/volume is supplied.
    r = one.loc[p]
    live_open = {"time_ny": r.time_ny, "ticker": r.ticker, "open": float(r.open)}

    if len(closed) and not (closed.time_ny.max() < t):
        future_violations.append((t, "closed_input_not_before_boundary", closed.time_ny.max()))

    for x in live.evaluate(closed, live_open=live_open):
        xt = pd.Timestamp(x["entry_time_et"])
        if xt != t:
            continue
        ct = pd.Timestamp(x["candidate_time_et"])
        if not (ct < xt):
            future_violations.append((t, "candidate_not_before_entry", ct))
        day = str(x["date_et"])
        if daily_cap.get(day, 0) >= 6:
            continue
        k = (xt, str(x["session"]), str(x["direction"]), ct)
        if k in emitted:
            continue
        emitted[k] = x
        daily_cap[day] = daily_cap.get(day, 0) + 1

    if n % 1000 == 0:
        print(f"Checked {n}/{len(boundaries)} causal boundaries...")

trades = pd.DataFrame(sorted(emitted.values(), key=lambda x: pd.Timestamp(x["entry_time_et"])))
if trades.empty:
    raise RuntimeError("No strict-causal September trades found.")

# Outcome measurement happens only AFTER causal selection is frozen.
rows = []
for _, t in trades.iterrows():
    entry_time = pd.Timestamp(t["entry_time_et"])
    pos = one.index[one.time_ny == entry_time]
    if len(pos) == 0:
        continue
    j = int(pos[-1])
    entry = float(t["entry"])
    stop = float(t["stop"])
    direction = str(t["direction"])
    ticker = str(one.iloc[j].ticker)
    risk = entry - stop if direction == "LONG" else stop - entry
    if not np.isfinite(risk) or risk <= 0:
        continue

    row = dict(t)
    row["risk_points"] = risk
    for rr in range(1, 7):
        target = entry + rr * risk if direction == "LONG" else entry - rr * risk
        outcome = "OPEN"
        for q in range(j, min(j + 241, len(one))):
            b = one.iloc[q]
            if str(b.ticker) != ticker:
                break
            stop_hit = float(b.low) <= stop if direction == "LONG" else float(b.high) >= stop
            target_hit = float(b.high) >= target if direction == "LONG" else float(b.low) <= target
            # Canonical conservative ordering.
            if stop_hit:
                outcome = "LOSS"
                break
            if target_hit:
                outcome = "WIN"
                break
        row[f"{rr}R"] = outcome
    rows.append(row)

out = pd.DataFrame(rows)
Path("data/reports").mkdir(parents=True, exist_ok=True)
out_path = "data/reports/2026-09_strict_causal_outcomes.csv"
out.to_csv(out_path, index=False)

print("\n" + "=" * 92)
print("THE ICON — SEPTEMBER STRICT-CAUSAL OUTCOMES")
print("=" * 92)
print("Causal FINAL trades:", len(out))
print("Future-data invariant violations:", len(future_violations))
print("Risk per trade: $300")
print("Outcome window: 241 minutes | conservative stop-first ordering")

summary = []
for rr in range(1, 7):
    s = out[f"{rr}R"]
    w = int((s == "WIN").sum())
    l = int((s == "LOSS").sum())
    o = int((s == "OPEN").sum())
    resolved = w + l
    wr = 100.0 * w / resolved if resolved else np.nan
    pnl = w * rr * RISK_DOLLARS - l * RISK_DOLLARS

    # Sequential realized-R equity on resolved trades; OPEN contributes 0.
    vals = np.where(s == "WIN", rr, np.where(s == "LOSS", -1, 0)).astype(float)
    eq = np.cumsum(vals)
    peaks = np.maximum.accumulate(np.r_[0.0, eq])
    dd = peaks[1:] - eq
    max_dd_r = float(dd.max()) if len(dd) else 0.0

    # Max consecutive losses.
    max_losing_streak = cur = 0
    for v in s:
        if v == "LOSS":
            cur += 1
            max_losing_streak = max(max_losing_streak, cur)
        elif v == "WIN":
            cur = 0

    summary.append({
        "RR": f"1:{rr}",
        "Wins": w,
        "Losses": l,
        "Open": o,
        "WR": wr,
        "PnL": pnl,
        "MaxDD$": max_dd_r * RISK_DOLLARS,
        "MaxLossStreak": max_losing_streak,
    })

sm = pd.DataFrame(summary)
print("\n" + sm.round({"WR": 2, "MaxDD$": 0}).to_string(index=False))
print("\nSaved:", out_path)
print("\nREAD-ONLY RESEARCH TEST. No strategy/filter/threshold/session/execution changes were made.")
