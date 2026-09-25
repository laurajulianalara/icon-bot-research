#!/usr/bin/env python3
"""THE ICON — Sep 21 causal candidate-finalization diagnostic.

READ-ONLY. Does not modify strategy thresholds, reports, or market data.

Purpose:
1) Trace the known 04:39 -> 04:42 SHORT replacement chain.
2) Prove exactly what is knowable at each minute.
3) Compare current live.evaluate() behavior with the benchmark survivor.
4) Inspect ALL Sep 21 supersession chains without replaying the whole month.

This is a diagnostic, not a strategy fix.
"""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import icon_option2b_shadow_live as live

DAY = pd.Timestamp("2026-09-21", tz=live.TZ)
TARGET_ENTRY = pd.Timestamp("2026-09-21 04:45:00", tz=live.TZ)
TARGET_CANDIDATE = pd.Timestamp("2026-09-21 04:42:00", tz=live.TZ)

def et(s):
    x = pd.to_datetime(s)
    return x.dt.tz_localize(live.TZ) if x.dt.tz is None else x.dt.tz_convert(live.TZ)

# Load only existing data. Nothing is written.
frames = []
h = pd.read_parquet(live.HIST)[live.NEED].copy()
h["time_ny"] = et(h.time_ny)
frames.append(h)

for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
    try:
        q = pd.read_parquet(p)
        if not set(live.NEED).issubset(q.columns):
            continue
        q = q[live.NEED].copy()
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
    (one.time_ny >= DAY - pd.Timedelta(days=4))
    & (one.time_ny < DAY + pd.Timedelta(days=1))
].copy()

print("=" * 94)
print("SEP 21 — CAUSAL CANDIDATE FINALIZATION DIAGNOSTIC")
print("=" * 94)

# ------------------------------------------------------------------
# A. Full-data reference chain (diagnostic reference only).
# ------------------------------------------------------------------
full_c = live.build_candidates(one)
sep = full_c[full_c.time_ny.dt.date == DAY.date()].copy()
sep["benchmark_signal"] = sep.time_ny + pd.Timedelta(minutes=3)

print("\nA) KNOWN 04:30–04:45 LONDON SHORT CHAIN (full-data reference)")
chain = sep[
    (sep.session == "LONDON")
    & (sep.direction == "SHORT")
    & (sep.time_ny >= pd.Timestamp("2026-09-21 04:30", tz=live.TZ))
    & (sep.time_ny <= TARGET_CANDIDATE)
]
print(chain[["time_ny","extreme","next_same_extreme_time","benchmark_signal"]].to_string(index=False))

# ------------------------------------------------------------------
# B. What current live evaluator does at each actual boundary.
# IMPORTANT: closed bars are strictly before boundary; live_open is
# the just-opened bar. No future H/L/C is supplied.
# ------------------------------------------------------------------
print("\nB) CURRENT LIVE EVALUATOR — 04:39 THROUGH 04:45")
current = []
for boundary in pd.date_range(
    pd.Timestamp("2026-09-21 04:39", tz=live.TZ),
    TARGET_ENTRY,
    freq="1min",
):
    closed = one[one.time_ny < boundary].tail(6500).copy()
    op = one[one.time_ny == boundary]
    if op.empty:
        print(boundary, "NO OPEN BAR")
        continue

    sigs = live.evaluate(closed, live_open=op.iloc[0][live.NEED].to_dict())
    near = [
        x for x in sigs
        if x["session"] == "LONDON"
        and x["direction"] == "SHORT"
        and pd.Timestamp(x["candidate_time_et"]) >= pd.Timestamp("2026-09-21 04:30", tz=live.TZ)
    ]
    emitted_now = [x for x in near if pd.Timestamp(x["entry_time_et"]) == boundary]
    for x in emitted_now:
        current.append(x)
    print(
        f"{boundary.strftime('%H:%M')} |",
        [(x["candidate_time_et"], x["entry_time_et"], round(float(x["v15_score"]), 6)) for x in emitted_now]
        or "no emission"
    )

# ------------------------------------------------------------------
# C. Causal candidate visibility.
# This does NOT decide a new strategy rule. It simply shows when each
# completed 3m candidate first becomes visible to a live process.
# A 3m candle stamped T uses T,T+1,T+2 and is first fully known at T+3.
# ------------------------------------------------------------------
print("\nC) WHEN EACH CANDIDATE FIRST BECOMES KNOWABLE")
for _, c in chain.iterrows():
    knowable = c.time_ny + pd.Timedelta(minutes=3)
    replacement = c.next_same_extreme_time
    replacement_knowable = (
        replacement + pd.Timedelta(minutes=3)
        if pd.notna(replacement) else pd.NaT
    )
    print(
        f"candidate {c.time_ny.strftime('%H:%M')} | "
        f"first knowable {knowable.strftime('%H:%M')} | "
        f"next candidate stamp {replacement.strftime('%H:%M') if pd.notna(replacement) else 'NONE'} | "
        f"next candidate fully knowable {replacement_knowable.strftime('%H:%M') if pd.notna(replacement_knowable) else 'NONE'}"
    )

# ------------------------------------------------------------------
# D. Exact benchmark target sanity check.
# ------------------------------------------------------------------
target = chain[chain.time_ny == TARGET_CANDIDATE]
print("\nD) TARGET")
if target.empty:
    print("FAIL: 04:42 benchmark candidate not found.")
else:
    r = target.iloc[0]
    print("Benchmark candidate:", r.time_ny)
    print("Expected benchmark entry:", TARGET_ENTRY)
    print("Candidate candle fully known at:", r.time_ny + pd.Timedelta(minutes=3))
    print("Later same-direction candidate:", r.next_same_extreme_time)

print("\nE) DIAGNOSTIC VERDICT")
wrong = [
    x for x in current
    if pd.Timestamp(x["candidate_time_et"]) == pd.Timestamp("2026-09-21 04:39", tz=live.TZ)
]
right = [
    x for x in current
    if pd.Timestamp(x["candidate_time_et"]) == TARGET_CANDIDATE
    and pd.Timestamp(x["entry_time_et"]) == TARGET_ENTRY
]
print("Current evaluator emitted 04:39 candidate:", "YES" if wrong else "NO")
print("Current evaluator emitted benchmark 04:42 -> 04:45:", "YES" if right else "NO")
if wrong and not right:
    print("RESULT: REPRODUCED THE FINALIZATION-TIMING BUG.")
elif right and not wrong:
    print("RESULT: CURRENT EVALUATOR MATCHES THIS BENCHMARK CHAIN.")
else:
    print("RESULT: MIXED — inspect trace above before changing any logic.")

print("\nF) ALL SEP 21 FULL-DATA SUPERSESSION CHAINS")
sup = sep[sep.next_same_extreme_time.notna()].copy()
if sup.empty:
    print("NONE")
else:
    print(
        sup[["time_ny","session","direction","extreme","next_same_extreme_time"]]
        .to_string(index=False)
    )

print("\nREAD-ONLY: no strategy thresholds, reports, or market data were changed.")
