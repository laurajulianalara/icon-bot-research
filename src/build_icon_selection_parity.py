"""Build a separate TradingView selection-parity diagnostic.

It starts from the current frozen Option 2A Pine build, then instruments the
raw V27-qualified selections BEFORE TradingView position/order gating. The
frozen Sep 1-17 master is used only as the audit answer key, never as a
selection input.
"""
from pathlib import Path
import subprocess
import pandas as pd

TZ = "America/New_York"
MASTER = Path("data/ICON_MASTER_1911_TRADE_LEVEL.csv")
BASE = Path("src/icon_bot_frozen_option2a.pine")
OUT = Path("src/icon_selection_parity.pine")

subprocess.run(["python", "src/build_icon_bot_frozen_option2a.py"], check=True)

df = pd.read_csv(MASTER)
df["candidate_time"] = pd.to_datetime(df["candidate_time"], utc=True).dt.tz_convert(TZ)
start = pd.Timestamp("2026-09-01 00:00:00", tz=TZ)
end = pd.Timestamp("2026-09-18 00:00:00", tz=TZ)
df = df[(df.candidate_time >= start) & (df.candidate_time < end)].copy()
df = df.sort_values(["candidate_time", "direction"]).reset_index(drop=True)
assert len(df) == 50, f"Expected 50 frozen trades, found {len(df)}"

def ms(ts):
    return int(ts.tz_convert("UTC").timestamp() * 1000)

times = ",".join(str(ms(x)) for x in df.candidate_time)
dirs = ",".join("1" if x == "LONG" else "-1" for x in df.direction)

pine = BASE.read_text()

needle = "// Frozen thresholds\n"
audit_defs = f"""// SELECTION PARITY AUDIT — Sep 1-17, 2026 only.
// These 50 keys are comparison data only. They NEVER authorize a trade.
var array<int> auditTimes = array.from({times})
var array<int> auditDirs = array.from({dirs})
var array<bool> auditMatched = array.new_bool(50, false)
var int auditSelected = 0
var int auditMatchedCount = 0
var int auditExtra = 0
AUDIT_START = timestamp("America/New_York", 2026, 9, 1, 0, 0)
AUDIT_END = timestamp("America/New_York", 2026, 9, 18, 0, 0)

f_audit_selection(int candidateTime, bool isLong) =>
    bool matched = false
    if candidateTime >= AUDIT_START and candidateTime < AUDIT_END
        auditSelected += 1
        int d = isLong ? 1 : -1
        for ai = 0 to 49
            if not array.get(auditMatched, ai) and array.get(auditTimes, ai) == candidateTime and array.get(auditDirs, ai) == d
                array.set(auditMatched, ai, true)
                auditMatchedCount += 1
                matched := true
                break
        if not matched
            auditExtra += 1
    matched

"""
if needle not in pine:
    raise SystemExit("Could not find threshold insertion point")
pine = pine.replace(needle, audit_defs + needle, 1)

old = """                                bool v27 = not (reclaim >= V27_RTH and reclaimXWick >= V27_WTH)
                                if v27 and strategy.position_size == 0 and not orderPendingL
"""
new = """                                bool v27 = not (reclaim >= V27_RTH and reclaimXWick >= V27_WTH)
                                if v27
                                    f_audit_selection(time, isLong)
                                if v27 and strategy.position_size == 0 and not orderPendingL
"""
if old not in pine:
    raise SystemExit("Could not find V27 selection point")
pine = pine.replace(old, new, 1)

tail = """
// Selection-parity dashboard. Raw selection is measured before order/position gating.
var table auditTable = table.new(position.middle_right, 2, 7, border_width = 1)
if barstate.islast
    int auditMissing = 50 - auditMatchedCount
    float auditPct = 100.0 * auditMatchedCount / 50.0
    table.cell(auditTable, 0, 0, "OPTION 2A — SELECTION PARITY")
    table.cell(auditTable, 1, 0, "SEP 1–17")
    table.cell(auditTable, 0, 1, "Frozen expected")
    table.cell(auditTable, 1, 1, "50")
    table.cell(auditTable, 0, 2, "Pine selected")
    table.cell(auditTable, 1, 2, str.tostring(auditSelected))
    table.cell(auditTable, 0, 3, "Matched")
    table.cell(auditTable, 1, 3, str.tostring(auditMatchedCount))
    table.cell(auditTable, 0, 4, "Missing")
    table.cell(auditTable, 1, 4, str.tostring(auditMissing))
    table.cell(auditTable, 0, 5, "Extra")
    table.cell(auditTable, 1, 5, str.tostring(auditExtra))
    table.cell(auditTable, 0, 6, "Selection parity")
    table.cell(auditTable, 1, 6, str.tostring(auditPct, "#.00") + "%")
"""
pine += tail
OUT.write_text(pine)
print("CREATED", OUT)
print("FROZEN EXPECTED: 50")
print("AUDIT WINDOW: Sep 1-17, 2026 ET")
print("IMPORTANT: frozen keys are comparison-only; Pine selection remains independent.")
print("Next: paste src/icon_selection_parity.pine into a separate TradingView Strategy on MNQ1! 3m.")
