import pandas as pd
import numpy as np

TODAY = "data/mnq_sep21_2026_1m.parquet"
HIST = "data/mnq_continuous_1m.parquet"
DATE = pd.Timestamp("2026-09-21").date()
RTH = 0.576132
WTH = 0.183258
RISK_DOLLARS = 300

h = pd.read_parquet(HIST)
t = pd.read_parquet(TODAY)
for x in (h, t):
    x["time_ny"] = pd.to_datetime(x["time_ny"])

t = t[t["time_ny"].dt.date == DATE].copy()
if t.empty:
    print("NO SEPT 21 RAW DATA AVAILABLE")
    raise SystemExit

need = ["time_ny","ticker","open","high","low","close","volume"]
one = pd.concat(
    [h[need][h.time_ny < t.time_ny.min()].tail(300), t[need]],
    ignore_index=True
).drop_duplicates("time_ny", keep="last").sort_values("time_ny").reset_index(drop=True)

one["atr1"] = pd.concat([
    one.high-one.low,
    (one.high-one.close.shift()).abs(),
    (one.low-one.close.shift()).abs()
], axis=1).max(axis=1).rolling(20).mean()

z = one.set_index("time_ny")
three = z.resample("3min", label="left", closed="left").agg(
    ticker=("ticker","last"),
    open=("open","first"),
    high=("high","max"),
    low=("low","min"),
    close=("close","last"),
    volume=("volume","sum")
).dropna(subset=["open","high","low","close"]).reset_index()

three["upper_wick"] = three.high - three[["open","close"]].max(axis=1)
three["lower_wick"] = three[["open","close"]].min(axis=1) - three.low

mins = three.time_ny.dt.hour * 60 + three.time_ny.dt.minute
# Same scope as the Sep 18 report: London + NYAM + NYPM.
sm = ((mins >= 120) & (mins < 300)) | ((mins >= 570) & (mins < 750)) | ((mins >= 810) & (mins < 1020))
g = three[(three.time_ny.dt.date == DATE) & sm].copy()

def sess(ts):
    m = ts.hour * 60 + ts.minute
    if 120 <= m < 300:
        return "LONDON"
    if 570 <= m < 750:
        return "NYAM"
    return "NYPM"

g["session"] = g.time_ny.apply(sess)
g = g.reset_index(drop=True)

cands = []
for session, gg in g.groupby("session", sort=False):
    rh = rl = None
    for _, r in gg.iterrows():
        if rh is None:
            rh = float(r.high)
            rl = float(r.low)
            continue
        rng = float(r.high-r.low)
        if r.low < rl:
            cands.append(dict(
                time_ny=r.time_ny, session=session, direction="LONG",
                ticker=r.ticker, extreme=float(r.low),
                wick_percent=float(r.lower_wick/rng) if rng > 0 else 0
            ))
        if r.high > rh:
            cands.append(dict(
                time_ny=r.time_ny, session=session, direction="SHORT",
                ticker=r.ticker, extreme=float(r.high),
                wick_percent=float(r.upper_wick/rng) if rng > 0 else 0
            ))
        rh = max(rh, float(r.high))
        rl = min(rl, float(r.low))

cand = pd.DataFrame(cands)
if cand.empty:
    print("NO SEPT 21 CANDIDATES")
    raise SystemExit

cand = cand.sort_values("time_ny").reset_index(drop=True)
cand["next_same_extreme_time"] = cand.groupby(["session","direction"]).time_ny.shift(-1)

idx1 = pd.Series(one.index, index=one.time_ny).to_dict()
rows = []

for _, c in cand.iterrows():
    i = idx1.get(c.time_ny)
    if i is None or i < 20 or i + 3 >= len(one):
        continue

    a = float(one.iloc[i].atr1)
    if not np.isfinite(a) or a <= 0:
        continue

    sg = 1 if c.direction == "LONG" else -1
    vals = {}
    for k in [1, 2]:
        b = one.iloc[i+k]
        vals[f"m{k}_move_atr"] = (float(b.close)-float(one.iloc[i].close))/a*sg
        cp = (b.close-b.low)/(b.high-b.low) if b.high > b.low else .5
        vals[f"m{k}_close_pos"] = float(cp if c.direction == "LONG" else 1-cp)

    if not (
        vals["m1_move_atr"] <= .300
        and vals["m1_close_pos"] >= .140
        and vals["m2_close_pos"] <= .912
    ):
        continue

    first2 = one.iloc[i+1:i+3]
    reclaim = (
        (float(first2.iloc[-1].close)-float(c.extreme))/a
        if c.direction == "LONG"
        else (float(c.extreme)-float(first2.iloc[-1].close))/a
    )
    rw = reclaim * float(c.wick_percent)
    if reclaim >= RTH and rw >= WTH:
        continue

    j = i + 3
    signal = one.iloc[j].time_ny
    if pd.notna(c.next_same_extreme_time) and signal >= c.next_same_extreme_time:
        continue
    if one.iloc[j].ticker != c.ticker:
        continue

    entry = float(one.iloc[j].open)
    stop = float(c.extreme)-.25 if c.direction == "LONG" else float(c.extreme)+.25
    risk = entry-stop if c.direction == "LONG" else stop-entry
    if risk <= 0:
        continue

    maxr = 0.0
    for q in range(j, min(j+241, len(one))):
        b = one.iloc[q]
        if b.ticker != c.ticker:
            break
        fav = (
            (float(b.high)-entry)/risk
            if c.direction == "LONG"
            else (entry-float(b.low))/risk
        )
        stop_hit = float(b.low) <= stop if c.direction == "LONG" else float(b.high) >= stop
        # Canonical conservative order: stop first.
        if stop_hit:
            break
        maxr = max(maxr, fav)

    rows.append(dict(
        session=c.session, entry_time=signal, direction=c.direction,
        entry=entry, stop=stop, risk_points=risk, max_rr=maxr
    ))

r = pd.DataFrame(rows)
print("\n=== OPTION 2A — SEPT 21 LONDON + NYAM + NYPM ===")
if r.empty:
    print("QUALIFYING TRADES: 0")
    raise SystemExit

print("Trades:", len(r))
print(r[["session","entry_time","direction","entry","stop","risk_points","max_rr"]].to_string(index=False))

print("\nRR RESULTS — $300 RISK")
for rr in range(1, 5):
    wins = int((r.max_rr >= rr).sum())
    losses = len(r) - wins
    wr = 100 * wins / len(r)
    pnl = wins * (rr * RISK_DOLLARS) - losses * RISK_DOLLARS
    print(f"1:{rr} | {wins}W / {losses}L | WR {wr:.2f}% | P&L {pnl:+,.0f} USD")

r.to_csv("data/sep21_option2a.csv", index=False)
print("\nSaved: data/sep21_option2a.csv")
