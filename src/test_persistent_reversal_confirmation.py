#!/usr/bin/env python3
"""
THE ICON — PERSISTENT REVERSAL CONFIRMATION CAUSAL TEST

Purpose:
- Replay today's data sequentially (fast; no waiting for live bars).
- Build causal session extremes.
- Apply the EXISTING frozen V7/V8/V15/V27 filters unchanged.
- If a qualified extreme passes, KEEP IT ACTIVE.
- Give each of the next 1..5 completed 3m candles a chance to validate reversal.
- LONG confirms when a later 3m CLOSE > original extreme candle body_top.
- SHORT confirms when a later 3m CLOSE < original extreme candle body_bottom.
- Entry = following 3m open after confirmation.
- Stop = original qualified extreme +/- 0.25.
- Report 1R..6R outcomes.

No historical candidate list. No next_same_extreme_time. No future supersession.
Future bars are used for outcome scoring only AFTER a causal trade entry exists.
"""
import os, sys
import numpy as np
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

# Reuse the exact frozen filter implementation from the live runner.
from icon_true_live_bar_by_bar import (
    TZ, ET, SYMBOL, bootstrap, make3, frozen_filter, session_name
)

MAX_CONFIRM_BARS = 5
R_LEVELS = range(1, 7)

def fmt(t):
    return pd.Timestamp(t).strftime("%H:%M")

def outcome(th, entry_i, direction, entry, stop):
    risk = entry-stop if direction=="LONG" else stop-entry
    if risk <= 0:
        return risk, {r:"INVALID" for r in R_LEVELS}

    out = {}
    for rr in R_LEVELS:
        target = entry + rr*risk if direction=="LONG" else entry - rr*risk
        status = "OPEN"
        for j in range(entry_i, len(th)):
            b = th.iloc[j]
            hit_stop = float(b.low) <= stop if direction=="LONG" else float(b.high) >= stop
            hit_target = float(b.high) >= target if direction=="LONG" else float(b.low) <= target
            if hit_stop and hit_target:
                status = "AMBIG"
                break
            if hit_stop:
                status = "LOSS"
                break
            if hit_target:
                status = "WIN"
                break
        out[rr] = status
    return risk, out

def main():
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        sys.exit("MASSIVE_API_KEY is not set.")

    one = bootstrap(key)
    one = one.sort_values("time_ny").reset_index(drop=True)
    today = datetime.now(ET).date()

    th_all = make3(one)
    th = th_all[th_all.time_ny.dt.date == today].copy().reset_index(drop=True)
    if th.empty:
        sys.exit("No completed 3m bars found for today.")

    # We replay only today's bars, but ATR/filter calculations retain prior history.
    running = {}
    active = []
    qualified = []
    confirmed = []

    for i, r in th.iterrows():
        t = r.time_ny
        s = r.session

        # 1) Existing active qualified extremes get another completed 3m chance.
        still = []
        for p in active:
            if t <= p["time_ny"]:
                still.append(p)
                continue
            bars_waited = int((t - p["time_ny"]).total_seconds() // 180)
            if bars_waited < 1:
                still.append(p)
                continue
            if bars_waited > MAX_CONFIRM_BARS:
                p["status"] = "EXPIRED"
                continue

            ok = (float(r.close) > p["body_top"]) if p["direction"]=="LONG" else (float(r.close) < p["body_bottom"])
            if ok:
                entry_i = i + 1
                if entry_i < len(th):
                    er = th.iloc[entry_i]
                    # Entry must be the immediately following 3m bar and same session.
                    if er.time_ny == t + pd.Timedelta(minutes=3) and er.session == p["session"]:
                        entry = float(er.open)
                        stop = p["extreme"]-.25 if p["direction"]=="LONG" else p["extreme"]+.25
                        risk, outs = outcome(th, entry_i, p["direction"], entry, stop)
                        confirmed.append({
                            **p, "confirm_time":t, "bars_waited":bars_waited,
                            "entry_time":er.time_ny, "entry":entry, "stop":stop,
                            "risk":risk, "outcomes":outs
                        })
                        p["status"] = "CONFIRMED"
                    else:
                        p["status"] = "NO_ENTRY_BAR"
                else:
                    p["status"] = "CONFIRMED_NO_FUTURE_OPEN"
            else:
                still.append(p)
        active = still

        if s is None:
            continue

        # 2) Causal session-extreme discovery.
        key2 = (t.date(), s)
        h, l = float(r.high), float(r.low)
        rng = h-l
        if key2 not in running:
            running[key2] = [h, l]
            continue

        rh, rl = running[key2]
        cs = []
        if l < rl:
            cs.append({
                "time_ny":t, "session":s, "direction":"LONG", "extreme":l,
                "atr":float(r.atr_20), "sweep_distance":rl-l,
                "wick_percent":float(r.lower_wick/rng) if rng>0 else 0,
                "body_top":max(float(r.open),float(r.close)),
                "body_bottom":min(float(r.open),float(r.close))
            })
        if h > rh:
            cs.append({
                "time_ny":t, "session":s, "direction":"SHORT", "extreme":h,
                "atr":float(r.atr_20), "sweep_distance":h-rh,
                "wick_percent":float(r.upper_wick/rng) if rng>0 else 0,
                "body_top":max(float(r.open),float(r.close)),
                "body_bottom":min(float(r.open),float(r.close))
            })
        running[key2] = [max(rh,h), min(rl,l)]

        for c in cs:
            # frozen_filter only reads candidate's constituent 1m bars i,i+1,i+2.
            ok, stage, sc = frozen_filter(one, c)
            if ok:
                p = {**c, "v15_score":sc, "status":"ACTIVE"}
                qualified.append(p)
                active.append(p)

    print("="*88)
    print("THE ICON — PERSISTENT REVERSAL CONFIRMATION TEST")
    print("="*88)
    print(f"Date: {today} | Symbol: {SYMBOL}")
    print(f"Confirmation window tested: next 1-{MAX_CONFIRM_BARS} completed 3m candles")
    print("Frozen V7/V8/V15/V27: UNCHANGED")
    print("Future supersession: DISABLED")
    print()

    print(f"QUALIFIED EXTREMES: {len(qualified)}")
    for p in qualified:
        matches = [x for x in confirmed if x["time_ny"]==p["time_ny"] and x["direction"]==p["direction"] and x["session"]==p["session"]]
        if matches:
            x=matches[0]
            print(f"  {p['session']} {p['direction']} {fmt(p['time_ny'])} | V15 {p['v15_score']:.6f} | CONFIRMED {fmt(x['confirm_time'])} after {x['bars_waited']} bar(s)")
        else:
            print(f"  {p['session']} {p['direction']} {fmt(p['time_ny'])} | V15 {p['v15_score']:.6f} | NO CONFIRM within {MAX_CONFIRM_BARS} bars")

    print()
    print(f"TRADES: {len(confirmed)}")
    for x in confirmed:
        rr = " | ".join(f"{r}R {x['outcomes'][r]}" for r in R_LEVELS)
        print("-"*88)
        print(f"{x['session']} {x['direction']} | candidate {fmt(x['time_ny'])} -> confirm {fmt(x['confirm_time'])} ({x['bars_waited']} bars) -> entry {fmt(x['entry_time'])}")
        print(f"Entry {x['entry']:.2f} | Stop {x['stop']:.2f} | Risk {x['risk']:.2f} | V15 {x['v15_score']:.6f}")
        print(rr)

    print()
    print("WINDOW COMPARISON")
    for w in range(1, MAX_CONFIRM_BARS+1):
        xs=[x for x in confirmed if x["bars_waited"]<=w]
        print(f"  max {w} bar(s): {len(xs)} trade(s)")

if __name__=="__main__":
    main()
