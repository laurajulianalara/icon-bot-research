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
OUT = Path("src/icon_divergence_diagnostic.pine")

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

# Candidate: count every Pine running-extreme candidate in the audit window,
# before V7/V8 filtering.
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

# Split the combined V7+V8 branch so each stage is independently observable.
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

# V15 before the daily six-trade cap.
old = """                            bool v15 = score >= V15_SCORE_THRESHOLD
                            if v15 and v15CountTodayL < MAX_V15_PER_ET_DAY
                                v15CountTodayL += 1
                                bool v27 = not (reclaim >= V27_RTH and reclaimXWick >= V27_WTH)
"""
new = """                            bool v15 = score >= V15_SCORE_THRESHOLD
                            if v15 and time >= AUDIT_START and time < AUDIT_END
                                f_diag_hit(3, time, isLong ? 1 : -1)
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

# Put the stage dashboard on the left so it cannot cover the existing
# selection-parity dashboard on the middle-right.
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
"""
pine += tail

OUT.write_text(pine)
print("CREATED", OUT)
print("AUDIT WINDOW: Sep 1-17, 2026 ET")
print("LEFT TABLE: stage-by-stage divergence")
print("RIGHT TABLE: final selection parity")
print("Frozen 50 are comparison-only; strategy rules are unchanged.")
