from common import *

def main():
 rows=[];groups=[];seeds=[];spectra=[]
 for p in sorted((OLD/'final').glob('normal_*.bin')):
  dev=p.stem.split('_')[1];names,_,fields,d=load_pr3(p);t=d['ts'];dd=d['methods']['diag'][:,0];di={f:i for i,f in enumerate(fields)};b=pd.read_csv(OLD/'final'/f'birth_{dev}.csv');md=pd.read_pickle(CACHE/f'Marker_{dev}.pkl')
  for segment,st,en in [('day1105_pre',epoch('2026-11-05 07:20'),epoch('2026-11-05 11:30')),('day1105_post',epoch('2026-11-05 13:00'),epoch('2026-11-05 22:00')),('night1105',epoch('2026-11-05 23:20'),epoch('2026-11-06 07:00')),('day1106',epoch('2026-11-06 07:20'),epoch('2026-11-06 22:00')),('night1106',epoch('2026-11-06 23:20'),epoch('2026-11-07 07:00')),('day1107',epoch('2026-11-07 07:20'),epoch('2026-11-07 15:00'))]:
   use=(t>=st)&(t<en);tt=t[use];x=d['rawx'][use];cal=d['methods']['x'][use,0];common=x-cal;adj=(np.diff(tt)>=30000)&(np.diff(tt)<=90000);dx=np.diff(x,axis=0);dc=np.diff(common,axis=0);dr=np.diff(cal,axis=0);dx[~adj]=np.nan;dc[~adj]=np.nan;dr[~adj]=np.nan
   for kind,ids in [('all',list(range(len(names)))),('YJ',[i for i,n in enumerate(names) if n.startswith('YJ')]),('YXJ',[i for i,n in enumerate(names) if n.startswith('YXJ')]),('ordinary',[i for i,n in enumerate(names) if not n.startswith(('YJ','YXJ','ZJ','ZXJ'))])]:
    if not ids:continue
    mat=dx[:,ids];complete=mat[np.isfinite(mat).all(axis=1)];frac=np.nan
    if len(complete)>=30:
     ev=np.linalg.eigvalsh(np.cov(complete,rowvar=False)) if len(ids)>1 else np.array([np.var(complete)]);frac=np.maximum(ev[-min(3,len(ev)):],0).sum()/max(1e-20,np.maximum(ev,0).sum())
    groups.append({'device_id':dev,'segment':segment,'kind':kind,'markers':len(ids),'complete_steps':len(complete),'raw_step_top3_PCA_energy_fraction':frac,'raw_step_rms_mm':np.sqrt(np.nanmean(mat**2)),'C0_correction_step_rms_mm':np.sqrt(np.nanmean(dc[:,ids]**2)),'C0_residual_step_rms_mm':np.sqrt(np.nanmean(dr[:,ids]**2)),'meaning':'empirical spatial energy / original-model association; not fraction of physical noise'})
   for i,n in enumerate(names):
    v=x[:,i];r=cal[:,i];h=v-rolling(tt,v);d2=r[2:]-2*r[1:-1]+r[:-2];ok=adj[1:]&adj[:-1];d2[~ok]=np.nan;sd=robust_sd(d2)/np.sqrt(6);lag=corr(dr[1:,i],dr[:-1,i]);rawlag=corr(dx[1:,i],dx[:-1,i]);rho=corr(dx[:,i],dc[:,i]);finite=np.isfinite(dx[:,i]);othermat=np.delete(dr,i,axis=1);others=np.full(len(dr),np.nan);has=np.isfinite(othermat).any(axis=1);others[has]=np.nanmedian(othermat[has],axis=1)
    row={'device_id':dev,'marker_name':n,'kind':'YJ' if n.startswith(('YJ','ZJ')) else 'YXJ' if n.startswith(('YXJ','ZXJ')) else 'ordinary','segment':segment,'start_beijing':iso(st),'end_exclusive_beijing':iso(en),'raw_step_P99_mm':np.nanquantile(abs(dx[:,i]),.99),'raw_step_lag1_r':rawlag,'C0_residual_step_lag1_r':lag,'C0_residual_step_vs_other_median_r':corr(dr[:,i],others),'raw_step_vs_C0_common_step_r':rho,'second_difference_white_sigma_proxy_mm':sd,'raw_highpass5min_MAD_mm':robust_sd(h),'highpass_unit':'minute-scale variation; 5min trailing median residual; not true error','eligible_white_like_proxy':bool(np.isfinite(lag) and -.75<=lag<=-.15),'interpretation':'negative increment correlation can support stochastic-like jitter, but does not prove noise / static truth'};rows.append(row)
    if segment.startswith('night') and np.isfinite(sd):seeds.append(sd)
    # Frequency bins on contiguous ~60s sequences only; irregular/gapped
    # pieces are not interpolated into a synthetic spectrum.
    for a,bb in zip(np.r_[0,np.flatnonzero(~adj)+1],np.r_[np.flatnonzero(~adj)+1,len(tt)]):
     if bb-a<128 or not np.isfinite(v[a:bb]).all():continue
     z=v[a:bb];z=z-np.polyval(np.polyfit(np.arange(len(z)),z,1),np.arange(len(z)));z*=np.hanning(len(z));power=abs(np.fft.rfft(z))**2;freq=np.fft.rfftfreq(len(z),np.median(np.diff(tt[a:bb]))/60000);den=power[1:].sum()
     spectra.append({'device_id':dev,'marker_name':n,'segment':segment,'start_beijing':iso(tt[a]),'end_beijing':iso(tt[bb-1]),'samples':bb-a,'period2to6min_energy_fraction':power[(freq>=1/6)&(freq<=.5)].sum()/max(den,1e-20),'period6to30min_energy_fraction':power[(freq>=1/30)&(freq<1/6)].sum()/max(den,1e-20),'period_over30min_energy_fraction':power[(freq>0)&(freq<1/30)].sum()/max(den,1e-20),'definition':'linear detrend + Hann, native near-minute contiguous timestamps; descriptive not physical labels'})
 write(pd.DataFrame(rows),'old_noise_components.csv');write(pd.DataFrame(groups),'old_spatial_common.csv');write(pd.DataFrame(spectra),'old_frequency_components.csv')
 seed=float(np.median(seeds));(W/'noise_seed.json').write_text(json.dumps({'old_only_sigma_median_mm':seed,'gaussian_test_levels_mm':[.5*seed,seed,2*seed],'definition':'second-difference MAD/sqrt6 of old C0 residual; proxy, not calibrated pixel noise'}),encoding='utf-8')
 q=pd.DataFrame(rows);print(q[q.segment.str.startswith('night')].groupby(['device_id','kind'])[['eligible_white_like_proxy','second_difference_white_sigma_proxy_mm','raw_step_vs_C0_common_step_r']].median().round(4).to_string());print('Frozen noise test scales:',seed,[.5*seed,seed,2*seed])
if __name__=='__main__':main()
