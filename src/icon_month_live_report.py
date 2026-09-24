import os
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

# ============================================================
# THE ICON — PERMANENT CURRENT-MONTH REPORTER
# Frozen Option 2A logic | $300 risk | RR 1:1 through 1:6
# ============================================================

HIST = "data/mnq_continuous_1m.parquet"
RTH = 0.576132
WTH = 0.183258
RISK_DOLLARS = 300
TZ = "America/New_York"

load_dotenv(".env")
API_KEY = os.getenv("MASSIVE_API_KEY")
if not API_KEY:
    raise ValueError("MASSIVE_API_KEY was not found in .env")

Path("data/reports").mkdir(parents=True, exist_ok=True)

now = datetime.now(ZoneInfo(TZ))
today = pd.Timestamp(now.date())
month_start = today.replace(day=1)

# MNQ quarterly contract for a given date.
def mnq_contract(ts):
    y = ts.year
    m = ts.month

    if m <= 3:
        code = "H"
        yy = y % 100
    elif m <= 6:
        code = "M"
        yy = y % 100
    elif m <= 9:
        code = "U"
        yy = y % 100
    else:
        code = "Z"
        yy = y % 100

    return f"MNQ{code}{yy:02d}"

def session_name(ts):
    m = ts.hour * 60 + ts.minute
    if 1200 <= m < 1440:
        return "ASIA"
    if 120 <= m < 300:
        return "LONDON"
    if 570 <= m < 750:
        return "NYAM"
    if 810 <= m < 1020:
        return "NYPM"
    return None

def download_day(day):
    ticker = mnq_contract(day)
    url = f"https://api.massive.com/futures/v1/aggs/{ticker}"

    local = pd.Timestamp(day.date(), tz=TZ)
    start_utc = local.tz_convert("UTC")
    end_utc = (local + pd.Timedelta(days=1)).tz_convert("UTC")

    params = {
        "resolution": "1min",
        "window_start.gte": start_utc.isoformat(),
        "window_start.lt": end_utc.isoformat(),
        "limit": 50000,
        "sort": "window_start.asc",
        "apiKey": API_KEY,
    }

    r = requests.get(url, params=params, timeout=90)

    if r.status_code != 200:
        print(f"{day.date()} | API {r.status_code}")
        return pd.DataFrame()

    rows = r.json().get("results", [])
    out = []

    for x in rows:
        ts = x.get("window_start")
        if ts is None:
            continue

        out.append({
            "time_utc": pd.to_datetime(ts, unit="ns", utc=True),
            "ticker": ticker,
            "open": x.get("open"),
            "high": x.get("high"),
            "low": x.get("low"),
            "close": x.get("close"),
            "volume": x.get("volume"),
        })

    df = pd.DataFrame(out)

    if df.empty:
        return df

    df["time_ny"] = df["time_utc"].dt.tz_convert(TZ)
    df = df[df.time_ny.dt.date == day.date()].copy()

    return df

# Required market-data columns
need = ["time_ny","ticker","open","high","low","close","volume"]

print("\n============================================================")
print("THE ICON — CURRENT MONTH REPORT")
print("Frozen Option 2A | Risk: $300 | RR: 1:1 through 1:6")
print("============================================================")
print("Month:", month_start.strftime("%B %Y"))
print("Today:", now.strftime("%Y-%m-%d %H:%M:%S ET"))

# ------------------------------------------------------------
# SMART MONTH DATA LOADER
# 1. Use continuous history first
# 2. Use saved daily files second
# 3. Download only missing/current trading dates
# 4. Cache every successful download
# ------------------------------------------------------------

hist_full = pd.read_parquet(HIST)
hist_full["time_ny"] = pd.to_datetime(hist_full["time_ny"])

month_mask = (
    (hist_full.time_ny.dt.year == today.year)
    & (hist_full.time_ny.dt.month == today.month)
)

pieces = []

hist_month = hist_full.loc[month_mask, need].copy()

if not hist_month.empty:
    pieces.append(hist_month)
    print(
        "\nHistorical cache:",
        hist_month.time_ny.min(),
        "->",
        hist_month.time_ny.max()
    )

# Load every saved current-month daily parquet.
pattern = f"mnq_{month_start.strftime('%b').lower()}*_{today.year}*_1m.parquet"

for f in sorted(Path("data").glob(pattern)):
    try:
        x = pd.read_parquet(f)
        x["time_ny"] = pd.to_datetime(x["time_ny"])

        if not set(need).issubset(x.columns):
            continue

        x = x[
            (x.time_ny.dt.year == today.year)
            & (x.time_ny.dt.month == today.month)
        ][need].copy()

        if not x.empty:
            pieces.append(x)

    except Exception as e:
        print("CACHE READ ERROR:", f.name, e)

if pieces:
    existing = (
        pd.concat(pieces, ignore_index=True)
        .drop_duplicates(["time_ny","ticker"], keep="last")
        .sort_values("time_ny")
        .reset_index(drop=True)
    )
else:
    existing = pd.DataFrame(columns=need)

existing_dates = set()

if not existing.empty:
    existing_dates = set(existing.time_ny.dt.date)

print("\nChecking dates...")

# Only request weekdays.
# Current day is ALWAYS refreshed because it may still be developing.
for day in pd.date_range(month_start, today, freq="D"):

    # Saturday/Sunday
    if day.weekday() >= 5:
        continue

    ddate = day.date()

    # Historical/saved dates before today require no API request.
    if ddate in existing_dates and ddate != today.date():
        print(f"{ddate} | LOCAL")
        continue

    print(f"{ddate} | requesting update...")

    # Forward data has been coming from the December MNQ contract.
    # Preserve that convention for Sep 2026 forward collection.
    ticker = f"MNQZ{str(day.year)[-1]}"

    local = pd.Timestamp(ddate, tz=TZ)
    start_utc = local.tz_convert("UTC")
    end_utc = (local + pd.Timedelta(days=1)).tz_convert("UTC")

    url = f"https://api.massive.com/futures/v1/aggs/{ticker}"

    params = {
        "resolution": "1min",
        "window_start.gte": start_utc.isoformat(),
        "window_start.lt": end_utc.isoformat(),
        "limit": 50000,
        "sort": "window_start.asc",
        "apiKey": API_KEY,
    }

    try:
        r = requests.get(url, params=params, timeout=90)

        if r.status_code == 429:
            print(f"{ddate} | RATE LIMITED — keeping existing cache")
            continue

        if r.status_code != 200:
            print(f"{ddate} | API {r.status_code}")
            continue

        rows = r.json().get("results", [])

        out = []

        for x in rows:
            ts = x.get("window_start")

            if ts is None:
                continue

            out.append({
                "time_utc": pd.to_datetime(ts, unit="ns", utc=True),
                "ticker": ticker,
                "open": x.get("open"),
                "high": x.get("high"),
                "low": x.get("low"),
                "close": x.get("close"),
                "volume": x.get("volume"),
            })

        fresh = pd.DataFrame(out)

        if fresh.empty:
            print(f"{ddate} | no new data")
            continue

        fresh["time_ny"] = fresh["time_utc"].dt.tz_convert(TZ)

        fresh = fresh[
            fresh.time_ny.dt.date == ddate
        ].copy()

        if fresh.empty:
            print(f"{ddate} | no ET candles")
            continue

        # Cache successful API result.
        cache_path = (
            f"data/mnq_"
            f"{day.strftime('%b%d').lower()}_"
            f"{day.year}_full_et_1m.parquet"
        )

        fresh.to_parquet(cache_path, index=False)

        print(
            f"{ddate} | DOWNLOADED {len(fresh)} candles | "
            f"{fresh.time_ny.min().strftime('%H:%M')} - "
            f"{fresh.time_ny.max().strftime('%H:%M')} ET"
        )

        pieces.append(fresh[need])

    except Exception as e:
        print(f"{ddate} | DOWNLOAD ERROR:", e)

if not pieces:
    raise RuntimeError("No current-month market data available.")

month_data = (
    pd.concat(pieces, ignore_index=True)
    .drop_duplicates(["time_ny","ticker"], keep="last")
    .sort_values("time_ny")
    .reset_index(drop=True)
)

# Keep only this calendar month.
month_data = month_data[
    (month_data.time_ny.dt.year == today.year)
    & (month_data.time_ny.dt.month == today.month)
].copy()

latest_market_time = month_data.time_ny.max()

print("\nCurrent month assembled:")
print("Candles:", len(month_data))
print("First:", month_data.time_ny.min())
print("Last: ", latest_market_time)

# Historical tail supplies ATR context before first downloaded candle.
hist = pd.read_parquet(HIST)
hist["time_ny"] = pd.to_datetime(hist["time_ny"])

need = ["time_ny","ticker","open","high","low","close","volume"]

if month_data.time_ny.dt.tz is not None and hist.time_ny.dt.tz is None:
    hist["time_ny"] = hist["time_ny"].dt.tz_localize(TZ)
elif month_data.time_ny.dt.tz is None and hist.time_ny.dt.tz is not None:
    month_data["time_ny"] = month_data["time_ny"].dt.tz_localize(TZ)

one = pd.concat(
    [
        hist[need][hist.time_ny < month_data.time_ny.min()].tail(300),
        month_data[need]
    ],
    ignore_index=True
)

one = (
    one.drop_duplicates(["time_ny","ticker"], keep="last")
    .sort_values("time_ny")
    .reset_index(drop=True)
)

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

# Original candidate-engine 3-minute ATR(20).
three_prev_close = three["close"].shift(1)

three_true_range = pd.concat(
    [
        three["high"] - three["low"],
        (three["high"] - three_prev_close).abs(),
        (three["low"] - three_prev_close).abs(),
    ],
    axis=1
).max(axis=1)

three["atr_20"] = three_true_range.rolling(20).mean()

three["upper_wick"] = three.high - three[["open","close"]].max(axis=1)
three["lower_wick"] = three[["open","close"]].min(axis=1) - three.low
three["session"] = three.time_ny.apply(session_name)

g = three[
    (three.time_ny >= pd.Timestamp(month_start.date(), tz=TZ))
    & three.session.notna()
].copy()

# ------------------------------------------------------------
# Candidate generation — same frozen Option 2A logic
# ------------------------------------------------------------

cands = []

# Session must reset every DATE + SESSION.
for (date, session), gg in g.groupby(
    [g.time_ny.dt.date, "session"], sort=False
):
    rh = rl = None

    for _, r in gg.iterrows():
        if rh is None:
            rh = float(r.high)
            rl = float(r.low)
            continue

        rng = float(r.high-r.low)

        if r.low < rl:
            cands.append({
                "time_ny": r.time_ny,
                "date": date,
                "session": session,
                "direction": "LONG",
                "ticker": r.ticker,
                "extreme": float(r.low),
                "atr": float(r.atr_20) if pd.notna(r.atr_20) else np.nan,
                "sweep_distance": float(rl - r.low),
                "wick_percent": float(r.lower_wick/rng) if rng > 0 else 0
            })

        if r.high > rh:
            cands.append({
                "time_ny": r.time_ny,
                "date": date,
                "session": session,
                "direction": "SHORT",
                "ticker": r.ticker,
                "extreme": float(r.high),
                "atr": float(r.atr_20) if pd.notna(r.atr_20) else np.nan,
                "sweep_distance": float(r.high - rh),
                "wick_percent": float(r.upper_wick/rng) if rng > 0 else 0
            })

        rh = max(rh, float(r.high))
        rl = min(rl, float(r.low))

if not cands:
    raise RuntimeError("No Option 2A candidates found this month.")

cand = pd.DataFrame(cands).sort_values("time_ny").reset_index(drop=True)

# Critical: next extreme is only relevant inside the same DATE/session/direction.
cand["next_same_extreme_time"] = cand.groupby(
    ["date","session","direction"]
).time_ny.shift(-1)

idx1 = pd.Series(one.index, index=one.time_ny).to_dict()

# ------------------------------------------------------------
# V15 FROZEN HISTORICAL ELIGIBILITY REFERENCE
# ------------------------------------------------------------
# Rebuild V15 exactly from the original V11 population.
V11_PATH = "data/v11_reversal_state_forensics.csv"

v15_allowed = None

if Path(V11_PATH).exists():
    ref = pd.read_csv(V11_PATH)
    ref["candidate_time"] = pd.to_datetime(ref["candidate_time"], utc=True)
    ref["candidate_time_et"] = ref["candidate_time"].dt.tz_convert(TZ)

    ref["reclaim_x_wick"] = (
        ref.early_reclaim_atr * ref.wick_percent
    )
    ref["close_x_reclaim"] = (
        ref.m2_close_pos * ref.early_reclaim_atr
    )
    ref["sweep_minus_reclaim"] = (
        ref.sweep_atr - ref.early_reclaim_atr
    )
    ref["impulse_minus_reclaim"] = (
        ref.reversal_impulse - ref.early_reclaim_atr
    )
    ref["quality_balance"] = (
        ref.rejection_quality
        * ref.impulse_to_reclaim
        / (1 + ref.reclaim_to_sweep)
    )

    parts = []

    for col, hi, weight in [
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
        rank = ref[col].rank(pct=True)
        component = rank if hi else 1-rank
        parts += [component] * weight

    ref["score"] = pd.concat(parts,axis=1).mean(axis=1)
    score_threshold = ref.score.quantile(.07)

    ref = ref[ref.score >= score_threshold].copy()

    ref["date_et"] = ref.candidate_time_et.dt.date
    ref = ref.sort_values("candidate_time_et").reset_index(drop=True)
    ref["trade_num_day"] = ref.groupby("date_et").cumcount()+1
    ref = ref[ref.trade_num_day <= 6].copy()

    v15_allowed = set(
        zip(
            ref.candidate_time_et.astype(str),
            ref.direction.astype(str)
        )
    )

    print(
        f"Frozen V15 reference loaded: {len(v15_allowed)} eligible trades"
    )
else:
    print(
        "WARNING: V11 reference missing — historical parity "
        "validation cannot be enforced."
    )

# ------------------------------------------------------------
# FORWARD V15 — frozen historical percentile reference
# ------------------------------------------------------------
# IMPORTANT:
# New candidates are scored against the ORIGINAL V11 distribution.
# We never re-rank against the current month, so the strategy does
# not drift as new trades arrive.

V15_SCORE_THRESHOLD = 0.145921011058

V15_SPEC = [
    ("rejection_quality",  1, 2),
    ("impulse_to_reclaim", 1, 2),
    ("reclaim_to_sweep",   0, 1),
    ("reversal_impulse",   1, 1),
    ("reclaim_x_wick",     0, 2),
    ("close_x_reclaim",    0, 2),
    ("sweep_minus_reclaim",1, 1),
    ("impulse_minus_reclaim",1,2),
    ("quality_balance",    1, 2),
]

def frozen_pct_rank(series, value):
    """
    Percentile rank against frozen V11 reference.

    Mirrors pandas average-rank behavior for ties:
    (number below + (ties + 1)/2) / N
    """
    a = pd.to_numeric(series, errors="coerce").dropna().to_numpy()

    if len(a) == 0 or not np.isfinite(value):
        return np.nan

    below = np.sum(a < value)
    ties = np.sum(a == value)

    if ties:
        rank = below + (ties + 1.0) / 2.0
    else:
        # New value inserted between historical observations.
        rank = below + 1.0

    rank = min(max(rank, 1.0), float(len(a)))

    return rank / float(len(a))


def forward_v15_score(features):
    if "ref" not in globals():
        return np.nan

    components = []

    for col, hi, weight in V15_SPEC:
        value = features.get(col, np.nan)

        pct = frozen_pct_rank(ref[col], value)

        if not np.isfinite(pct):
            return np.nan

        component = pct if hi else 1.0-pct

        components.extend([component] * weight)

    return float(np.mean(components))

trades = []

# Frozen Option 2A: first six V15-pass candidates per ET calendar day
# consume the daily slots BEFORE V27 is applied.
v15_slots_by_day = {}

for _, c in cand.iterrows():

    i = idx1.get(c.time_ny)

    if i is None or i < 20 or i+3 >= len(one):
        continue

    a = float(one.iloc[i].atr1)

    if not np.isfinite(a) or a <= 0:
        continue

    sg = 1 if c.direction == "LONG" else -1

    vals = {}

    for k in [1,2]:
        b = one.iloc[i+k]
        pre = one.iloc[max(0,i+k-5):i+k+1]

        vals[f"m{k}_move_atr"] = (
            (float(b.close)-float(one.iloc[i].close))/a*sg
        )

        vals[f"m{k}_body_atr"] = abs(float(b.close-b.open))/a

        cp = (
            (b.close-b.low)/(b.high-b.low)
            if b.high > b.low else .5
        )

        vals[f"m{k}_close_pos"] = float(
            cp if c.direction == "LONG" else 1-cp
        )

        vals[f"m{k}_dir_bars5"] = int(
            ((((pre.close-pre.open)*sg)>0)).sum()
        )

    # V7 BASE RULE — frozen
    if not (
        vals["m1_move_atr"] <= .300
        and vals["m1_close_pos"] >= .140
        and vals["m2_close_pos"] <= .912
    ):
        continue

    first2 = one.iloc[i+1:i+3]

    if c.direction == "LONG":
        adverse = (float(c.extreme)-float(first2.low.min()))/a
        reclaim = (
            float(first2.iloc[-1].close)-float(c.extreme)
        )/a
    else:
        adverse = (
            float(first2.high.max())-float(c.extreme)
        )/a
        reclaim = (
            float(c.extreme)-float(first2.iloc[-1].close)
        )/a

    # --------------------------------------------------------
    # V8 HARD ELIGIBILITY FILTERS — frozen
    # --------------------------------------------------------
    if not (
        reclaim <= .90
        and vals["m2_close_pos"] <= .80
        and float(c.wick_percent) <= .60
        and vals["m2_move_atr"] <= .15
        and vals["m2_dir_bars5"] <= 4
    ):
        continue

    # --------------------------------------------------------
    # V11 FEATURES REQUIRED BY V15
    # --------------------------------------------------------

    rejection_quality = (
        (1-min(max(vals["m2_close_pos"],0),1))
        *
        (1-min(max(float(c.wick_percent),0),1))
    )

    reversal_impulse = -vals["m2_move_atr"]

    # Exact original candidate-generator sweep calculation.
    # sweep_distance was captured against the running session
    # extreme BEFORE that extreme was updated.
    # V15 sweep_atr uses the candidate's ORIGINAL 3-minute ATR.
    # Do NOT use `a` here: `a` is the 1-minute ATR required by
    # the V7 m1/m2 feature calculations above.
    candidate_atr = float(c.atr)

    sweep_atr = (
        float(c.sweep_distance) / candidate_atr
        if np.isfinite(candidate_atr) and candidate_atr > 0
        else np.nan
    )

    # If this candidate exists in frozen V11, use its exact original
    # sweep_atr. This preserves exact historical parity.
    historical_ref_row = None

    if "ref" in globals():
        exact_ref = ref[
            (ref["candidate_time_et"].astype(str) == str(c.time_ny))
            & (ref["direction"].astype(str) == str(c.direction))
        ]

        if len(exact_ref):
            historical_ref_row = exact_ref.iloc[0]

            if (
                "sweep_atr" in historical_ref_row.index
                and pd.notna(historical_ref_row["sweep_atr"])
            ):
                sweep_atr = float(historical_ref_row["sweep_atr"])

    reclaim_to_sweep = reclaim/(abs(sweep_atr)+.05)

    impulse_to_reclaim = (
        reversal_impulse/(abs(reclaim)+.05)
    )

    reclaim_x_wick = (
        reclaim * float(c.wick_percent)
    )

    close_x_reclaim = (
        vals["m2_close_pos"] * reclaim
    )

    sweep_minus_reclaim = (
        sweep_atr-reclaim
    )

    impulse_minus_reclaim = (
        reversal_impulse-reclaim
    )

    quality_balance = (
        rejection_quality
        * impulse_to_reclaim
        / (1+reclaim_to_sweep)
    )

    v15_features = {
        "rejection_quality": rejection_quality,
        "impulse_to_reclaim": impulse_to_reclaim,
        "reclaim_to_sweep": reclaim_to_sweep,
        "reversal_impulse": reversal_impulse,
        "reclaim_x_wick": reclaim_x_wick,
        "close_x_reclaim": close_x_reclaim,
        "sweep_minus_reclaim": sweep_minus_reclaim,
        "impulse_minus_reclaim": impulse_minus_reclaim,
        "quality_balance": quality_balance,
    }

    # --------------------------------------------------------
    # V15 ELIGIBILITY
    # --------------------------------------------------------

    key = (str(c.time_ny), str(c.direction))

    historical_candidate = False

    if v15_allowed is not None:
        all_ref_dates = ref["candidate_time_et"].dt.date

        if len(all_ref_dates):
            historical_candidate = (
                c.time_ny.date() <= max(all_ref_dates)
            )

    if historical_candidate:
        # Exact historical V15 decision.
        if key not in v15_allowed:
            continue

        v15_score = (
            float(historical_ref_row["score"])
            if historical_ref_row is not None
            and "score" in historical_ref_row.index
            else np.nan
        )

    else:
        # New candidate: score against frozen V11 distribution.
        v15_score = forward_v15_score(v15_features)

        if not np.isfinite(v15_score):
            continue

        if v15_score < V15_SCORE_THRESHOLD:
            continue

    # --------------------------------------------------------
    # FROZEN 6/DAY CAP — AFTER V15, BEFORE V27
    # --------------------------------------------------------
    date_et = c.time_ny.date()
    slot_num = v15_slots_by_day.get(date_et, 0) + 1
    v15_slots_by_day[date_et] = slot_num

    # Temporary Sep 23 audit: show every V15 survivor, including
    # candidates later blocked by the six/day cap or V27.
    rw = reclaim * float(c.wick_percent)
    v27_pass = not (reclaim >= RTH and rw >= WTH)


    if slot_num > 6:
        continue

    # --------------------------------------------------------
    # V27 OPTION 2A — frozen thresholds
    # --------------------------------------------------------

    if not v27_pass:
        continue

    j = i+3
    signal = one.iloc[j].time_ny

    if (
        pd.notna(c.next_same_extreme_time)
        and signal >= c.next_same_extreme_time
    ):
        continue

    if one.iloc[j].ticker != c.ticker:
        continue

    entry = float(one.iloc[j].open)

    stop = (
        float(c.extreme)-.25
        if c.direction == "LONG"
        else float(c.extreme)+.25
    )

    risk = (
        entry-stop
        if c.direction == "LONG"
        else stop-entry
    )

    if risk <= 0:
        continue

    outcomes = {}

    for rr in range(1,7):

        target = (
            entry + rr*risk
            if c.direction == "LONG"
            else entry - rr*risk
        )

        outcome = "OPEN"

        for q in range(j, min(j+241, len(one))):

            b = one.iloc[q]

            if b.ticker != c.ticker:
                break

            stop_hit = (
                float(b.low) <= stop
                if c.direction == "LONG"
                else float(b.high) >= stop
            )

            target_hit = (
                float(b.high) >= target
                if c.direction == "LONG"
                else float(b.low) <= target
            )

            # Canonical conservative ordering: stop first.
            if stop_hit:
                outcome = "LOSS"
                break

            if target_hit:
                outcome = "WIN"
                break

        outcomes[f"{rr}R"] = outcome

    trades.append({
        "date": signal.date().isoformat(),
        "session": c.session,
        "candidate_time": c.time_ny,
        "entry_time": signal,
        "direction": c.direction,
        "entry": entry,
        "stop": stop,
        "risk_points": risk,
        **outcomes
    })

tr = pd.DataFrame(trades)

if tr.empty:
    raise RuntimeError("No frozen Option 2A trades found this month.")

# ------------------------------------------------------------
# DAILY REPORT
# OPEN outcomes are NOT counted as losses.
# ------------------------------------------------------------

daily_rows = []

for date, x in tr.groupby("date", sort=True):

    row = {
        "Date": date,
        "Trades": len(x)
    }

    for rr in range(1,7):

        s = x[f"{rr}R"]

        w = int((s=="WIN").sum())
        l = int((s=="LOSS").sum())
        o = int((s=="OPEN").sum())

        resolved = w+l

        wr = (
            100*w/resolved
            if resolved else np.nan
        )

        pnl = (
            w*(rr*RISK_DOLLARS)
            - l*RISK_DOLLARS
        )

        row[f"{rr}R Wins"] = w
        row[f"{rr}R Losses"] = l
        row[f"{rr}R Open"] = o
        row[f"{rr}R WR"] = wr
        row[f"{rr}R PnL"] = pnl

    daily_rows.append(row)

daily = pd.DataFrame(daily_rows)

# Keep zero-trade market dates visible in the daily report.
# This changes reporting only — never strategy selection or P&L logic.
market_dates = sorted(
    pd.Series(month_data.loc[month_data.time_ny <= latest_market_time, "time_ny"].dt.date)
    .drop_duplicates()
    .astype(str)
    .tolist()
)
reported_dates = set(daily["Date"].astype(str)) if not daily.empty else set()
zero_rows = []
for d in market_dates:
    if d in reported_dates:
        continue
    row = {"Date": d, "Trades": 0}
    for rr in range(1,7):
        row[f"{rr}R Wins"] = 0
        row[f"{rr}R Losses"] = 0
        row[f"{rr}R Open"] = 0
        row[f"{rr}R WR"] = np.nan
        row[f"{rr}R PnL"] = 0
    zero_rows.append(row)

if zero_rows:
    daily = pd.concat([daily, pd.DataFrame(zero_rows)], ignore_index=True)
    daily["_sort_date"] = pd.to_datetime(daily["Date"], errors="coerce")
    daily = daily.sort_values("_sort_date").drop(columns="_sort_date").reset_index(drop=True)

# MONTH TOTAL
total = {
    "Date": "MONTH TOTAL",
    "Trades": len(tr)
}

for rr in range(1,7):

    s = tr[f"{rr}R"]

    w = int((s=="WIN").sum())
    l = int((s=="LOSS").sum())
    o = int((s=="OPEN").sum())

    resolved = w+l

    total[f"{rr}R Wins"] = w
    total[f"{rr}R Losses"] = l
    total[f"{rr}R Open"] = o
    total[f"{rr}R WR"] = (
        100*w/resolved if resolved else np.nan
    )
    total[f"{rr}R PnL"] = (
        w*(rr*RISK_DOLLARS)
        - l*RISK_DOLLARS
    )

daily = pd.concat(
    [daily, pd.DataFrame([total])],
    ignore_index=True
)

tag = now.strftime("%Y-%m")

trade_path = f"data/reports/{tag}_trades.csv"
daily_path = f"data/reports/{tag}_daily_report.csv"

tr.to_csv(trade_path, index=False)
daily.to_csv(daily_path, index=False)

# Compact screen table
display_cols = ["Date","Trades"]

for rr in range(1,7):
    display_cols += [f"{rr}R WR",f"{rr}R PnL"]

print("\n============================================================")
print("DATA AVAILABLE THROUGH:")
print(latest_market_time)
print("============================================================")

print(
    daily[display_cols]
    .round(2)
    .to_string(index=False)
)

print("\nSaved:")
print(trade_path)
print(daily_path)

print("\nNOTE:")
print("OPEN = outcome not yet resolved in available market data.")
print("OPEN trades are NOT counted as losses or included in WR.")
print("Re-run this same command later to update today's results.")
