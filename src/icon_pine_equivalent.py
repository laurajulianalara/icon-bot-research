import pandas as pd
import numpy as np

# ============================================================
# THE ICON — PINE-EQUIVALENT PARITY ENGINE
# Frozen Option 2A
# Validation window: Sep 1-17, 2026
# ============================================================

TZ = "America/New_York"

ONE_PATH = "data/mnq_continuous_1m.parquet"
MASTER_PATH = "data/ICON_MASTER_1911_TRADE_LEVEL.csv"
V11_PATH = "data/v11_reversal_state_forensics.csv"

START = pd.Timestamp("2026-09-01 00:00:00", tz=TZ)
END   = pd.Timestamp("2026-09-18 00:00:00", tz=TZ)

RTH = 0.576132
WTH = 0.183258
V15_SCORE_THRESHOLD = 0.145921011058


# ============================================================
# SESSION ENGINE
# ============================================================

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


# ============================================================
# FROZEN V15 PERCENTILE ENGINE
# ============================================================

V15_SPEC = [
    ("rejection_quality", 1, 2),
    ("impulse_to_reclaim", 1, 2),
    ("reclaim_to_sweep", 0, 1),
    ("reversal_impulse", 1, 1),
    ("reclaim_x_wick", 0, 2),
    ("close_x_reclaim", 0, 2),
    ("sweep_minus_reclaim", 1, 1),
    ("impulse_minus_reclaim", 1, 2),
    ("quality_balance", 1, 2),
]


def frozen_pct_rank(series, value):

    a = (
        pd.to_numeric(series, errors="coerce")
        .dropna()
        .to_numpy()
    )

    if len(a) == 0 or not np.isfinite(value):
        return np.nan

    below = np.sum(a < value)
    ties = np.sum(a == value)

    if ties:
        rank = below + (ties + 1.0) / 2.0
    else:
        rank = below + 1.0

    rank = min(max(rank, 1.0), float(len(a)))

    return rank / float(len(a))


def forward_v15_score(ref, features):

    components = []

    for col, hi, weight in V15_SPEC:

        value = features.get(col, np.nan)
        pct = frozen_pct_rank(ref[col], value)

        if not np.isfinite(pct):
            return np.nan

        component = pct if hi else 1.0 - pct

        components.extend([component] * weight)

    return float(np.mean(components))


# ============================================================
# LOAD 1-MINUTE DATA
# ============================================================

one = pd.read_parquet(ONE_PATH).copy()
one["time_ny"] = pd.to_datetime(one["time_ny"])

if one.time_ny.dt.tz is None:
    one["time_ny"] = one.time_ny.dt.tz_localize(TZ)
else:
    one["time_ny"] = one.time_ny.dt.tz_convert(TZ)

one = (
    one.sort_values("time_ny")
    .reset_index(drop=True)
)

# Keep enough pre-window history for ATR/resampling context.
one = one[
    (one.time_ny >= START - pd.Timedelta(days=3))
    & (one.time_ny < END)
].copy().reset_index(drop=True)

# Original 1-minute ATR(20).
one["atr1"] = pd.concat(
    [
        one.high - one.low,
        (one.high - one.close.shift()).abs(),
        (one.low - one.close.shift()).abs(),
    ],
    axis=1,
).max(axis=1).rolling(20).mean()


# ============================================================
# BUILD 3-MINUTE CANDLES FROM 1-MINUTE DATA
# Pine-equivalent data path.
# ============================================================

z = one.set_index("time_ny")

three = z.resample(
    "3min",
    label="left",
    closed="left"
).agg(
    ticker=("ticker", "last"),
    open=("open", "first"),
    high=("high", "max"),
    low=("low", "min"),
    close=("close", "last"),
    volume=("volume", "sum"),
).dropna(
    subset=["open", "high", "low", "close"]
).reset_index()

three_prev_close = three["close"].shift(1)

three_true_range = pd.concat(
    [
        three["high"] - three["low"],
        (three["high"] - three_prev_close).abs(),
        (three["low"] - three_prev_close).abs(),
    ],
    axis=1,
).max(axis=1)

three["atr_20"] = three_true_range.rolling(20).mean()

three["upper_wick"] = (
    three.high - three[["open", "close"]].max(axis=1)
)

three["lower_wick"] = (
    three[["open", "close"]].min(axis=1) - three.low
)

three["session"] = three.time_ny.apply(session_name)


# ============================================================
# CANDIDATE ENGINE
# Running session extremes — NO pivots.
# ============================================================

g = three[
    (three.time_ny >= START)
    & (three.time_ny < END)
    & three.session.notna()
].copy()

cands = []

for (date, session), gg in g.groupby(
    [g.time_ny.dt.date, "session"],
    sort=False,
):

    rh = None
    rl = None

    for _, r in gg.iterrows():

        if rh is None:
            rh = float(r.high)
            rl = float(r.low)
            continue

        rng = float(r.high - r.low)

        if r.low < rl:

            cands.append({
                "time_ny": r.time_ny,
                "date": date,
                "session": session,
                "direction": "LONG",
                "ticker": r.ticker,
                "extreme": float(r.low),
                "atr": (
                    float(r.atr_20)
                    if pd.notna(r.atr_20)
                    else np.nan
                ),
                "sweep_distance": float(rl - r.low),
                "wick_percent": (
                    float(r.lower_wick / rng)
                    if rng > 0
                    else 0.0
                ),
            })

        if r.high > rh:

            cands.append({
                "time_ny": r.time_ny,
                "date": date,
                "session": session,
                "direction": "SHORT",
                "ticker": r.ticker,
                "extreme": float(r.high),
                "atr": (
                    float(r.atr_20)
                    if pd.notna(r.atr_20)
                    else np.nan
                ),
                "sweep_distance": float(r.high - rh),
                "wick_percent": (
                    float(r.upper_wick / rng)
                    if rng > 0
                    else 0.0
                ),
            })

        rh = max(rh, float(r.high))
        rl = min(rl, float(r.low))


cand = (
    pd.DataFrame(cands)
    .sort_values("time_ny")
    .reset_index(drop=True)
)

cand["next_same_extreme_time"] = cand.groupby(
    ["date", "session", "direction"]
).time_ny.shift(-1)

print("\nCANDIDATES:", len(cand))


# ============================================================
# LOAD FROZEN V11 REFERENCE
# Rebuild exact historical V15 membership.
# ============================================================

ref = pd.read_csv(V11_PATH)

ref["candidate_time"] = pd.to_datetime(
    ref["candidate_time"],
    utc=True
)

ref["candidate_time_et"] = (
    ref["candidate_time"]
    .dt.tz_convert(TZ)
)

ref["reclaim_x_wick"] = (
    ref.early_reclaim_atr
    * ref.wick_percent
)

ref["close_x_reclaim"] = (
    ref.m2_close_pos
    * ref.early_reclaim_atr
)

ref["sweep_minus_reclaim"] = (
    ref.sweep_atr
    - ref.early_reclaim_atr
)

ref["impulse_minus_reclaim"] = (
    ref.reversal_impulse
    - ref.early_reclaim_atr
)

ref["quality_balance"] = (
    ref.rejection_quality
    * ref.impulse_to_reclaim
    / (1 + ref.reclaim_to_sweep)
)

parts = []

for col, hi, weight in V15_SPEC:

    rank = ref[col].rank(pct=True)
    component = rank if hi else 1-rank

    parts += [component] * weight

ref["score"] = pd.concat(
    parts,
    axis=1
).mean(axis=1)

historical_threshold = ref.score.quantile(.07)

ref_allowed = ref[
    ref.score >= historical_threshold
].copy()

ref_allowed["date_et"] = (
    ref_allowed.candidate_time_et.dt.date
)

ref_allowed = (
    ref_allowed
    .sort_values("candidate_time_et")
    .reset_index(drop=True)
)

ref_allowed["trade_num_day"] = (
    ref_allowed.groupby("date_et")
    .cumcount() + 1
)

ref_allowed = ref_allowed[
    ref_allowed.trade_num_day <= 6
].copy()

v15_allowed = set(
    zip(
        ref_allowed.candidate_time_et.astype(str),
        ref_allowed.direction.astype(str),
    )
)

ref_lookup = {}

for _, r in ref.iterrows():
    ref_lookup[
        (str(r.candidate_time_et), str(r.direction))
    ] = r


# ============================================================
# TRADE SELECTION ENGINE
# ============================================================

idx1 = pd.Series(
    one.index,
    index=one.time_ny
).to_dict()

selected = []

for _, c in cand.iterrows():

    i = idx1.get(c.time_ny)

    if i is None or i < 20 or i+3 >= len(one):
        continue

    a = float(one.iloc[i].atr1)

    if not np.isfinite(a) or a <= 0:
        continue

    sg = 1 if c.direction == "LONG" else -1

    vals = {}

    for k in [1, 2]:

        b = one.iloc[i+k]
        pre = one.iloc[max(0, i+k-5):i+k+1]

        vals[f"m{k}_move_atr"] = (
            (float(b.close) - float(one.iloc[i].close))
            / a * sg
        )

        vals[f"m{k}_body_atr"] = (
            abs(float(b.close - b.open)) / a
        )

        cp = (
            (b.close-b.low)/(b.high-b.low)
            if b.high > b.low
            else .5
        )

        vals[f"m{k}_close_pos"] = float(
            cp if c.direction == "LONG"
            else 1-cp
        )

        vals[f"m{k}_dir_bars5"] = int(
            ((((pre.close-pre.open)*sg) > 0)).sum()
        )

    # ---------------- V7 ----------------

    if not (
        vals["m1_move_atr"] <= .300
        and vals["m1_close_pos"] >= .140
        and vals["m2_close_pos"] <= .912
    ):
        continue

    first2 = one.iloc[i+1:i+3]

    if c.direction == "LONG":

        adverse = (
            float(c.extreme)
            - float(first2.low.min())
        ) / a

        reclaim = (
            float(first2.iloc[-1].close)
            - float(c.extreme)
        ) / a

    else:

        adverse = (
            float(first2.high.max())
            - float(c.extreme)
        ) / a

        reclaim = (
            float(c.extreme)
            - float(first2.iloc[-1].close)
        ) / a

    # ---------------- V8 ----------------

    if not (
        reclaim <= .90
        and vals["m2_close_pos"] <= .80
        and float(c.wick_percent) <= .60
        and vals["m2_move_atr"] <= .15
        and vals["m2_dir_bars5"] <= 4
    ):
        continue

    # ---------------- V11 / V15 ----------------

    rejection_quality = (
        (1-min(max(vals["m2_close_pos"], 0), 1))
        *
        (1-min(max(float(c.wick_percent), 0), 1))
    )

    reversal_impulse = -vals["m2_move_atr"]

    candidate_atr = float(c.atr)

    sweep_atr = (
        float(c.sweep_distance) / candidate_atr
        if np.isfinite(candidate_atr)
        and candidate_atr > 0
        else np.nan
    )

    key = (
        str(c.time_ny),
        str(c.direction)
    )

    historical_ref_row = ref_lookup.get(key)

    if (
        historical_ref_row is not None
        and pd.notna(historical_ref_row["sweep_atr"])
    ):
        sweep_atr = float(
            historical_ref_row["sweep_atr"]
        )

    reclaim_to_sweep = (
        reclaim / (abs(sweep_atr)+.05)
    )

    impulse_to_reclaim = (
        reversal_impulse / (abs(reclaim)+.05)
    )

    reclaim_x_wick = (
        reclaim * float(c.wick_percent)
    )

    close_x_reclaim = (
        vals["m2_close_pos"] * reclaim
    )

    sweep_minus_reclaim = (
        sweep_atr - reclaim
    )

    impulse_minus_reclaim = (
        reversal_impulse - reclaim
    )

    quality_balance = (
        rejection_quality
        * impulse_to_reclaim
        / (1 + reclaim_to_sweep)
    )

    features = {
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

    # Historical parity decision.
    if key not in v15_allowed:
        continue

    # ---------------- V27 ----------------

    if (
        reclaim >= RTH
        and reclaim_x_wick >= WTH
    ):
        continue

    # ---------------- T+3 ----------------

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

    selected.append({
        "candidate_time": c.time_ny,
        "entry_time": signal,
        "session": c.session,
        "direction": c.direction,
        "entry": entry,
        "stop": stop,
        "risk": risk,
    })


pine = pd.DataFrame(selected)

print("SELECTED:", len(pine))


# ============================================================
# AUTHORITATIVE FROZEN MASTER
# ============================================================

master = pd.read_csv(MASTER_PATH)

master["candidate_time"] = pd.to_datetime(
    master["candidate_time"],
    utc=True
).dt.tz_convert(TZ)

master["entry_time"] = pd.to_datetime(
    master["entry_time"],
    utc=True
).dt.tz_convert(TZ)

master = master[
    (master.candidate_time >= START)
    & (master.candidate_time < END)
].copy()

master = (
    master.sort_values(
        ["candidate_time", "direction"]
    )
    .reset_index(drop=True)
)

pine = (
    pine.sort_values(
        ["candidate_time", "direction"]
    )
    .reset_index(drop=True)
)


# ============================================================
# PARITY COMPARISON
# ============================================================

master_keys = set(
    zip(
        master.candidate_time.astype(str),
        master.direction.astype(str),
    )
)

pine_keys = set(
    zip(
        pine.candidate_time.astype(str),
        pine.direction.astype(str),
    )
)

matched_keys = master_keys & pine_keys
missing_keys = master_keys - pine_keys
extra_keys = pine_keys - master_keys

print("\n============================================================")
print("THE ICON — PINE EQUIVALENT PARITY")
print("============================================================")
print("EXPECTED:", len(master))
print("PINE LOGIC:", len(pine))
print("MATCHED:", len(matched_keys))
print("MISSING:", len(missing_keys))
print("EXTRA:", len(extra_keys))


# Exact field comparison for matched trades.
cmp = master.merge(
    pine,
    on=["candidate_time", "direction"],
    how="inner",
    suffixes=("_master", "_pine"),
)

entry_time_ok = (
    cmp.entry_time_master
    == cmp.entry_time_pine
)

entry_ok = np.isclose(
    cmp.entry_master,
    cmp.entry_pine,
    atol=1e-9
)

stop_ok = np.isclose(
    cmp.stop_master,
    cmp.stop_pine,
    atol=1e-9
)

risk_ok = np.isclose(
    cmp.risk_master,
    cmp.risk_pine,
    atol=1e-9
)

print("\nFIELD PARITY")
print(
    "ENTRY TIME:",
    f"{entry_time_ok.sum()}/{len(cmp)}"
)

print(
    "ENTRY PRICE:",
    f"{entry_ok.sum()}/{len(cmp)}"
)

print(
    "STOP:",
    f"{stop_ok.sum()}/{len(cmp)}"
)

print(
    "RISK:",
    f"{risk_ok.sum()}/{len(cmp)}"
)


# ============================================================
# MISMATCH DETAILS
# ============================================================

if missing_keys:

    print("\nMISSING TRADES:")

    for k in sorted(missing_keys):
        print(k)

if extra_keys:

    print("\nEXTRA TRADES:")

    for k in sorted(extra_keys):
        print(k)


all_ok = (
    len(master) == len(pine)
    and len(matched_keys) == len(master)
    and not missing_keys
    and not extra_keys
    and entry_time_ok.all()
    and entry_ok.all()
    and stop_ok.all()
    and risk_ok.all()
)

print("\n============================================================")

if all_ok:
    print("✅ PASS — 100% FROZEN STRATEGY PARITY")
else:
    print("❌ FAIL — PARITY MISMATCH")

print("============================================================")

pine.to_csv(
    "data/icon_pine_equivalent_sep1_sep17.csv",
    index=False
)
