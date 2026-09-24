"""Build TradingView candidate diagnostic for frozen Option 2A.

This diagnostic instruments candidate generation and displays only the exact
Sep 15, 2026 candidate mismatches between Pine and the authoritative Python
candidate set. It does not change any strategy selection rule or authorize
trades.
"""
from pathlib import Path
import subprocess
import pandas as pd

BASE = Path("src/icon_selection_parity.pine")
OUT = Path("src/icon_candidate_parity.pine")

subprocess.run(["python", "src/build_icon_selection_parity.py"], check=True)
pine = BASE.read_text()

# Authoritative Python candidate answer key. Audit-only.
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

needle = "// Frozen thresholds\n"
defs = f"""// SEP 15 CANDIDATE DIAGNOSTIC
var array<int> pyCandTimes = array.from({candidate_times})
var array<int> pyCandDirs = array.from({candidate_dirs})
var array<bool> pyCandMatched = array.new_bool(686, false)
var array<int> extraCandTimes = array.new_int()
var array<int> extraCandDirs = array.new_int()\nvar array<float> extraCandPrior = array.new_float()\nvar array<float> extraCandExtreme = array.new_float()

f_candidate_audit(int t, int d, float prior, float ext) =>
    int found = -1
    for jj = 0 to 685
        if array.get(pyCandTimes, jj) == t and array.get(pyCandDirs, jj) == d
            found := jj
            break
    if found >= 0
        array.set(pyCandMatched, found, true)
    else
        array.push(extraCandTimes, t)
        array.push(extraCandDirs, d)

"""
if needle not in pine:
    raise SystemExit("Could not find diagnostic insertion point")
pine = pine.replace(needle, defs + needle, 1)

old = """                if exists
                    float sg = isLong ? 1.0 : -1.0
"""
new = """                if exists
                    if time >= AUDIT_START and time < AUDIT_END
                        f_candidate_audit(time, isLong ? 1 : -1, isLong ? runLow : runHigh, isLong ? low : high)
                    float sg = isLong ? 1.0 : -1.0
"""
if old not in pine:
    raise SystemExit("Could not instrument Candidate stage")
pine = pine.replace(old, new, 1)

sep15_tail = r'''
var table sep15Table = table.new(position.middle_right, 5, 10, border_width = 1)
if barstate.islast
    int sep15Start = timestamp("America/New_York", 2026, 9, 15, 0, 0)
    int sep16Start = timestamp("America/New_York", 2026, 9, 16, 0, 0)
    table.cell(sep15Table, 0, 0, "SEP 15 EXACT MISMATCHES")
    table.cell(sep15Table, 1, 0, "Time")
    table.cell(sep15Table, 2, 0, "Dir")\n    table.cell(sep15Table, 3, 0, "TV prior")\n    table.cell(sep15Table, 4, 0, "TV extreme")

    int rr = 1
    table.cell(sep15Table, 0, rr, "PINE EXTRA")
    rr += 1

    for jj = 0 to array.size(extraCandTimes) - 1
        int tt = array.get(extraCandTimes, jj)
        if tt >= sep15Start and tt < sep16Start and rr < 5
            table.cell(sep15Table, 0, rr, "Extra")
            table.cell(sep15Table, 1, rr, str.format_time(tt, "HH:mm", "America/New_York"))
            table.cell(sep15Table, 2, rr, array.get(extraCandDirs, jj) == 1 ? "LONG" : "SHORT")\n            table.cell(sep15Table, 3, rr, str.tostring(array.get(extraCandPrior, jj)))\n            table.cell(sep15Table, 4, rr, str.tostring(array.get(extraCandExtreme, jj)))
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
'''

pine += sep15_tail
OUT.write_text(pine)

print("CREATED", OUT)
print("VERSION: CANDIDATE PARITY V4 — SEP 15 STATE")
print("DISPLAY: Sep 15 mismatches + TradingView prior/extreme state")
print("Frozen/Python candidates are comparison-only; strategy rules are unchanged.")
