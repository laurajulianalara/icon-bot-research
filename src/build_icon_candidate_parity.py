"""Build stage-by-stage TradingView divergence diagnostic for frozen Option 2A.

Starts from the working selection-parity diagnostic and adds stage counters.
For each stage it reports:
  1) total Pine events reaching that stage
  2) how many of the authoritative frozen 50 are still present

This does not change any selection rule or authorize trades.
"""
from pathlib import Path
import subprocess
import pandas as pd

BASE = Path("src/icon_selection_parity.pine")
OUT = Path("src/icon_candidate_parity.pine")

subprocess.run(["python", "src/build_icon_selection_parity.py"], check=True)
pine = BASE.read_text()

# Authoritative Python candidate answer key. This is audit-only and never
# authorizes a Pine candidate/trade.
cand = pd.read_parquet("data/reversal_candidates.parquet").copy()
time_col = "candidate_time" if "candidate_time" in cand.columns else "time_ny"
cand[time_col] = pd.to_datetime(cand[time_col], utc=True).dt.tz_convert("America/New_York")
start = pd.Timestamp("2026-09-01 00:00:00", tz="America/New_York")
end = pd.Timestamp("2026-09-18 00:00:00", tz="America/New_York")
cand = cand[(cand[time_col] >= start) & (cand[time_col] < end)].copy()
cand = cand.sort_values([time_col, "direction"]).reset_index(drop=True)
assert len(cand) == 686, f"Expected 686 Python candidates, found {len(cand)}"
def ms(ts):
    return int(ts.tz_convert("UTC").timestamp() * 1000)
candidate_times = ",".join(str(ms(x)) for x in cand[time_col])
candidate_dirs = ",".join("1" if str(x).upper() == "LONG" else "-1" for x in cand["direction"])


# Global arrays are intentionally used here because Pine functions may mutate
# array contents without illegally reassigning global scalar variables.
needle = "// Frozen thresholds\n"
defs = f"""// DIVERGENCE DIAGNOSTIC
// diagTotal / diagFrozen use indexes:
// 0 Candidate, 1 V7, 2 V8, 3 V15, 4 6/day, 5 V27.
var array<int> diagTotal = array.new_int(6, 0)
var array<int> diagFrozen = array.new_int(6, 0)
var array<int> diagV15Times = array.new_int()
var array<int> diagV15Dirs = array.new_int()
var array<int> diagV15DayNums = array.new_int()
var array<bool> diagV15Frozen = array.new_bool()
var array<float> diagV15Scores = array.new_float()
var array<int> pyCandTimes = array.from({candidate_times})
var array<int> pyCandDirs = array.from({candidate_dirs})
var array<bool> pyCandMatched = array.new_bool(686, false)
var array<int> extraCandTimes = array.new_int()
var array<int> extraCandDirs = array.new_int()
var array<int> extraByDay = array.new_int(17, 0)

f_audit_day_index(int t) =>
    int d = dayofmonth(t, "America/New_York")
    d >= 1 and d <= 17 ? d - 1 : -1

f_candidate_audit(int t, int d) =>
    int found = -1
    for jj = 0 to 685
        if array.get(pyCandTimes, jj) == t and array.get(pyCandDirs, jj) == d
            found := jj
            break
    if found >= 0
        array.set(pyCandMatched, found, true)
    else
        int di = f_audit_day_index(t)
        if di >= 0
            array.set(extraByDay, di, array.get(extraByDay, di) + 1)
        if array.size(extraCandTimes) < 12
            array.push(extraCandTimes, t)
            array.push(extraCandDirs, d)


f_diag_is_frozen(int t, int d) =>
    bool found = false
    for ii = 0 to 49
        if array.get(auditTimes, ii) == t and array.get(auditDirs, ii) == d
            found := true
            break
    found

f_diag_hit(int stage, int t, int d) =>
    array.set(diagTotal, stage, array.get(diagTotal, stage) + 1)
    if f_diag_is_frozen(t, d)
        array.set(diagFrozen, stage, array.get(diagFrozen, stage) + 1)

"""
if needle not in pine:
    raise SystemExit("Could not find diagnostic insertion point")
pine = pine.replace(needle, defs + needle, 1)

old = """                if exists
                    float sg = isLong ? 1.0 : -1.0
"""
new = """                if exists
                    int diagD = isLong ? 1 : -1
                    if time >= AUDIT_START and time < AUDIT_END
                        f_diag_hit(0, time, diagD)
                        f_candidate_audit(time, diagD)
                    float sg = isLong ? 1.0 : -1.0
"""
if old not in pine:
    raise SystemExit("Could not instrument Candidate stage")
pine = pine.replace(old, new, 1)

old = """                        if v7 and v8
                            float sweepAtr = sweepDistance / atr3
"""
new = """                        if v7 and time >= AUDIT_START and time < AUDIT_END
                            f_diag_hit(1, time, isLong ? 1 : -1)
                        if v7 and v8 and time >= AUDIT_START and time < AUDIT_END
                            f_diag_hit(2, time, isLong ? 1 : -1)

                        if v7 and v8
                            float sweepAtr = sweepDistance / atr3
"""
if old not in pine:
    raise SystemExit("Could not instrument V7/V8 stages")
pine = pine.replace(old, new, 1)

old = """                            bool v15 = score >= V15_SCORE_THRESHOLD
                            if v15 and v15CountTodayL < MAX_V15_PER_ET_DAY
                                v15CountTodayL += 1
                                bool v27 = not (reclaim >= V27_RTH and reclaimXWick >= V27_WTH)
"""
new = """                            bool v15 = score >= V15_SCORE_THRESHOLD
                            if v15 and time >= AUDIT_START and time < AUDIT_END
                                f_diag_hit(3, time, isLong ? 1 : -1)
                                array.push(diagV15Times, time)
                                array.push(diagV15Dirs, isLong ? 1 : -1)
                                array.push(diagV15DayNums, v15CountTodayL + 1)
                                array.push(diagV15Frozen, f_diag_is_frozen(time, isLong ? 1 : -1))
                                array.push(diagV15Scores, score)
                            if v15 and v15CountTodayL < MAX_V15_PER_ET_DAY
                                if time >= AUDIT_START and time < AUDIT_END
                                    f_diag_hit(4, time, isLong ? 1 : -1)
                                v15CountTodayL += 1
                                bool v27 = not (reclaim >= V27_RTH and reclaimXWick >= V27_WTH)
                                if v27 and time >= AUDIT_START and time < AUDIT_END
                                    f_diag_hit(5, time, isLong ? 1 : -1)
"""
if old not in pine:
    raise SystemExit("Could not instrument V15/day-cap/V27 stages")
pine = pine.replace(old, new, 1)

// Sep 15 exact mismatch table: audit-only, no strategy logic changes.
sep15_tail = r"""
var table sep15Table = table.new(position.middle_right, 3, 10, border_width = 1)
if barstate.islast
    int sep15Start = timestamp("America/New_York", 2026, 9, 15, 0, 0)
    int sep16Start = timestamp("America/New_York", 2026, 9, 16, 0, 0)
    table.cell(sep15Table, 0, 0, "SEP 15 EXACT MISMATCHES")
    table.cell(sep15Table, 1, 0, "Time")
    table.cell(sep15Table, 2, 0, "Dir")
    int rr = 1
    table.cell(sep15Table, 0, rr, "PINE EXTRA")
    rr += 1
    for jj = 0 to array.size(extraCandTimes) - 1
        int tt = array.get(extraCandTimes, jj)
        if tt >= sep15Start and tt < sep16Start and rr < 5
            table.cell(sep15Table, 0, rr, "Extra")
            table.cell(sep15Table, 1, rr, str.format_time(tt, "HH:mm", "America/New_York"))
            table.cell(sep15Table, 2, rr, array.get(extraCandDirs, jj) == 1 ? "LONG" : "SHORT")
            rr += 1
    if rr < 5
        table.cell(sep15Table, 0, rr, "PY MISSING")
        rr += 1
    for jj = 0 to 685
        int tt = array.get(pyCandTimes, jj)
        if tt >= sep15Start and tt < sep16Start and not array.get(pyCandMatched, jj) and rr < 10
            table.cell(sep15Table, 0, rr, "Missing")
            table.cell(sep15Table, 1, rr, str.format_time(tt, "HH:mm", "America/New_York"))
            table.cell(sep15Table, 2, rr, array.get(pyCandDirs, jj) == 1 ? "LONG" : "SHORT")
            rr += 1
"""
pine += sep15_tail

OUT.write_text(pine)

print("CREATED", OUT)
print("VERSION: CANDIDATE PARITY V3 — SEP 15 ONLY")
print("AUDIT WINDOW: Sep 1-17, 2026 ET")
print("LEFT TABLE: stage-by-stage divergence")
print("RIGHT TABLE: final selection parity")
print("BOTTOM-RIGHT TABLE: Sep 1 Pine V15 sequence before 04:57")
print("Frozen 50 are comparison-only; strategy rules are unchanged.")
