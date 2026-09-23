import pandas as pd, numpy as np

print("=== FINAL END-TO-END CAUSALITY AUDIT ===")

FILES=["data/v56_icon_bot_funded_prior_year_trades.csv","data/v27_option2a_trades.csv"]
tr=pd.concat([pd.read_csv(f).assign(source_file=f) for f in FILES],ignore_index=True)
tr["candidate_time"]=pd.to_datetime(tr["candidate_time"],utc=True,errors="coerce")

one=pd.read_parquet("data/mnq_continuous_1m.parquet").copy()
one["t"]=pd.to_datetime(one["time_ny"],utc=True,errors="coerce")
one=one.dropna(subset=["t"]).sort_values("t").drop_duplicates("t").reset_index(drop=True)
idx=pd.Series(one.index,index=one.t).to_dict()

cand=pd.read_parquet("data/v101_1m_candidate_reference_map.parquet").copy()
cand["candidate_time"]=pd.to_datetime(cand["candidate_time"],utc=True,errors="coerce")

# Reproduce the exact 1,911 classification used by the latest audit.
mapped=[]
for _,x in tr.iterrows():
    q=cand[(cand.candidate_time>=x.candidate_time-pd.Timedelta(minutes=6))&
           (cand.candidate_time<=x.candidate_time+pd.Timedelta(minutes=6))]
    q=q[q.direction.astype(str).str.upper()==str(x.direction).upper()]
    if q.empty: mapped.append(None)
    else: mapped.append((q.candidate_time-x.candidate_time).abs().idxmin())
if any(x is None for x in mapped): raise SystemExit("FAIL: not all 1,911 map to native 1m candidates")

cand["_day"]=cand.candidate_time.dt.tz_convert("America/New_York").dt.date
lookup={}
for key,g in cand.sort_values("candidate_time").groupby(["_day","direction"],dropna=False):
    lookup[key]=list(g.candidate_time.dropna())

flags=[]; mt=[]
for j in mapped:
    r=cand.loc[j]; t=r.candidate_time; mt.append(t)
    future=[z for z in lookup[(r["_day"],r["direction"])] if z>t and z<=t+pd.Timedelta(minutes=3)]
    flags.append(bool(future))
tr["mapped_candidate_time"]=mt
tr["known_3m_future_bug"]=flags
cohort=tr[~tr.known_3m_future_bug].copy()
print("Known-3m-bug-clean cohort:",len(cohort))

# End-to-end audit: do NOT assume original entry/risk are causal.
# Reconstruct what V7 could know from native 1m only:
# candidate timestamp T; m1=T+1 closed; m2=T+2 closed; signal/entry=T+3 OPEN.
# Stop is candidate extreme +/- one tick. Every pre-entry filter uses <= T+2.
checks=[]
for rid,x in cohort.iterrows():
    i=idx.get(x.candidate_time)
    reasons=[]
    if i is None or i+3>=len(one):
        reasons.append("candidate_time_not_exact_native_1m")
        checks.append((rid,False,";".join(reasons),np.nan,np.nan)); continue

    # Contract continuity through entry.
    if "ticker" in one.columns and one.iloc[i+3].ticker!=one.iloc[i].ticker:
        reasons.append("contract_changed_before_entry")

    entry_live=float(one.iloc[i+3].open)
    extreme=float(x.get("extreme",np.nan))
    if not np.isfinite(extreme):
        # Derive candidate extreme from stop/risk relation only as a cross-check fallback.
        # Original V7 stop was extreme +/- .25.
        orig_entry=float(x.entry); orig_risk=float(x.risk)
        orig_stop=orig_entry-orig_risk if x.direction=="LONG" else orig_entry+orig_risk
        extreme=orig_stop+.25 if x.direction=="LONG" else orig_stop-.25

    stop_live=extreme-.25 if x.direction=="LONG" else extreme+.25
    risk_live=entry_live-stop_live if x.direction=="LONG" else stop_live-entry_live
    if not np.isfinite(risk_live) or risk_live<=0: reasons.append("nonpositive_live_risk")

    # Original stored entry/risk must equal the values reproducible at T+3 open.
    if not np.isclose(float(x.entry),entry_live,atol=1e-9): reasons.append("stored_entry_not_Tplus3_open")
    if not np.isclose(float(x.risk),risk_live,atol=1e-9): reasons.append("stored_risk_not_causal_rebuild")

    # Candidate extreme must already be present on T candle, not later.
    b=one.iloc[i]
    if x.direction=="LONG" and not np.isclose(float(b.low),extreme,atol=.2500001):
        reasons.append("extreme_not_on_candidate_bar")
    if x.direction=="SHORT" and not np.isclose(float(b.high),extreme,atol=.2500001):
        reasons.append("extreme_not_on_candidate_bar")

    # Signal timing itself must be exactly T+3 minutes in native data.
    if one.iloc[i+3].t != x.candidate_time+pd.Timedelta(minutes=3):
        reasons.append("Tplus3_not_contiguous_minute")

    checks.append((rid,len(reasons)==0,";".join(reasons),entry_live,risk_live))

audit=pd.DataFrame(checks,columns=["row_id","fully_causal_mechanics","failure_reason","rebuilt_entry","rebuilt_risk"]).set_index("row_id")
cohort=cohort.join(audit)

passed=cohort[cohort.fully_causal_mechanics].copy()
failed=cohort[~cohort.fully_causal_mechanics].copy()
print(f"FULLY CAUSAL MECHANICS: {len(passed)} / {len(cohort)}")
print(f"FAILED:                 {len(failed)} / {len(cohort)}")
if len(failed):
    print("\nFAILURE REASONS")
    print(failed.failure_reason.value_counts().to_string())

# Score ONLY passed rows, using rebuilt entry/risk, never stored outcomes.
def score(df):
    for rr in range(1,7):
        w=l=u=0
        for _,x in df.iterrows():
            i=idx[x.candidate_time]; j=i+3
            entry=float(x.rebuilt_entry); risk=float(x.rebuilt_risk)
            stop=entry-risk if x.direction=="LONG" else entry+risk
            target=entry+rr*risk if x.direction=="LONG" else entry-rr*risk
            out=0
            for _,b in one.iloc[j:min(j+241,len(one))].iterrows():
                if "ticker" in one.columns and b.ticker!=one.iloc[j].ticker: break
                if x.direction=="LONG":
                    if b.low<=stop: out=-1; break
                    if b.high>=target: out=1; break
                else:
                    if b.high>=stop: out=-1; break
                    if b.low<=target: out=1; break
            if out==1:w+=1
            elif out==-1:l+=1
            else:u+=1
        n=w+l
        print(f"1:{rr} | {w}W/{l}L/{u}U | WR {100*w/n:.2f}%" if n else f"1:{rr} no resolved")

print("\nRR — ONLY TRADES PASSING END-TO-END MECHANICS AUDIT")
score(passed)
cohort.to_csv("data/final_end_to_end_causality_audit.csv",index=False)
print("\nSaved data/final_end_to_end_causality_audit.csv")
print("\nNOTE: PASS means entry/stop/timing mechanics are reproducible from native 1m data and the known 3m future-extreme bug is absent.")
print("It does NOT certify unknown upstream logic not represented in the saved trade files; any such logic must be audited from its generating source code.")
