import pandas as pd
import numpy as np

# THE ICON — OPTION 2B SPLIT TEST
# Option 2A remains untouched.
# ONLY change: 6/day cap is applied to FINAL valid trades, after V27 +
# canonical supersession/ticker/risk checks, instead of to V15 survivors.

ONE = "data/mnq_continuous_1m.parquet"
CAND = "data/reversal_candidates.parquet"
V11 = "data/v11_reversal_state_forensics.csv"
A_LOCKED = "data/v27_option2a_trades.csv"
OUT_TRADES = "data/v2b_final_trade_cap_trades.csv"
OUT_RR = "data/v2b_final_trade_cap_rr_1_to_6.csv"
RRS = [1,2,3,4,5,6]
TZ = "America/New_York"
V15_SCORE_THRESHOLD = 0.145921011058
RTH = 0.576132
WTH = 0.183258

one = pd.read_parquet(ONE)
cand = pd.read_parquet(CAND)
q = pd.read_csv(V11)
a = pd.read_csv(A_LOCKED)

one["time_ny"] = pd.to_datetime(one["time_ny"])
cand["time_ny"] = pd.to_datetime(cand["time_ny"])
q["candidate_time"] = pd.to_datetime(q["candidate_time"], utc=True)
q["candidate_time_et"] = q["candidate_time"].dt.tz_convert(TZ)
a["candidate_time"] = pd.to_datetime(a["candidate_time"], utc=True)

one = one.sort_values("time_ny").reset_index(drop=True)
cand = cand.sort_values("time_ny").drop_duplicates(
    ["time_ny","session","direction"]
).reset_index(drop=True)
cand["next_same_extreme_time"] = cand.groupby(
    ["session_id","direction"], sort=False
).time_ny.shift(-1)
idx = pd.Series(one.index, index=one.time_ny).to_dict()
cm = {(r.time_ny, str(r.direction)): r for _, r in cand.iterrows()}

# Exact V15 feature/score construction.
q["reclaim_x_wick"] = q.early_reclaim_atr * q.wick_percent
q["close_x_reclaim"] = q.m2_close_pos * q.early_reclaim_atr
q["sweep_minus_reclaim"] = q.sweep_atr - q.early_reclaim_atr
q["impulse_minus_reclaim"] = q.reversal_impulse - q.early_reclaim_atr
q["quality_balance"] = (
    q.rejection_quality * q.impulse_to_reclaim / (1 + q.reclaim_to_sweep)
)
parts = []
for col, hi, w in [
    ("rejection_quality",1,2),
    ("impulse_to_reclaim",1,2),
    ("reclaim_to_sweep",0,1),
    ("reversal_impulse",1,1),
    ("reclaim_x_wick",0,2),
    ("close_x_reclaim",0,2),
    ("sweep_minus_reclaim",1,1),
    ("impulse_minus_reclaim",1,2),
    ("quality_balance",1,2),
]:
    rank = q[col].rank(pct=True)
    comp = rank if hi else 1-rank
    parts += [comp] * w
q["score"] = pd.concat(parts, axis=1).mean(axis=1)

# Same frozen V15 threshold, but NO pre-V27 six/day cap.
z = q[q.score >= V15_SCORE_THRESHOLD].copy()

# Same frozen V27 rule.
z = z[~(
    (z.early_reclaim_atr >= RTH)
    & (z.reclaim_x_wick >= WTH)
)].copy()
z = z.sort_values("candidate_time_et").reset_index(drop=True)

def canonical_setup(row):
    key = (row.candidate_time_et, str(row.direction))
    c = cm.get(key)
    if c is None:
        return None
    i = idx.get(c.time_ny)
    if i is None or i + 3 >= len(one):
        return None
    j = i + 3
    signal = one.iloc[j].time_ny
    if one.iloc[j].ticker != c.ticker:
        return None
    if pd.notna(c.next_same_extreme_time) and signal >= c.next_same_extreme_time:
        return None
    entry = float(one.iloc[j].open)
    stop = float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk = entry-stop if c.direction=="LONG" else stop-entry
    if risk <= 0:
        return None
    return c, j, signal, entry, stop, risk

# OPTION 2B ONLY CHANGE:
# A daily slot is consumed only after the setup is a canonical valid trade.
selected = []
count_by_day = {}
for _, row in z.iterrows():
    setup = canonical_setup(row)
    if setup is None:
        continue
    c, j, signal, entry, stop, risk = setup
    day = signal.tz_convert(TZ).date()
    n = count_by_day.get(day, 0)
    if n >= 6:
        continue
    count_by_day[day] = n + 1
    selected.append({
        "candidate_time": row.candidate_time,
        "candidate_time_et": row.candidate_time_et,
        "entry_time": signal,
        "date_et": day,
        "session": row.session,
        "direction": row.direction,
        "score": row.score,
        "early_reclaim_atr": row.early_reclaim_atr,
        "reclaim_x_wick": row.reclaim_x_wick,
        "entry": entry,
        "stop": stop,
        "risk_points": risk,
    })

b = pd.DataFrame(selected)
if b.empty:
    raise RuntimeError("Option 2B selected zero trades.")

def replay(row, rr):
    c = cm.get((row.candidate_time_et, str(row.direction)))
    if c is None:
        return "MISSING"
    i = idx.get(c.time_ny)
    if i is None or i+3 >= len(one):
        return "MISSING"
    j = i+3
    signal = one.iloc[j].time_ny
    if one.iloc[j].ticker != c.ticker:
        return "MISSING"
    if pd.notna(c.next_same_extreme_time) and signal >= c.next_same_extreme_time:
        return "MISSING"
    entry = float(one.iloc[j].open)
    stop = float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
    risk = entry-stop if c.direction=="LONG" else stop-entry
    if risk <= 0:
        return "MISSING"
    target = entry+rr*risk if c.direction=="LONG" else entry-rr*risk
    for k in range(j, min(j+241, len(one))):
        bar = one.iloc[k]
        if bar.ticker != c.ticker:
            break
        stop_hit = bar.low <= stop if c.direction=="LONG" else bar.high >= stop
        target_hit = bar.high >= target if c.direction=="LONG" else bar.low <= target
        if stop_hit:
            return "LOSS"
        if target_hit:
            return "WIN"
    return "UNRESOLVED"

rows = []
for rr in RRS:
    oc = b.apply(lambda r: replay(r, rr), axis=1)
    b[f"{rr}R"] = oc
    wins = int((oc=="WIN").sum())
    losses = int((oc=="LOSS").sum())
    unresolved = int((oc=="UNRESOLVED").sum())
    missing = int((oc=="MISSING").sum())
    resolved = wins + losses
    wr = 100*wins/resolved if resolved else np.nan
    pnl = wins*(rr*300) - losses*300
    rows.append([rr,len(b),wins,losses,unresolved,missing,wr,pnl])

rrout = pd.DataFrame(rows, columns=[
    "rr","trades","wins","losses","unresolved","missing","wr_pct","pnl_at_300"
])

def max_loss_streak(s):
    cur = mx = 0
    for x in s:
        cur = cur + 1 if x=="LOSS" else 0
        mx = max(mx, cur)
    return mx

print("\n=== THE ICON — OPTION 2B SPLIT TEST ===")
print("ONLY CHANGE: six/day cap counts FINAL valid trades.")
print(f"Option 2A locked trades in this research period: {len(a)}")
print(f"Option 2B trades in same research period:        {len(b)}")
print(f"Additional trades:                              {len(b)-len(a):+d}")
print(f"Active days: {b.date_et.nunique()} | Avg trades/active day: {len(b)/b.date_et.nunique():.2f}")
print(f"Max actual trades/day: {b.groupby('date_et').size().max()}")

print("\n=== OPTION 2B RR 1:1 THROUGH 1:6 ===")
print(rrout.round(2).to_string(index=False))

print("\n=== OPTION 2B SESSION DISTRIBUTION ===")
sess = b.groupby("session").size().sort_values(ascending=False)
for name, n in sess.items():
    print(f"{name:8s} {n:4d} | {100*n/len(b):5.1f}%")

print("\n=== 4R LOSS STREAK ===")
print("Max consecutive 4R losses:", max_loss_streak(b["4R"]))

# Sep 2026 slice if present.
sep = b[
    (pd.to_datetime(b.entry_time).dt.tz_convert(TZ).dt.year == 2026)
    & (pd.to_datetime(b.entry_time).dt.tz_convert(TZ).dt.month == 9)
].copy()
if len(sep):
    print("\n=== SEPTEMBER 2026 — OPTION 2B ===")
    print("Trades:", len(sep))
    print(sep.groupby("session").size().sort_values(ascending=False).to_string())
    for rr in RRS:
        s = sep[f"{rr}R"]
        w = int((s=="WIN").sum()); l = int((s=="LOSS").sum())
        print(f"{rr}R: {w}W / {l}L | WR {100*w/(w+l):.2f}%" if w+l else f"{rr}R: unresolved")

b.to_csv(OUT_TRADES, index=False)
rrout.to_csv(OUT_RR, index=False)
print("\nSaved:", OUT_TRADES)
print("Saved:", OUT_RR)
print("\nOption 2A files were NOT modified.")
