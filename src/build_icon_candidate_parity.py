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

f_candidate_audit(int t, int d) =>
    int found = -1
    for jj = 0 to 685
        if array.get(pyCandTimes, jj) == t and array.get(pyCandDirs, jj) == d
            found := jj
            break
    if found >= 0
        array.set(pyCandMatched, found, true)
    else if array.size(extraCandTimes) < 12
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

tail = r"""
// Stage-by-stage divergence dashboard.
var table divTable = table.new(position.middle_left, 3, 8, border_width = 1)
if barstate.islast
    table.cell(divTable, 0, 0, "OPTION 2A — DIVERGENCE")
    table.cell(divTable, 1, 0, "Pine total")
    table.cell(divTable, 2, 0, "Frozen 50 alive")
    table.cell(divTable, 0, 1, "Candidate")
    table.cell(divTable, 1, 1, str.tostring(array.get(diagTotal, 0)))
    table.cell(divTable, 2, 1, str.tostring(array.get(diagFrozen, 0)))
    table.cell(divTable, 0, 2, "V7")
    table.cell(divTable, 1, 2, str.tostring(array.get(diagTotal, 1)))
    table.cell(divTable, 2, 2, str.tostring(array.get(diagFrozen, 1)))
    table.cell(divTable, 0, 3, "V8")
    table.cell(divTable, 1, 3, str.tostring(array.get(diagTotal, 2)))
    table.cell(divTable, 2, 3, str.tostring(array.get(diagFrozen, 2)))
    table.cell(divTable, 0, 4, "V15")
    table.cell(divTable, 1, 4, str.tostring(array.get(diagTotal, 3)))
    table.cell(divTable, 2, 4, str.tostring(array.get(diagFrozen, 3)))
    table.cell(divTable, 0, 5, "6/day")
    table.cell(divTable, 1, 5, str.tostring(array.get(diagTotal, 4)))
    table.cell(divTable, 2, 5, str.tostring(array.get(diagFrozen, 4)))
    table.cell(divTable, 0, 6, "V27")
    table.cell(divTable, 1, 6, str.tostring(array.get(diagTotal, 5)))
    table.cell(divTable, 2, 6, str.tostring(array.get(diagFrozen, 5)))
    int firstDropStage = -1
    for ss = 0 to 5
        if firstDropStage == -1 and array.get(diagFrozen, ss) < 50
            firstDropStage := ss
    string firstDrop = firstDropStage == -1 ? "NONE" : firstDropStage == 0 ? "Candidate" : firstDropStage == 1 ? "V7" : firstDropStage == 2 ? "V8" : firstDropStage == 3 ? "V15" : firstDropStage == 4 ? "6/day" : "V27"
    table.cell(divTable, 0, 7, "First frozen drop")
    table.cell(divTable, 1, 7, firstDrop)
    table.cell(divTable, 2, 7, firstDropStage == -1 ? "50/50 survive" : str.tostring(array.get(diagFrozen, firstDropStage)) + "/50")

var table capTable = table.new(position.bottom_left, 2, 5, border_width = 1)
if barstate.islast
    int blockedIdx = -1
    for ii = 0 to array.size(diagV15Times) - 1
        if blockedIdx == -1 and array.get(diagV15Frozen, ii) and array.get(diagV15DayNums, ii) > 6
            blockedIdx := ii
    table.cell(capTable, 0, 0, "6/DAY — FIRST BLOCKED FROZEN")
    if blockedIdx >= 0
        int bt = array.get(diagV15Times, blockedIdx)
        int bd = array.get(diagV15Dirs, blockedIdx)
        int bn = array.get(diagV15DayNums, blockedIdx)
        table.cell(capTable, 0, 1, "Time")
        table.cell(capTable, 1, 1, str.format_time(bt, "yyyy-MM-dd HH:mm", "America/New_York"))
        table.cell(capTable, 0, 2, "Direction")
        table.cell(capTable, 1, 2, bd == 1 ? "LONG" : "SHORT")
        table.cell(capTable, 0, 3, "Pine V15 # that day")
        table.cell(capTable, 1, 3, str.tostring(bn))
        table.cell(capTable, 0, 4, "Meaning")
        table.cell(capTable, 1, 4, "Earlier Pine V15 extras consumed cap")
    else
        table.cell(capTable, 0, 1, "None found")

// Sep 1 pre-cap sequence.
var table seqTable = table.new(position.bottom_right, 6, 9, border_width = 1)
if barstate.islast
    int targetDayStart = timestamp("America/New_York", 2026, 9, 1, 0, 0)
    int blockedTime = timestamp("America/New_York", 2026, 9, 1, 4, 57)
    table.cell(seqTable, 0, 0, "SEP 1 — PINE V15 BEFORE 04:57")
    table.cell(seqTable, 1, 0, "Time")
    table.cell(seqTable, 2, 0, "Dir")
    table.cell(seqTable, 3, 0, "Frozen?")
    table.cell(seqTable, 4, 0, "V15 score")
    table.cell(seqTable, 5, 0, "Day #")
    int row = 1
    for ii = 0 to array.size(diagV15Times) - 1
        int tt = array.get(diagV15Times, ii)
        if tt >= targetDayStart and tt < blockedTime and row <= 7
            table.cell(seqTable, 0, row, str.tostring(row))
            table.cell(seqTable, 1, row, str.format_time(tt, "HH:mm", "America/New_York"))
            table.cell(seqTable, 2, row, array.get(diagV15Dirs, ii) == 1 ? "LONG" : "SHORT")
            table.cell(seqTable, 3, row, array.get(diagV15Frozen, ii) ? "YES" : "NO")
            table.cell(seqTable, 4, row, str.tostring(array.get(diagV15Scores, ii), "#.######"))
            table.cell(seqTable, 5, row, str.tostring(array.get(diagV15DayNums, ii)))
            row += 1
    table.cell(seqTable, 0, 8, "Blocked")
    table.cell(seqTable, 1, 8, "04:57")
    table.cell(seqTable, 2, 8, "LONG")
    table.cell(seqTable, 3, 8, "YES")
    table.cell(seqTable, 4, 8, "Python selected")
    table.cell(seqTable, 5, 8, "Pine #7")
"""

pine += tail

candidate_tail = r"""
var table candTable = table.new(position.top_center, 4, 15, border_width = 1)
if barstate.islast
    int matchedCandidates = 0
    for jj = 0 to 685
        if array.get(pyCandMatched, jj)
            matchedCandidates += 1
    int missingCandidates = 686 - matchedCandidates
    int pineCandidates = array.get(diagTotal, 0)
    int extraCandidates = pineCandidates - matchedCandidates
    table.cell(candTable, 0, 0, "CANDIDATE PARITY")
    table.cell(candTable, 1, 0, "Python")
    table.cell(candTable, 2, 0, "Pine")
    table.cell(candTable, 3, 0, "Matched")
    table.cell(candTable, 0, 1, "Totals")
    table.cell(candTable, 1, 1, "686")
    table.cell(candTable, 2, 1, str.tostring(pineCandidates))
    table.cell(candTable, 3, 1, str.tostring(matchedCandidates))
    table.cell(candTable, 0, 2, "Missing")
    table.cell(candTable, 1, 2, str.tostring(missingCandidates))
    table.cell(candTable, 2, 2, "Extra")
    table.cell(candTable, 3, 2, str.tostring(extraCandidates))
    table.cell(candTable, 0, 3, "FIRST PINE EXTRAS")
    table.cell(candTable, 1, 3, "Time")
    table.cell(candTable, 2, 3, "Dir")
    int nshow = math.min(array.size(extraCandTimes), 10)
    if nshow > 0
        for jj = 0 to nshow - 1
            int tt = array.get(extraCandTimes, jj)
            int dd = array.get(extraCandDirs, jj)
            table.cell(candTable, 0, 4 + jj, str.tostring(jj + 1))
            table.cell(candTable, 1, 4 + jj, str.format_time(tt, "yyyy-MM-dd HH:mm", "America/New_York"))
            table.cell(candTable, 2, 4 + jj, dd == 1 ? "LONG" : "SHORT")
"""
pine += candidate_tail

OUT.write_text(pine)

print("CREATED", OUT)
print("VERSION: CANDIDATE PARITY — 686 PYTHON CANDIDATES")
print("AUDIT WINDOW: Sep 1-17, 2026 ET")
print("LEFT TABLE: stage-by-stage divergence")
print("RIGHT TABLE: final selection parity")
print("BOTTOM-RIGHT TABLE: Sep 1 Pine V15 sequence before 04:57")
print("Frozen 50 are comparison-only; strategy rules are unchanged.")
