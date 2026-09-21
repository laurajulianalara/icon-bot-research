import pandas as pd
ONE='data/mnq_continuous_1m.parquet'
CAND='data/reversal_candidates.parquet'
LOCKED='data/v27_option2a_trades.csv'
one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); locked=pd.read_csv(LOCKED)
one['time_ny']=pd.to_datetime(one['time_ny']); cand['time_ny']=pd.to_datetime(cand['time_ny']); locked['candidate_time']=pd.to_datetime(locked['candidate_time'])
one=one.sort_values('time_ny').reset_index(drop=True)
cand=cand.sort_values('time_ny').drop_duplicates(['time_ny','session','direction']).reset_index(drop=True)
cand['next_same_extreme_time']=cand.groupby(['session_id','direction'],sort=False).time_ny.shift(-1)
idx=pd.Series(one.index,index=one.time_ny).to_dict()
cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}
def calc_mfe(row):
    c=cm.get((row.candidate_time,str(row.direction)))
    if c is None: return None
    i=idx.get(c.time_ny)
    if i is None or i+3>=len(one): return None
    j=i+3
    if one.iloc[j].ticker!=c.ticker: return None
    if pd.notna(c.next_same_extreme_time) and one.iloc[j].time_ny>=c.next_same_extreme_time: return None
    entry=float(one.iloc[j].open)
    stop=float(c.extreme)-0.25 if c.direction=='LONG' else float(c.extreme)+0.25
    risk=entry-stop if c.direction=='LONG' else stop-entry
    if risk<=0: return None
    best=0.0
    for z in range(j,min(j+241,len(one))):
        b=one.iloc[z]
        if b.ticker!=c.ticker: break
        stop_hit=(b.low<=stop) if c.direction=='LONG' else (b.high>=stop)
        if stop_hit: break
        fav=(float(b.high)-entry)/risk if c.direction=='LONG' else (entry-float(b.low))/risk
        best=max(best,fav)
    return best
aug=locked[(locked.candidate_time.dt.year==2026)&(locked.candidate_time.dt.month==8)].copy()
aug['mfe_r']=aug.apply(calc_mfe,axis=1)
print('=== OPTION 2A — AUGUST 2026 RUNNER / MFE STUDY ===')
print('Trades:',len(aug),'| Valid:',int(aug.mfe_r.notna().sum()))
print('Average max RR:',round(aug.mfe_r.mean(),2))
print('Median max RR:',round(aug.mfe_r.median(),2))
print('Highest single-trade RR:',round(aug.mfe_r.max(),2))
print('\nREACHED AT LEAST:')
for level in [1,2,3,4,5,6,7,8,10,12,15,20,25,30]:
    n=int((aug.mfe_r>=level).sum())
    print(str(level)+'R: '+str(n)+'/'+str(len(aug))+' = '+format(100*n/len(aug),'.2f')+'%')
aug[['candidate_time','direction','mfe_r']].to_csv('data/v40_aug2026_mfe_runner_study.csv',index=False)
print('\nSaved: data/v40_aug2026_mfe_runner_study.csv')