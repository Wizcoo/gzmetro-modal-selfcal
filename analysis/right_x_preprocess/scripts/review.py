from common import *

KEYS=['stage','line','device_id','marker_name','date','phase','scope']

def key_table(stage):
 paths=sorted(O.glob(f'key_chain_metrics_{stage}*.csv'))
 # old summaries initially used a single line file; avoid duplicate copies.
 if (O/f'key_chain_metrics_{stage}_right.csv').exists():paths=[p for p in paths if p.name!=f'key_chain_metrics_{stage}.csv']
 d=pd.concat([pd.read_csv(p,dtype={'device_id':str}) for p in paths],ignore_index=True)
 if stage=='validation':d=d[(d.line.eq('right')&d.date.ge('2026-11-07'))|d.line.eq('left')]
 return d

def compare(stage):
 d=key_table(stage);d=d[d.layer.eq('cal')&d.phase.eq('night')&d.scope.eq('same_B0_active')]
 b=d[d.method.eq('B0_raw')].set_index(KEYS);rows=[]
 for method,g in d[d.method.str.startswith('B')].groupby('method'):
  if method=='B0_raw':continue
  for _,r in g.iterrows():
   k=tuple(r[x] for x in KEYS)
   if k not in b.index:continue
   z=b.loc[k];out={x:r[x] for x in KEYS};out.update(method=method,kind=r['kind'],rows=r['rows'])
   for f in ['LF_Q95_Q05_mm','step_abs_P99_mm','drift10min_abs_P99_mm','drift30min_abs_P99_mm','drift60min_abs_P99_mm','first_last30_median_change_mm']:
    out['B0_'+f]=z[f];out[f]=r[f];out['ratio_'+f]=r[f]/z[f] if abs(z[f])>1e-10 else np.nan
   rows.append(out)
 result=pd.DataFrame(rows)
 write(result,f'key_AB_ratios_{stage}.csv')
 return result

def main():
 for stage in ['old','validation']:
  if not list(O.glob(f'key_chain_metrics_{stage}*.csv')):continue
  d=compare(stage)
  for line,g in d.groupby('line'):
   print('\n',stage,line,'key channel-nights',len(g)//4)
   for method,z in g.groupby('method'):
    print(method,'LF median/max',z.ratio_LF_Q95_Q05_mm.median(),z.ratio_LF_Q95_Q05_mm.max(),'step',z.ratio_step_abs_P99_mm.median(),z.ratio_step_abs_P99_mm.max(),'LF>10%',z.ratio_LF_Q95_Q05_mm.gt(1.1).sum(),'step>10%',z.ratio_step_abs_P99_mm.gt(1.1).sum())
    print(z.nlargest(2,'ratio_LF_Q95_Q05_mm')[['device_id','marker_name','date','B0_LF_Q95_Q05_mm','LF_Q95_Q05_mm','ratio_LF_Q95_Q05_mm']].to_string(index=False))
  for p in O.glob(f'noise_sensitivity_{stage}*.csv'):
   n=pd.read_csv(p,dtype={'device_id':str});base=n[n.method.eq('B0_raw')].set_index(['line','device_id','noise_sigma_mm','marker_name'])
   print('\n',p.name)
   for method,g in n.groupby('method'):
    b=base.reindex(pd.MultiIndex.from_frame(g[['line','device_id','noise_sigma_mm','marker_name']]))
    print(method,'paired noise calRMSE ratio median',np.median(g.cal_noise_sensitivity_RMSE_mm.to_numpy()/b.cal_noise_sensitivity_RMSE_mm.to_numpy()),'pre/raw',np.median(g.pre_noise_sensitivity_RMSE_mm/g.raw_noise_RMSE_mm))
  f=W/f'waveforms_{stage}.pkl'
  if not f.exists():continue
  w=pd.read_pickle(f);w=w[w.target_injected]
  for (line,layer),gg in w.groupby(['line','layer']):
   print('\nWAVE',stage,line,layer)
   for method,g in gg.groupby('method'):
    s=g[g.scenario.str.contains('step|ramp',regex=True)&~g.scenario.str.contains('mode')];print(method,'step/ramp retention range',s.retained_fraction.min(),s.retained_fraction.max(),'max extraB0 RMSE',g.extra_response_RMSE_vs_B0_mm.max(),'delay max',s.delay95_frames.max(),'ramp slope bias abs max',s.slope_fraction_bias.abs().max())

if __name__=='__main__':main()
