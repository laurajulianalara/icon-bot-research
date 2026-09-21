import pandas as pd
ONE='data/mnq_continuous_1m.parquet'; CAND='data/reversal_candidates.parquet'; LOCKED='data/v27_option2a_trades.csv'
one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); locked=pd.read_csv(LOCKED)
one['time_ny']=pd.to_datetime(one['time_ny']); cand['time_ny']=pd.to_datetime(cand['time_ny']); locked['candidate_time']=pd.to_datetime(locked['candidate_time'])
one=one.sort_values('time_ny').reset_index(drop=True); cand=cand.sort_values('time_ny').drop_duplicates(['time_ny','session','direction']).reset_index(drop=True)
cand['next_same_extreme_time']=cand.groupby(['session_id','direction'],sort=False).time_ny.shift(-1)
idx=pd.Series(one.index,index=one.time_ny).to_dict(); cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}
def mfe(row):
 c=cm.get((row.candidate_time,str(row.direction))); i=idx.get(c.time_ny) if c is not None else None
 if c is None or i is None or i+3>=len(one): return None
 j=i+3
 if one.iloc[j].ticker!=c.ticker: return None
 if pd.notna(c.next_same_extreme_time) and one.iloc[j].time_ny>=c.next_same_extreme_time: return None
 entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=='LONG' else float(c.extreme)+.25
 risk=entry-stop if c.direction=='LONG' else stop-entry
 if risk<=0:return None
 best=0.0
 for z in range(j,min(j+241,len(one))):
  b=one.iloc[z]
  if b.ticker!=c.ticker: break
  if (b.low<=stop if c.direction=='LONG' else b.high>=stop): break
  fav=(float(b.high)-entry)/risk if c.direction=='LONG' else (entry-float(b.low))/risk
  best=max(best,fav)
 return best
jul=locked[(locked.candidate_time.dt.year==2026)&(locked.candidate_time.dt.month==7)].copy(); jul['mfe_r']=jul.apply(mfe,axis=1)
print('=== OPTION 2A — JULY 2026 WEEKLY + MAX RR ===')
print('Trades:',len(jul),'| Valid:',jul.mfe_r.notna().sum())
print('Average max RR:',round(jul.mfe_r.mean(),2)); print('Median max RR:',round(jul.mfe_r.median(),2)); print('Highest single-trade RR:',round(jul.mfe_r.max(),2))
print('\nMAX RR DISTRIBUTION')
for r in [1,2,3,4,5,6,7,8,10,12,15,20,25,30]:
 n=int((jul.mfe_r>=r).sum()); print(f'{r}R: {n}/{len(jul)} = {100*n/len(jul):.2f}%')
jul['week_start']=(jul.candidate_time.dt.tz_localize(None)-pd.to_timedelta(jul.candidate_time.dt.weekday,unit='D')).dt.normalize()
print('\nWEEKLY STATS — FIXED RR, $250 RISK')
for ws,g in jul.groupby('week_start'):
 we=ws+pd.Timedelta(days=6); print(f'\n{ws:%b %d}–{we:%b %d} | {len(g)} trades')
 for r in [1,2,3,4,5,6]:
  w=int((g.mfe_r>=r).sum()); l=len(g)-w; pnl=(w*r-l)*250; print(f'{r}R: ${pnl:,.0f} | WR {100*w/len(g):.2f}% ({w}W/{l}L)')
jul[['candidate_time','direction','mfe_r','week_start']].to_csv('data/v41_july2026_weekly_mfe.csv',index=False)
print('\nSaved: data/v41_july2026_weekly_mfe.csv')