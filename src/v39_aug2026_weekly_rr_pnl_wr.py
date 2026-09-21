import pandas as pd
ONE='data/mnq_continuous_1m.parquet'; CAND='data/reversal_candidates.parquet'; LOCKED='data/v27_option2a_trades.csv'; RISK=250
one=pd.read_parquet(ONE); cand=pd.read_parquet(CAND); locked=pd.read_csv(LOCKED)
one['time_ny']=pd.to_datetime(one['time_ny']); cand['time_ny']=pd.to_datetime(cand['time_ny']); locked['candidate_time']=pd.to_datetime(locked['candidate_time'])
one=one.sort_values('time_ny').reset_index(drop=True); cand=cand.sort_values('time_ny').drop_duplicates(['time_ny','session','direction']).reset_index(drop=True)
cand['next_same_extreme_time']=cand.groupby(['session_id','direction'],sort=False).time_ny.shift(-1); idx=pd.Series(one.index,index=one.time_ny).to_dict(); cm={(r.time_ny,str(r.direction)):r for _,r in cand.iterrows()}
def replay(row,rr):
 c=cm.get((row.candidate_time,str(row.direction))); i=idx.get(c.time_ny) if c is not None else None
 if c is None or i is None or i+3>=len(one): return 'MISSING'
 j=i+3
 if one.iloc[j].ticker!=c.ticker:return 'MISSING'
 if pd.notna(c.next_same_extreme_time) and one.iloc[j].time_ny>=c.next_same_extreme_time:return 'MISSING'
 entry=float(one.iloc[j].open); stop=float(c.extreme)-.25 if c.direction=='LONG' else float(c.extreme)+.25; risk=entry-stop if c.direction=='LONG' else stop-entry
 if risk<=0:return 'MISSING'
 target=entry+rr*risk if c.direction=='LONG' else entry-rr*risk
 for z in range(j,min(j+241,len(one))):
  b=one.iloc[z]
  if b.ticker!=c.ticker:break
  if (b.low<=stop if c.direction=='LONG' else b.high>=stop):return 'LOSS'
  if (b.high>=target if c.direction=='LONG' else b.low<=target):return 'WIN'
 return 'UNRESOLVED'
aug=locked[(locked.candidate_time.dt.year==2026)&(locked.candidate_time.dt.month==8)].copy(); aug['week_start']=aug.candidate_time.dt.normalize()-pd.to_timedelta(aug.candidate_time.dt.weekday,unit='D')
rows=[]
for rr in range(1,7):
 for _,r in aug.iterrows(): rows.append({'week_start':r.week_start,'rr':rr,'result':replay(r,rr)})
d=pd.DataFrame(rows); g=d[d.result.isin(['WIN','LOSS'])].copy(); g['pnl']=g.apply(lambda r:(r.rr if r.result=='WIN' else -1)*RISK,axis=1)
out=g.groupby(['week_start','rr']).agg(trades=('result','size'),wins=('result',lambda x:(x=='WIN').sum()),losses=('result',lambda x:(x=='LOSS').sum()),pnl=('pnl','sum')).reset_index(); out['wr_pct']=100*out.wins/out.trades
print('=== OPTION 2A — AUGUST 2026 WEEKLY P&L + WR BY FIXED RR ===')
for ws in sorted(out.week_start.unique()):
 we=ws+pd.Timedelta(days=6); q=out[out.week_start==ws]; print('\n'+ws.strftime('%b %d')+'–'+we.strftime('%b %d')+' | '+str(int(q.iloc[0].trades))+' trades'); print(' | '.join(str(int(r.rr))+'R: $'+format(int(r.pnl),',')+' / '+format(r.wr_pct,'.2f')+'%' for _,r in q.iterrows()))
tot=g.groupby('rr').agg(trades=('result','size'),wins=('result',lambda x:(x=='WIN').sum()),pnl=('pnl','sum')).reset_index(); tot['wr_pct']=100*tot.wins/tot.trades
print('\nTOTAL AUGUST | '+str(len(aug))+' trades'); print(' | '.join(str(int(r.rr))+'R: $'+format(int(r.pnl),',')+' / '+format(r.wr_pct,'.2f')+'%' for _,r in tot.iterrows()))
out.to_csv('data/v39_aug2026_weekly_rr_pnl_wr.csv',index=False)
