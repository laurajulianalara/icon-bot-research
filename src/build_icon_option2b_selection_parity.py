"""Build Sep 1-17 2026 Option 2B Pine selection diagnostic.
Python Option 2B keys are the answer key only; they never authorize Pine trades.
"""
from pathlib import Path
import subprocess, pandas as pd
TZ="America/New_York"
BASE=Path("src/icon_bot_option2b.pine"); OUT=Path("src/icon_option2b_selection_parity.pine")
subprocess.run(["python","src/build_icon_bot_option2b.py"],check=True)
d=pd.read_csv("data/v2b_final_trade_cap_trades.csv")
t=pd.to_datetime(d["candidate_time"],utc=True).dt.tz_convert(TZ)
d["candidate_time_et"]=t
d=d[(t>=pd.Timestamp("2026-09-01",tz=TZ))&(t<pd.Timestamp("2026-09-18",tz=TZ))].sort_values(["candidate_time_et","direction"]).reset_index(drop=True)
N=len(d)
print("PYTHON OPTION 2B EXPECTED:",N)
def ms(x): return int(x.tz_convert("UTC").timestamp()*1000)
times=",".join(str(ms(x)) for x in d.candidate_time_et)
dirs=",".join("1" if x=="LONG" else "-1" for x in d.direction)
pine=BASE.read_text()
needle="// Frozen thresholds\n"
defs=f"""// OPTION 2B SELECTION PARITY — SEP 1-17 2026
// Python keys below are comparison-only and NEVER authorize a trade.
var array<int> auditTimes = array.from({times})
var array<int> auditDirs = array.from({dirs})
var array<bool> auditMatched = array.new_bool({N}, false)
var int auditSelected = 0
var int auditMatchedCount = 0
var int auditExtra = 0
AUDIT_START = timestamp("America/New_York", 2026, 9, 1, 0, 0)
AUDIT_END = timestamp("America/New_York", 2026, 9, 18, 0, 0)

"""
if needle not in pine: raise SystemExit("threshold insertion point missing")
pine=pine.replace(needle,defs+needle,1)
old="""                                    finalTradesTodayL += 1
                                    strategy.entry(isLong ? "IB Long" : "IB Short", isLong ? strategy.long : strategy.short, qty = 1)"""
new=f"""                                    finalTradesTodayL += 1
                                    if time >= AUDIT_START and time < AUDIT_END
                                        auditSelected += 1
                                        int auditD = isLong ? 1 : -1
                                        bool auditFound = false
                                        for auditI = 0 to {N-1}
                                            if not array.get(auditMatched, auditI) and array.get(auditTimes, auditI) == time and array.get(auditDirs, auditI) == auditD
                                                array.set(auditMatched, auditI, true)
                                                auditMatchedCount += 1
                                                auditFound := true
                                                break
                                        if not auditFound
                                            auditExtra += 1
                                    strategy.entry(isLong ? "IB Long" : "IB Short", isLong ? strategy.long : strategy.short, qty = 1)"""
if old not in pine: raise SystemExit("final entry insertion point missing")
pine=pine.replace(old,new,1)
pine+=f"""
var table auditTable = table.new(position.middle_right, 2, 7, border_width=1)
if barstate.islast
    int auditMissing = {N} - auditMatchedCount
    float auditPct = {N} > 0 ? 100.0 * auditMatchedCount / {N}.0 : na
    table.cell(auditTable,0,0,"OPTION 2B — SELECTION PARITY")
    table.cell(auditTable,1,0,"SEP 1–17")
    table.cell(auditTable,0,1,"Python expected")
    table.cell(auditTable,1,1,"{N}")
    table.cell(auditTable,0,2,"Pine selected")
    table.cell(auditTable,1,2,str.tostring(auditSelected))
    table.cell(auditTable,0,3,"Matched")
    table.cell(auditTable,1,3,str.tostring(auditMatchedCount))
    table.cell(auditTable,0,4,"Missing")
    table.cell(auditTable,1,4,str.tostring(auditMissing))
    table.cell(auditTable,0,5,"Extra")
    table.cell(auditTable,1,5,str.tostring(auditExtra))
    table.cell(auditTable,0,6,"Parity")
    table.cell(auditTable,1,6,str.tostring(auditPct,"#.00")+"%")
"""
OUT.write_text(pine)
print("CREATED",OUT)
print("Paste this diagnostic into TradingView on exact MNQZ2026, 3-minute chart.")
