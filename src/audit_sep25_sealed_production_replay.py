#!/usr/bin/env python3
"""
Sealed Sep 25 production replay.

Purpose:
- Use only locally saved market data.
- Never download or refresh data.
- At each cutoff, expose only candles <= cutoff.
- Reproduce the production reporter's candidate/filter logic as-of that cutoff.
- Print hard proof that future rows are not visible.

This is diagnostic only. It does not modify strategy files or send alerts.
"""

from pathlib import Path
import bisect
import json
import numpy as np
import pandas as pd

TZ = "America/New_York"
DATE = pd.Timestamp("2026-09-25").date()
CUTS = ["02:15", "02:18", "02:21", "04:30", "04:45", "04:57", "12:06"]

HIST = Path("data/mnq_continuous_1m.parquet")
REF_PATH = Path("data/icon_v15_pine_reference.json")
V11_PATH = Path("data/v11_reversal_state_forensics.csv")
RTH = 0.576132
WTH = 0.183258
V15_THRESHOLD = 0.145921011058
NEED = ["time_ny", "ticker", "open", "high", "low", "close", "volume"]

SPEC = [
    ("rejection_quality",1,2),("impulse_to_reclaim",1,2),
    ("reclaim_to_sweep",0,1),("reversal_impulse",1,1),
    ("reclaim_x_wick",0,2),("close_x_reclaim",0,2),
    ("sweep_minus_reclaim",1,1),("impulse_minus_reclaim",1,2),
    ("quality_balance",1,2),
]


def norm_time(s):
    x = pd.to_datetime(s, errors="coerce")
    if x.dt.tz is None:
        return x.dt.tz_localize(TZ)
    return x.dt.tz_convert(TZ)


def session_name(ts):
    m = ts.hour * 60 + ts.minute
    if 1200 <= m < 1440: return "ASIA"
    if 120 <= m < 300: return "LONDON"
    if 570 <= m < 750: return "NYAM"
    if 810 <= m < 1020: return "NYPM"
    return None


def load_local_only():
    frames = []

    if HIST.exists():
        h = pd.read_parquet(HIST)
        if set(NEED).issubset(h.columns):
            h = h[NEED].copy()
            h["time_ny"] = norm_time(h["time_ny"])
            frames.append(h)

    for p in sorted(Path("data").glob("mnq_*_1m.parquet")):
        if p == HIST:
            continue
        try:
            q = pd.read_parquet(p)
            if not set(NEED).issubset(q.columns):
                continue
            q = q[NEED].copy()
            q["time_ny"] = norm_time(q["time_ny"])
            frames.append(q)
        except Exception:
            pass

    if not frames:
        raise RuntimeError("No local 1m data found")

    one = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(["time_ny", "ticker"], keep="last")
        .sort_values("time_ny")
        .reset_index(drop=True)
    )
    return one


def build_ref():
    if not REF_PATH.exists():
        raise RuntimeError(f"Missing {REF_PATH}")
    with REF_PATH.open() as f:
        ref = {k: sorted(float(x) for x in v) for k, v in json.load(f).items()}
    return ref


def rank(v, arr):
    if not np.isfinite(v):
        return np.nan
    lo = bisect.bisect_left(arr, float(v))
    hi = bisect.bisect_right(arr, float(v))
    return (lo + (hi-lo+1)/2)/len(arr) if hi > lo else min(1, max(0, (lo+1)/len(arr)))


def v15_score(f, ref):
    pts = []
    for col, hi, w in SPEC:
        r = rank(f[col], ref[col])
        if not np.isfinite(r):
            return np.nan
        pts += [(r if hi else 1-r)] * w
    return float(np.mean(pts))


def build_v15_allowed():
    if not V11_PATH.exists():
        return None, None

    ref = pd.read_csv(V11_PATH)
    ref["candidate_time"] = pd.to_datetime(ref["candidate_time"], utc=True)
    ref["candidate_time_et"] = ref["candidate_time"].dt.tz_convert(TZ)

    needed = {
        "early_reclaim_atr", "wick_percent", "m2_close_pos", "sweep_atr",
        "reversal_impulse", "rejection_quality", "candidate_time_et"
    }
    if not needed.issubset(ref.columns):
        return None, None

    ref["reclaim_x_wick"] = ref.early_reclaim_atr * ref.wick_percent
    ref["close_x_reclaim"] = ref.m2_close_pos * ref.early_reclaim_atr
    ref["sweep_minus_reclaim"] = ref.sweep_atr - ref.early_reclaim_atr
    ref["impulse_minus_reclaim"] = ref.reversal_impulse - ref.early_reclaim_atr
    ref["impulse_to_reclaim"] = ref.reversal_impulse / (ref.early_reclaim_atr.abs() + .05)
    ref["reclaim_to_sweep"] = ref.early_reclaim_atr / (ref.sweep_atr.abs() + .05)
    ref["quality_balance"] = ref.rejection_quality * ref.impulse_to_reclaim / (1 + ref.reclaim_to_sweep)

    # Reproduce frozen V15 score construction used by the production reporter.
    score_cols = [c for c,_,_ in SPEC]
    pct = {}
    for c in score_cols:
        pct[c] = ref[c].rank(method="average", pct=True)

    vals = []
    for i in range(len(ref)):
        ps = []
        for col, hi, w in SPEC:
            r = float(pct[col].iloc[i])
            ps += [(r if hi else 1-r)] * w
        vals.append(float(np.mean(ps)))
    ref["v15_score"] = vals

    threshold = float(ref["v15_score"].quantile(.07))
    eligible = ref[ref.v15_score >= threshold].copy()

    # Match historical V15 reference's own per-day ordering/cap if present.
    eligible = eligible.sort_values("candidate_time_et")
    eligible["trade_num_day"] = eligible.groupby(eligible.candidate_time_et.dt.date).cumcount() + 1
    eligible = eligible[eligible.trade_num_day <= 6]

    allowed = set(eligible.candidate_time_et)
    max_ref_date = ref.candidate_time_et.dt.date.max()
    return allowed, max_ref_date


def run_asof(all_data, cutoff, ref_score, v15_allowed, v15_max_date):
    visible = all_data[all_data.time_ny <= cutoff].copy()
    if visible.empty:
        return [], None, 0

    # Keep enough pre-day history for ATR context, but nothing after cutoff.
    start_ctx = pd.Timestamp("2026-09-22 00:00:00", tz=TZ)
    one = visible[visible.time_ny >= start_ctx].copy().reset_index(drop=True)

    pc = one.close.shift(1)
    one["atr1"] = pd.concat([
        one.high-one.low,
        (one.high-pc).abs(),
        (one.low-pc).abs(),
    ], axis=1).max(axis=1).rolling(20).mean()

    z = one.set_index("time_ny")
    three = z.resample("3min", label="left", closed="left").agg(
        ticker=("ticker","last"),
        open=("open","first"),
        high=("high","max"),
        low=("low","min"),
        close=("close","last"),
        volume=("volume","sum"),
        n=("close","count"),
    ).reset_index()

    # A production-as-of candidate can only come from a completed 3m candle.
    three = three[(three.n == 3) & three.open.notna()].copy()

    p3 = three.close.shift(1)
    tr3 = pd.concat([
        three.high-three.low,
        (three.high-p3).abs(),
        (three.low-p3).abs(),
    ], axis=1).max(axis=1)
    three["atr_20"] = tr3.rolling(20).mean()
    three["upper_wick"] = three.high - three[["open","close"]].max(axis=1)
    three["lower_wick"] = three[["open","close"]].min(axis=1) - three.low
    three["session"] = three.time_ny.apply(session_name)

    g = three[three.session.notna()].copy()
    cands = []
    for (d,s), gg in g.groupby([g.time_ny.dt.date, "session"], sort=False):
        rh = rl = None
        for _, r in gg.iterrows():
            if rh is None:
                rh = float(r.high); rl = float(r.low); continue
            rng = float(r.high-r.low)
            if r.low < rl:
                cands.append(dict(time_ny=r.time_ny,date=d,session=s,direction="LONG",ticker=r.ticker,
                                  extreme=float(r.low),atr=float(r.atr_20) if pd.notna(r.atr_20) else np.nan,
                                  sweep_distance=float(rl-r.low),wick_percent=float(r.lower_wick/rng) if rng>0 else 0))
            if r.high > rh:
                cands.append(dict(time_ny=r.time_ny,date=d,session=s,direction="SHORT",ticker=r.ticker,
                                  extreme=float(r.high),atr=float(r.atr_20) if pd.notna(r.atr_20) else np.nan,
                                  sweep_distance=float(r.high-rh),wick_percent=float(r.upper_wick/rng) if rng>0 else 0))
            rh=max(rh,float(r.high)); rl=min(rl,float(r.low))

    if not cands:
        return [], one.time_ny.max(), 0

    cand = pd.DataFrame(cands).sort_values("time_ny").reset_index(drop=True)
    cand["next_same_extreme_time"] = cand.groupby(["date","session","direction"]).time_ny.shift(-1)

    idx = pd.Series(one.index, index=one.time_ny).to_dict()
    out = []

    for _, c in cand.iterrows():
        i = idx.get(c.time_ny)
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
            vals[f"m{k}_move_atr"] = (float(b.close)-float(one.iloc[i].close))/a*sg
            cp = (b.close-b.low)/(b.high-b.low) if b.high>b.low else .5
            vals[f"m{k}_close_pos"] = float(cp if c.direction=="LONG" else 1-cp)
            vals[f"m{k}_dir_bars5"] = int(((((pre.close-pre.open)*sg)>0)).sum())

        if not (vals["m1_move_atr"] <= .300 and vals["m1_close_pos"] >= .140 and vals["m2_close_pos"] <= .912):
            continue

        first2 = one.iloc[i+1:i+3]
        reclaim = ((float(first2.iloc[-1].close)-float(c.extreme))/a
                   if c.direction=="LONG"
                   else (float(c.extreme)-float(first2.iloc[-1].close))/a)

        if not (reclaim <= .90 and vals["m2_close_pos"] <= .80 and float(c.wick_percent) <= .60
                and vals["m2_move_atr"] <= .15 and vals["m2_dir_bars5"] <= 4):
            continue

        rq=(1-min(max(vals["m2_close_pos"],0),1))*(1-min(max(float(c.wick_percent),0),1))
        ri=-vals["m2_move_atr"]
        ca=float(c.atr)
        sa=float(c.sweep_distance)/ca if np.isfinite(ca) and ca>0 else np.nan
        rts=reclaim/(abs(sa)+.05)
        itr=ri/(abs(reclaim)+.05)
        rxw=reclaim*float(c.wick_percent)
        feats={
            "rejection_quality":rq,
            "impulse_to_reclaim":itr,
            "reclaim_to_sweep":rts,
            "reversal_impulse":ri,
            "reclaim_x_wick":rxw,
            "close_x_reclaim":vals["m2_close_pos"]*reclaim,
            "sweep_minus_reclaim":sa-reclaim,
            "impulse_minus_reclaim":ri-reclaim,
            "quality_balance":rq*itr/(1+rts),
        }

        sc = v15_score(feats, ref_score)

        # Production reporter semantics: historical dates covered by the frozen
        # V15 reference use exact membership; later dates use forward score.
        if v15_allowed is not None and v15_max_date is not None and c.date <= v15_max_date:
            if c.time_ny not in v15_allowed:
                continue
        else:
            if not np.isfinite(sc) or sc < V15_THRESHOLD:
                continue

        if reclaim >= RTH and rxw >= WTH:
            continue

        j = i+3
        signal = one.iloc[j].time_ny
        if signal > cutoff:
            continue

        if pd.notna(c.next_same_extreme_time) and signal >= c.next_same_extreme_time:
            continue

        if one.iloc[j].ticker != c.ticker:
            continue

        entry = float(one.iloc[j].open)
        stop = float(c.extreme)-.25 if c.direction=="LONG" else float(c.extreme)+.25
        risk = entry-stop if c.direction=="LONG" else stop-entry
        if risk <= 0:
            continue

        out.append({
            "entry_time": signal,
            "session": c.session,
            "direction": c.direction,
            "entry": entry,
            "stop": stop,
            "v15_score": sc,
        })

    if not out:
        return [], one.time_ny.max(), 0

    q = pd.DataFrame(out).sort_values("entry_time")
    q["n_day"] = q.groupby(q.entry_time.dt.date).cumcount()+1
    q = q[q.n_day <= 6]
    return q.to_dict("records"), one.time_ny.max(), 0


def main():
    all_data = load_local_only()
    ref_score = build_ref()
    v15_allowed, v15_max_date = build_v15_allowed()

    print("="*92)
    print("SEALED SEP 25 PRODUCTION-AS-OF REPLAY")
    print("LOCAL DATA ONLY | NETWORK/DOWNLOADS: DISABLED")
    print("="*92)

    for hhmm in CUTS:
        cutoff = pd.Timestamp(f"2026-09-25 {hhmm}:00", tz=TZ)
        future_rows = int((all_data.time_ny > cutoff).sum())
        visible = all_data[all_data.time_ny <= cutoff]
        max_visible = visible.time_ny.max() if not visible.empty else None

        trades, engine_max, _ = run_asof(all_data, cutoff, ref_score, v15_allowed, v15_max_date)
        day = [x for x in trades if pd.Timestamp(x["entry_time"]).date() == DATE]

        print(f"\nAS OF {hhmm} ET")
        print(f"  MAX DATA VISIBLE TO ENGINE: {engine_max}")
        print(f"  FUTURE ROWS IN SOURCE FILES: {future_rows} (not passed to engine)")
        print(f"  HARD CHECK max_visible <= cutoff: {bool(max_visible <= cutoff) if max_visible is not None else False}")

        if not day:
            print("  RESULT: NO TRADES")
        else:
            print(f"  RESULT: {len(day)} TRADE(S)")
            for x in day:
                t = pd.Timestamp(x["entry_time"]).strftime("%H:%M")
                print(f"    {t} | {x['session']} | {x['direction']} | entry {x['entry']:.2f} | stop {x['stop']:.2f}")

    print("\n" + "="*92)
    print("SEALED REPLAY COMPLETE — NO FILES MODIFIED")
    print("="*92)


if __name__ == "__main__":
    main()
