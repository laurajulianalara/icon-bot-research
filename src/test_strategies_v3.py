import pandas as pd
import numpy as np
from itertools import product

DATA_1M = "data/mnq_continuous_1m.parquet"
DATA_3M = "data/mnq_continuous_3m.parquet"
CANDIDATES = "data/reversal_candidates.parquet"
FEATURES_OUT = "data/v3_reversal_features.parquet"
RESULTS_OUT = "data/strategy_results_v3.csv"

LOOKBACK_DAYS = 365
MAX_CONFIRM_BARS = [3, 5, 8]
ENTRY_TYPES = ["NO_FIB", "FIB_500", "FIB_618", "FIB_705", "FIB_786"]
RR_VALUES = [3.0, 4.0]
STOP_BUFFERS = [0.25, 0.50]
MAX_ENTRY_WAIT_MIN = 30
MAX_TRADE_HOURS = 4
MIN_TRAIN_TRADES = 120
MIN_VALID_TRADES = 50
TARGET_WR = 50.0

print("\nLoading V3 data...")
one = pd.read_parquet(DATA_1M)
three = pd.read_parquet(DATA_3M)
cand = pd.read_parquet(CANDIDATES)
for x in (one, three, cand):
    x["time_ny"] = pd.to_datetime(x["time_ny"])
one = one.sort_values("time_ny").reset_index(drop=True)
three = three.sort_values("time_ny").reset_index(drop=True)
cand = cand.sort_values("time_ny").reset_index(drop=True)

end = three["time_ny"].max()
start = end - pd.Timedelta(days=LOOKBACK_DAYS)
one = one[one.time_ny >= start].copy()
three = three[three.time_ny >= start].copy()
cand = cand[cand.time_ny >= start].copy()
split = start + (end - start) * 0.70
print("Period:", start, "to", end)
print("Train:", start, "to", split)
print("Validation:", split, "to", end)
print("Candidates:", f"{len(cand):,}")

# ---------- 3M causal features ----------
three["range"] = three.high - three.low
three["body"] = (three.close - three.open).abs()
three["atr"] = pd.concat([
    three.high-three.low,
    (three.high-three.close.shift()).abs(),
    (three.low-three.close.shift()).abs()
], axis=1).max(axis=1).rolling(20).mean()
three["vol_med20"] = three.volume.rolling(20).median()
three["rel_vol"] = three.volume / three.vol_med20.replace(0, np.nan)

# Causal support/resistance zones: recent confirmed 3-bar pivots.
# A pivot at i-1 becomes known only when bar i closes.
three["pivot_hi"] = np.where(
    (three.high.shift(1) > three.high.shift(2)) & (three.high.shift(1) >= three.high),
    three.high.shift(1), np.nan)
three["pivot_lo"] = np.where(
    (three.low.shift(1) < three.low.shift(2)) & (three.low.shift(1) <= three.low),
    three.low.shift(1), np.nan)

idx_by_time = pd.Series(three.index, index=three["time_ny"]).to_dict()
one_idx = one.set_index("time_ny")

cand["next_same_extreme_time"] = cand.groupby(["session_id","direction"])["time_ny"].shift(-1)

required_1m = {"time_ny","ticker","open","high","low","close","volume"}
required_3m = {"time_ny","ticker","open","high","low","close","volume"}
required_c = {"time_ny","session_id","session","ticker","direction","extreme","open","atr","wick_percent","relative_volume","sweep_distance"}
for name, frame, required in [("1M", one, required_1m), ("3M", three, required_3m), ("candidates", cand, required_c)]:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{name} data is missing columns: {sorted(missing)}")

timestamp_matches = cand["time_ny"].isin(idx_by_time).sum()
print("Candidate timestamps matched to 3M:", f"{timestamp_matches:,}/{len(cand):,}")
if timestamp_matches == 0:
    raise ValueError("No candidate timestamps match the 3M dataset. Stop before scanning.")

def recent_sr_distance(i, direction, price, atr):
    lo = max(0, i-80)
    hist = three.iloc[lo:i+1]
    vals = hist["pivot_lo"].dropna().values if direction=="LONG" else hist["pivot_hi"].dropna().values
    if len(vals)==0 or not np.isfinite(atr) or atr<=0:
        return np.nan
    return float(np.min(np.abs(vals-price))/atr)

def find_confirm(c, max_bars):
    t = c["time_ny"]
    if t not in idx_by_time:
        return None
    i = idx_by_time[t]
    if i is None: return None
    direction, ticker = c.direction, c.ticker
    ref = c.open
    next_ext = c.next_same_extreme_time
    last_opp = ref
    for j in range(i+1, min(i+max_bars+1, len(three))):
        r = three.iloc[j]
        if r.ticker != ticker: return None
        if pd.notna(next_ext) and r.time_ny >= next_ext: return None
        if direction=="LONG" and r.close < r.open: last_opp = r.open
        if direction=="SHORT" and r.close > r.open: last_opp = r.open
        confirmed = (direction=="LONG" and r.close > last_opp) or (direction=="SHORT" and r.close < last_opp)
        if not confirmed: continue

        leg = three.iloc[i:j+1]
        if direction=="LONG":
            leg_end = leg.high.max(); size = leg_end-c.extreme
        else:
            leg_end = leg.low.min(); size = c.extreme-leg_end
        if size<=0: return None

        # Displacement = confirmation body/range relative to ATR.
        atr = float(r.atr) if pd.notna(r.atr) else np.nan
        disp_atr = abs(r.close-r.open)/atr if np.isfinite(atr) and atr>0 else 0
        close_pos = ((r.close-r.low)/(r.high-r.low)) if r.high>r.low else .5
        if direction=="SHORT": close_pos = 1-close_pos

        # FVG formed in reversal direction using only bars known by confirmation.
        fvg = False
        fvg_size_atr = 0.0
        if j>=2 and np.isfinite(atr) and atr>0:
            a = three.iloc[j-2]
            if direction=="LONG" and r.low > a.high:
                fvg=True; fvg_size_atr=(r.low-a.high)/atr
            if direction=="SHORT" and r.high < a.low:
                fvg=True; fvg_size_atr=(a.low-r.high)/atr

        # IFVG: an opposing 3-candle FVG created shortly before the extreme,
        # then closed through in the reversal direction by confirmation.
        ifvg=False
        pre = three.iloc[max(2,i-12):i+1]
        for k in pre.index:
            if k<2: continue
            z=three.loc[k]; a=three.loc[k-2]
            if direction=="LONG" and z.high < a.low:  # bearish FVG
                zone_hi=a.low
                if r.close > zone_hi: ifvg=True
            if direction=="SHORT" and z.low > a.high: # bullish FVG
                zone_lo=a.high
                if r.close < zone_lo: ifvg=True

        fibs={}
        for f in [.500,.618,.705,.786]:
            fibs[f] = leg_end-size*f if direction=="LONG" else leg_end+size*f

        return dict(confirm_time=r.time_ny, confirm_idx=j, cisd_bars=j-i,
                    leg_end=leg_end, leg_size=size, disp_atr=disp_atr,
                    confirm_close_pos=close_pos, fvg=fvg,
                    fvg_size_atr=fvg_size_atr, ifvg=ifvg, fibs=fibs)
    return None

def simulate(c, conf, entry_type, rr, stop_buffer):
    direction,ticker=c.direction,c.ticker
    ct=conf["confirm_time"]
    stop=c.extreme-stop_buffer if direction=="LONG" else c.extreme+stop_buffer
    w=one_idx.loc[ct:ct+pd.Timedelta(minutes=MAX_ENTRY_WAIT_MIN)]
    w=w[w.ticker==ticker]
    if w.empty:return None
    if entry_type=="NO_FIB":
        z=w[w.index>ct]
        if z.empty:return None
        ft=z.index[0]; entry=float(z.iloc[0].open)
    else:
        f={"FIB_500":.500,"FIB_618":.618,"FIB_705":.705,"FIB_786":.786}[entry_type]
        entry=conf["fibs"][f]; ft=None
        for ts,b in w.iterrows():
            if ts<=ct:continue
            if b.low<=entry<=b.high: ft=ts; break
        if ft is None:return None
    risk=entry-stop if direction=="LONG" else stop-entry
    if risk<=0:return None
    target=entry+risk*rr if direction=="LONG" else entry-risk*rr
    td=one_idx.loc[ft:ft+pd.Timedelta(hours=MAX_TRADE_HOURS)]
    td=td[td.ticker==ticker]
    if td.empty:return None
    outcome="TIMEOUT"; xt=td.index[-1]; mfe=mae=0.0
    for ts,b in td.iterrows():
        if direction=="LONG":
            fav=b.high-entry; adv=entry-b.low; sh=b.low<=stop; th=b.high>=target
        else:
            fav=entry-b.low; adv=b.high-entry; sh=b.high>=stop; th=b.low<=target
        mfe=max(mfe,fav); mae=max(mae,adv)
        if sh: outcome="LOSS"; xt=ts; break
        if th: outcome="WIN"; xt=ts; break
    return dict(fill_time=ft,exit_time=xt,outcome=outcome,
                result_r=rr if outcome=="WIN" else (-1.0 if outcome=="LOSS" else 0.0),
                mfe_r=mfe/risk,mae_r=mae/risk)

print("\nBuilding reversal-quality feature + trade cache...")
rows=[]
for n,(_,c) in enumerate(cand.iterrows(),1):
    if n%1000==0: print(f"Candidate {n:,}/{len(cand):,}")
    i=idx_by_time.get(c.time_ny)
    if i is None:continue
    atr=float(c.atr) if pd.notna(c.atr) else np.nan
    sr_dist=recent_sr_distance(i,c.direction,c.extreme,atr)
    sweep_atr=(c.sweep_distance/atr) if np.isfinite(atr) and atr>0 else 0
    # Rejection / absorption proxies known at candidate bar.
    rejection=float(c.wick_percent) if pd.notna(c.wick_percent) else 0
    relvol=float(c.relative_volume) if pd.notna(c.relative_volume) else 0
    absorption=(relvol>=1.2 and rejection>=.30)
    strong_abs=(relvol>=1.5 and rejection>=.40)
    for mb in MAX_CONFIRM_BARS:
        conf=find_confirm(c,mb)
        if conf is None:continue
        for entry,rr,sb in product(ENTRY_TYPES,RR_VALUES,STOP_BUFFERS):
            tr=simulate(c,conf,entry,rr,sb)
            if tr is None:continue
            rows.append({**tr,
                "candidate_time":c.time_ny,"session":c.session,"direction":c.direction,
                "max_cisd_bars":mb,"entry":entry,"rr":rr,"stop_buffer":sb,
                "sr_dist_atr":sr_dist,"sweep_atr":sweep_atr,"rejection":rejection,
                "relative_volume":relvol,"absorption":absorption,"strong_abs":strong_abs,
                "disp_atr":conf["disp_atr"],"confirm_close_pos":conf["confirm_close_pos"],
                "fvg":conf["fvg"],"fvg_size_atr":conf["fvg_size_atr"],"ifvg":conf["ifvg"]})
cache=pd.DataFrame(rows)
cache.to_parquet(FEATURES_OUT,index=False)
print("Cached trades:",f"{len(cache):,}")

# ---------- Targeted combination search ----------
# Each switch is interpretable and directly tied to reversal quality.
SR_MAX=[None,0.15,0.30,0.50]
SWEEP_MIN=[None,0.05,0.15]
REJECTION_MIN=[None,0.30,0.40]
VOL_MIN=[None,1.2,1.5]
DISP_MIN=[None,0.30,0.50,0.75]
IFVG_REQ=[False,True]
FVG_REQ=[False,True]
ABS_MODE=["NONE","BASIC","STRONG"]

base_combos=list(product(MAX_CONFIRM_BARS,ENTRY_TYPES,RR_VALUES,STOP_BUFFERS))
quality_combos=list(product(SR_MAX,SWEEP_MIN,REJECTION_MIN,VOL_MIN,DISP_MIN,IFVG_REQ,FVG_REQ,ABS_MODE))
print("\nBase execution families:",f"{len(base_combos):,}")
print("Reversal-quality combinations:",f"{len(quality_combos):,}")
print("Maximum combinations evaluated:",f"{len(base_combos)*len(quality_combos):,}")

def apply_filters(x,q):
    sr,sw,wk,vol,disp,ifvg,fvg,ab=q
    m=np.ones(len(x),dtype=bool)
    if sr is not None:m &= x.sr_dist_atr.fillna(999).values<=sr
    if sw is not None:m &= x.sweep_atr.values>=sw
    if wk is not None:m &= x.rejection.values>=wk
    if vol is not None:m &= x.relative_volume.values>=vol
    if disp is not None:m &= x.disp_atr.values>=disp
    if ifvg:m &= x.ifvg.values
    if fvg:m &= x.fvg.values
    if ab=="BASIC":m &= x.absorption.values
    if ab=="STRONG":m &= x.strong_abs.values
    return x.loc[m]

def one_live(x):
    x=x.sort_values("fill_time")
    keep=[]; exit_time=None
    for ix,tr in x.iterrows():
        if exit_time is not None and tr.fill_time<=exit_time:continue
        keep.append(ix); exit_time=tr.exit_time
    return x.loc[keep]

def metrics(x):
    x=one_live(x)
    z=x[x.outcome.isin(["WIN","LOSS"])]
    if z.empty:return None
    wins=(z.outcome=="WIN").sum()
    eq=z.result_r.cumsum(); dd=eq-eq.cummax()
    gw=z.loc[z.result_r>0,"result_r"].sum()
    gl=abs(z.loc[z.result_r<0,"result_r"].sum())
    return dict(trades=len(z),win_rate=wins/len(z)*100,net_r=z.result_r.sum(),
                expectancy_r=z.result_r.mean(),profit_factor=gw/gl if gl else np.nan,
                max_drawdown_r=abs(dd.min()))

results=[]
for bi,b in enumerate(base_combos,1):
    mb,entry,rr,sb=b
    base=cache[(cache.max_cisd_bars==mb)&(cache.entry==entry)&(cache.rr==rr)&(cache.stop_buffer==sb)]
    train_base=base[base.fill_time<split]
    valid_base=base[base.fill_time>=split]
    for q in quality_combos:
        tr=metrics(apply_filters(train_base,q))
        if tr is None or tr["trades"]<MIN_TRAIN_TRADES:continue
        va=metrics(apply_filters(valid_base,q))
        if va is None or va["trades"]<MIN_VALID_TRADES:continue
        sr,sw,wk,vol,disp,ifvg,fvg,ab=q
        results.append(dict(max_cisd_bars=mb,entry=entry,rr=rr,stop_buffer=sb,
            sr_max_atr=sr,sweep_min_atr=sw,rejection_min=wk,volume_min=vol,
            displacement_min_atr=disp,ifvg_required=ifvg,fvg_required=fvg,
            absorption=ab,
            train_trades=tr["trades"],train_wr=tr["win_rate"],train_exp_r=tr["expectancy_r"],
            train_pf=tr["profit_factor"],train_dd_r=tr["max_drawdown_r"],
            valid_trades=va["trades"],valid_wr=va["win_rate"],valid_exp_r=va["expectancy_r"],
            valid_pf=va["profit_factor"],valid_dd_r=va["max_drawdown_r"],
            target_50=(tr["win_rate"]>=TARGET_WR and va["win_rate"]>=TARGET_WR)))
    if bi%10==0:print(f"Execution family {bi}/{len(base_combos)}")

res=pd.DataFrame(results)
if res.empty:
    raise ValueError("No V3 combinations met the minimum train/validation sample sizes.")
res["robust_wr"]=res[["train_wr","valid_wr"]].min(axis=1)
res["robust_exp"]=res[["train_exp_r","valid_exp_r"]].min(axis=1)
res=res.sort_values(["target_50","robust_wr","robust_exp","valid_trades"],ascending=[False,False,False,False]).reset_index(drop=True)
res.to_csv(RESULTS_OUT,index=False)

print("\n===================================")
print(" V3 TARGETED REVERSAL SCAN COMPLETE")
print("===================================")
print("Results:",f"{len(res):,}")
print("50%+ in BOTH train and validation:",int(res.target_50.sum()))
print("Saved:",RESULTS_OUT)
cols=["entry","rr","max_cisd_bars","sr_max_atr","sweep_min_atr","rejection_min",
      "volume_min","displacement_min_atr","ifvg_required","fvg_required","absorption",
      "train_trades","train_wr","valid_trades","valid_wr","robust_wr","valid_dd_r"]
print("\nTOP 25 ROBUST RESULTS:")
print(res[cols].head(25).round(2).to_string(index=False))
print("\nIMPORTANT: These are research results, not a final live strategy.")
print("NEXT: push strategy_results_v3.csv so finalists can be audited by session/month and older-history robustness.")
