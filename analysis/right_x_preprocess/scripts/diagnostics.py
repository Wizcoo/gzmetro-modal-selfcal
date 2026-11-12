from dataio import *

def main():
 noise=[];key=[];daily=[]
 for q in pd.read_csv(O/'input_identity_validation.csv',dtype={'device_id':str}).to_dict('records'):
  line,dev=q['line'],q['device_id'];names,methods,fields,d=load(W/'validation'/f'clean_{line}_{dev}.bin');ix={f:i for i,f in enumerate(fields)};t=d['ts'];dd=d['methods']['diag']
  n=pd.read_csv(W/'validation'/f'noise_{line}_{dev}.csv');n['date']=pd.to_datetime(n.night_id,unit='D').dt.strftime('%Y-%m-%d');n=n[n.date.ge('2026-11-07' if line=='right' else '2026-11-05')];base=n[n.method.eq('B0_raw')].set_index(['night_id','marker','noise_sigma_mm'])
  for method,g in n.groupby('method'):
   b=base.reindex(pd.MultiIndex.from_frame(g[['night_id','marker','noise_sigma_mm']])).reset_index()
   for i,r in enumerate(g.to_dict('records')):
    r['ratio_pre_noise']=r['pre_noise_sensitivity_RMSE_mm']/b.iloc[i].pre_noise_sensitivity_RMSE_mm;r['ratio_cal_noise']=r['cal_noise_sensitivity_RMSE_mm']/b.iloc[i].cal_noise_sensitivity_RMSE_mm;r['kind']='node' if r['marker'].startswith(('YXJ','ZXJ')) else 'reference' if r['marker'].startswith(('YJ','ZJ')) else 'ordinary';noise.append(r)
  for date,phase,st,en in windows(t,'validation'):
   if phase!='night' or line=='right' and date<'2026-11-07':continue
   active=(t>=st)&(t<en)&(dd[:,0,ix['gate']]>0)&(dd[:,0,ix['n_corrected']]>0)
   if active.sum()<20:continue
   for i,name in enumerate(names):
    if not name.startswith(('YJ','YXJ','ZJ','ZXJ')):continue
    for mi,m in enumerate(methods):
     mask=active&np.isfinite(d['raw'][:,i])&np.isfinite(d['methods']['cal'][:,mi,i]);r=metrics(t[mask],d['methods']['cal'][mask,mi,i]);r.update(stage='validation',line=line,device_id=dev,marker_name=name,date=date,phase='night',scope='same_B0_active',method=m,kind='node' if name.startswith(('YXJ','ZXJ')) else 'reference');key.append(r)
 n=pd.DataFrame(noise)
 # Compact independent-night distributions. Complete per-point results remain
 # in the full summaries; these do not replace any channel records.
 rows=[]
 for keys,g in n.groupby(['line','method','noise_sigma_mm','kind']):
  rows.append(dict(zip(['line','method','noise_sigma_mm','kind'],keys),channel_nights=len(g),median_pre_noise_ratio=g.ratio_pre_noise.median(),median_cal_noise_ratio=g.ratio_cal_noise.median(),worst_cal_noise_ratio=g.ratio_cal_noise.max(),cal_worsened_over10pct=int(g.ratio_cal_noise.gt(1.1).sum())))
 write(pd.DataFrame(rows),'noise_night_overview.csv')
 d=pd.DataFrame(key);b=d[d.method.eq('B0_raw')].set_index(['line','device_id','marker_name','date']);out=[]
 for _,r in d[~d.method.eq('B0_raw')].iterrows():
  z=b.loc[tuple(r[f] for f in ['line','device_id','marker_name','date'])];q=r.to_dict()
  for f in ['LF_Q95_Q05_mm','step_abs_P99_mm','drift10min_abs_P99_mm','drift30min_abs_P99_mm','drift60min_abs_P99_mm']:
   q['B0_'+f]=z[f];q['ratio_'+f]=r[f]/z[f] if z[f]>1e-10 else np.nan
  out.append(q)
 c=pd.DataFrame(out);write(c,'heldout_key_AB.csv')
 for line,g in c.groupby('line'):
  print('\nKEY',line)
  for method,z in g.groupby('method'):
   print(method,'LF median/worst',z.ratio_LF_Q95_Q05_mm.median(),z.ratio_LF_Q95_Q05_mm.max(),'step median/worst',z.ratio_step_abs_P99_mm.median(),z.ratio_step_abs_P99_mm.max(),'countsLF/step>10%',z.ratio_LF_Q95_Q05_mm.gt(1.1).sum(),z.ratio_step_abs_P99_mm.gt(1.1).sum())
   print(z.nlargest(2,'ratio_LF_Q95_Q05_mm')[['device_id','marker_name','date','B0_LF_Q95_Q05_mm','LF_Q95_Q05_mm','ratio_LF_Q95_Q05_mm']].to_string(index=False))
 print(pd.DataFrame(rows).to_string(index=False))

if __name__=='__main__':main()
