import pandas as pd
import numpy as np

print("=== V85 REFERENCE TRADE + PRECEDING EXTREME FORENSICS ===")
v68=pd.read_parquet("data/v68_full_causal_feature_table.parquet").copy()
atlas=pd.read_parquet("data/v76_preentry_feature_atlas.parquet").copy()
refs=[]
for sample,path in [("2024-2025","data/v56_icon_bot_funded_prior_year_trades.csv"),
                    ("2025-2026","data/v27_option2a_trades.csv")]:
    x=pd.read_csv(path); x["sample"]=sample; refs.append(x)
ref=pd.concat(refs,ignore_index=True)

def tc(df):
    return next(c for c in ["candidate_time","t_utc","time","candidate_time_et"] if c in df.columns)
for df in [v68,atlas,ref]:
    c=tc(df); df["_t"]=pd.to_datetime(df[c],utc=True,errors="coerce")

# Exact reference membership.
refkeys=set(ref["_t"].dropna())
atlas["is_reference"]=atlas["_t"].isin(refkeys)
v68["is_reference"]=v68["_t"].isin(refkeys)

# Safe causal feature set shared by atlas/v68, excluding labels/outcomes/future.
ban=("win","outcome","target","exit","result","future","next_","hindsight","invalid","label","class","score")
features=[c for c in atlas.columns if c in v68.columns and
          pd.api.types.is_numeric_dtype(atlas[c]) and
          not any(b in c.lower() for b in ban) and c not in ("entry","risk")]
print("Reference matches in atlas:",int(atlas.is_reference.sum()),"/ 1911")
print("Shared causal numeric features:",len(features))

# #1: What successful reference trades had before entry, RR by RR.
rows=[]
for rr in range(1,7):
    lab=f"win_{rr}r"
    if lab not in atlas.columns: continue
    for f in features:
        a=pd.to_numeric(atlas.loc[atlas.is_reference & (atlas[lab]==1),f],errors="coerce").dropna()
        b=pd.to_numeric(atlas.loc[atlas.is_reference & (atlas[lab]==0),f],errors="coerce").dropna()
        if len(a)<20 or len(b)<20: continue
        scale=pd.concat([a,b]).std()
        sep=0 if not np.isfinite(scale) or scale==0 else abs(a.median()-b.median())/scale
        rows.append({"rr":rr,"feature":f,"winner_median":a.median(),"loser_median":b.median(),
                     "direction":"HIGHER" if a.median()>b.median() else "LOWER","separation":sep,
                     "winner_n":len(a),"loser_n":len(b)})
sig=pd.DataFrame(rows).sort_values(["rr","separation"],ascending=[True,False])
sig.to_csv("data/v85_reference_winner_confluences.csv",index=False)

# #3: For every selected reference extreme, locate nearest earlier same-session/same-direction
# candidate(s) that Python rejected before eventually selecting reference.
v68["date_et"]=v68["_t"].dt.tz_convert("America/New_York").dt.date
refmeta=ref.copy(); refmeta["date_et"]=refmeta["_t"].dt.tz_convert("America/New_York").dt.date
pairs=[]
for _,r in refmeta.iterrows():
    if pd.isna(r["_t"]) or "session" not in r or "direction" not in r: continue
    pool=v68[(v68.date_et==r.date_et)&(v68.session==r.session)&(v68.direction==r.direction)&(v68._t<r._t)].sort_values("_t")
    if pool.empty: continue
    # Keep up to 3 immediately preceding extremes: captures repeated WAIT -> WAIT -> ENTER sequences.
    for lag,(_,p) in enumerate(pool.tail(3).iloc[::-1].iterrows(),start=1):
        z={"selected_time":r["_t"],"rejected_time":p["_t"],"lag":lag,
           "minutes_before":(r["_t"]-p["_t"]).total_seconds()/60,
           "session":r.session,"direction":r.direction}
        for f in features:
            z["selected_"+f]=pd.to_numeric(v68.loc[v68._t==r["_t"],f],errors="coerce").iloc[0] if (v68._t==r["_t"]).any() else np.nan
            z["rejected_"+f]=pd.to_numeric(pd.Series([p[f]]),errors="coerce").iloc[0]
        pairs.append(z)
pairs=pd.DataFrame(pairs)
pairs.to_parquet("data/v85_selected_vs_preceding_extremes.parquet",index=False)

# Rank features that change most from rejected extreme -> selected extreme.
comp=[]
if len(pairs):
    for f in features:
        a=pd.to_numeric(pairs["selected_"+f],errors="coerce")
        b=pd.to_numeric(pairs["rejected_"+f],errors="coerce")
        ok=a.notna()&b.notna()
        if ok.sum()<30: continue
        av=a[ok].astype(float).to_numpy()\n        bv=b[ok].astype(float).to_numpy()\n        delta=pd.Series(av-bv)
        scale=pd.concat([a[ok],b[ok]]).std()
        comp.append({"feature":f,"pairs":int(ok.sum()),"selected_median":a[ok].median(),
                     "rejected_median":b[ok].median(),"median_delta":delta.median(),
                     "abs_standardized_change":0 if not np.isfinite(scale) or scale==0 else abs(delta.median())/scale,
                     "selected_higher_pct":100*(delta>0).mean()})
comp=pd.DataFrame(comp).sort_values("abs_standardized_change",ascending=False)
comp.to_csv("data/v85_selected_vs_rejected_feature_changes.csv",index=False)

print("\n#1 TOP CONFLUENCES OF REFERENCE WINNERS")
for rr in range(1,7):
    print(f"\n1:{rr}")
    print(sig[sig.rr==rr].head(12).to_string(index=False))

print("\n#3 SELECTED EXTREME VS IMMEDIATELY PRECEDING EXTREMES")
print("Comparison rows:",len(pairs),"selected trades with prior extremes:",pairs.selected_time.nunique() if len(pairs) else 0)
print(comp.head(20).to_string(index=False) if len(comp) else "No pairs found")
print("\nSaved:")
print(" data/v85_reference_winner_confluences.csv")
print(" data/v85_selected_vs_preceding_extremes.parquet")
print(" data/v85_selected_vs_rejected_feature_changes.csv")
print("NEXT: use these exact differences to engineer the AI WAIT/ENTER feature set, including CISD/structure after timing audit.")
