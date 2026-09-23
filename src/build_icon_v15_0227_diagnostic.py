"""Build stage-by-stage TradingView divergence diagnostic for frozen Option 2A.

Starts from the working selection-parity diagnostic and adds stage counters.
For each stage it reports:
  1) total Pine events reaching that stage
  2) how many of the authoritative frozen 50 are still present

This does not change any selection rule or authorize trades.
"""
from pathlib import Path
import subprocess

BASE = Path("src/icon_selection_parity.pine")
OUT = Path("src/icon_v15_0227_diagnostic.pine")

subprocess.run(["python", "src/build_icon_selection_parity.py"], check=True)
pine = BASE.read_text()

# Global arrays are intentionally used here because Pine functions may mutate
# array contents without illegally reassigning global scalar variables.
needle = "// Frozen thresholds\n"
defs = r"""// DIVERGENCE DIAGNOSTIC
// diagTotal / diagFrozen use indexes:
// 0 Candidate, 1 V7, 2 V8, 3 V15, 4 6/day, 5 V27.
var array<int> diagTotal = array.new_int(6, 0)
var array<int> diagFrozen = array.new_int(6, 0)
var array<int> diagV15Times = array.new_int()
var array<int> diagV15Dirs = array.new_int()
var array<int> diagV15DayNums = array.new_int()
var array<bool> diagV15Frozen = array.new_bool()
var array<float> diagV15Scores = array.new_float()
var array<float> diag0227Vals = array.new_float(19, na)

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

                            // Component-level capture for the first false Pine V15 admission:
                            // Sep 1, 2026 02:27 ET LONG. Indexes 0..8 are raw features,
                            // 9..17 are their frozen-reference percentile ranks, 18 is final score.
                            bool diag0227 = isLong and time == timestamp("America/New_York", 2026, 9, 1, 2, 27)
                            if diag0227
                                array.set(diag0227Vals, 0, rejectionQuality)
                                array.set(diag0227Vals, 1, impulseToReclaim)
                                array.set(diag0227Vals, 2, reclaimToSweep)
                                array.set(diag0227Vals, 3, reversalImpulse)
                                array.set(diag0227Vals, 4, reclaimXWick)
                                array.set(diag0227Vals, 5, closeXReclaim)
                                array.set(diag0227Vals, 6, sweepMinusReclaim)
                                array.set(diag0227Vals, 7, impulseMinusReclaim)
                                array.set(diag0227Vals, 8, qualityBalance)
                                array.set(diag0227Vals, 9, v15_0.rank(rejectionQuality))
                                array.set(diag0227Vals, 10, v15_1.rank(impulseToReclaim))
                                array.set(diag0227Vals, 11, v15_2.rank(reclaimToSweep))
                                array.set(diag0227Vals, 12, v15_3.rank(reversalImpulse))
                                array.set(diag0227Vals, 13, v15_4.rank(reclaimXWick))
                                array.set(diag0227Vals, 14, v15_5.rank(closeXReclaim))
                                array.set(diag0227Vals, 15, v15_6.rank(sweepMinusReclaim))
                                array.set(diag0227Vals, 16, v15_7.rank(impulseMinusReclaim))
                                array.set(diag0227Vals, 17, v15_8.rank(qualityBalance))
                                array.set(diag0227Vals, 18, score)

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

# Add focused component table for Sep 1 02:27 LONG.
component_tail = r"""
var table compTable = table.new(position.top_left, 4, 11, border_width = 1)
if barstate.islast
    table.cell(compTable, 0, 0, "SEP 1 02:27 LONG — V15")
    table.cell(compTable, 1, 0, "Raw")
    table.cell(compTable, 2, 0, "Rank")
    table.cell(compTable, 3, 0, "Weighted use")

    table.cell(compTable, 0, 1, "rejection_quality")
    table.cell(compTable, 0, 2, "impulse_to_reclaim")
    table.cell(compTable, 0, 3, "reclaim_to_sweep")
    table.cell(compTable, 0, 4, "reversal_impulse")
    table.cell(compTable, 0, 5, "reclaim_x_wick")
    table.cell(compTable, 0, 6, "close_x_reclaim")
    table.cell(compTable, 0, 7, "sweep_minus_reclaim")
    table.cell(compTable, 0, 8, "impulse_minus_reclaim")
    table.cell(compTable, 0, 9, "quality_balance")

    for jj = 0 to 8
        float rawv = array.get(diag0227Vals, jj)
        float rankv = array.get(diag0227Vals, 9 + jj)
        table.cell(compTable, 1, 1 + jj, str.tostring(rawv, "#.########"))
        table.cell(compTable, 2, 1 + jj, str.tostring(rankv, "#.########"))

    table.cell(compTable, 3, 1, "high x2")
    table.cell(compTable, 3, 2, "high x2")
    table.cell(compTable, 3, 3, "low x1")
    table.cell(compTable, 3, 4, "high x1")
    table.cell(compTable, 3, 5, "low x2")
    table.cell(compTable, 3, 6, "low x2")
    table.cell(compTable, 3, 7, "high x1")
    table.cell(compTable, 3, 8, "high x2")
    table.cell(compTable, 3, 9, "high x2")

    float sc = array.get(diag0227Vals, 18)
    table.cell(compTable, 0, 10, "FINAL SCORE")
    table.cell(compTable, 1, 10, str.tostring(sc, "#.########"))
    table.cell(compTable, 2, 10, "Threshold")
    table.cell(compTable, 3, 10, str.tostring(V15_SCORE_THRESHOLD, "#.########"))
"""
pine += component_tail

OUT.write_text(pine)

print("CREATED", OUT)
print("VERSION: V15 02:27 COMPONENT DIAGNOSTIC")
print("AUDIT WINDOW: Sep 1-17, 2026 ET")
print("LEFT TABLE: stage-by-stage divergence")
print("RIGHT TABLE: final selection parity")
print("TOP-LEFT TABLE: Sep 1 02:27 raw V15 components + ranks")
print("Frozen 50 are comparison-only; strategy rules are unchanged.")
