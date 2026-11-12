from dataio import *

def main():
 extras=[];changes=[];safety=[]
 for stage in ['old','validation']:
  w=pd.read_pickle(W/f'waveforms_{stage}.pkl');w['first_valid_delay_frames']=np.nan;w['delay95_after_first_valid_frames']=np.nan;w['delay95_seconds_from_scheduled_onset']=np.nan;w['delay95_seconds_after_first_valid']=np.nan
  idxw=w.set_index(['line','device_id','scenario','onset_beijing','marker_name','method','layer']).index
  for q in pd.read_csv(O/f'input_identity_{stage}.csv',dtype={'device_id':str}).to_dict('records'):
   line,dev=q['line'],q['device_id'];names,methods,fields,d=load(W/stage/f'clean_{line}_{dev}.bin');index=pd.Index(d['ts']);delta=d['methods']['pre'][:,1]-d['raw'];ji,ki=np.where(np.isfinite(delta)&(abs(delta)>1e-12))
   for j,k in zip(ji,ki):changes.append({'stage':stage,'line':line,'device_id':dev,'marker_name':names[k],'time_beijing':iso(d['ts'][j]),'rawX_mm':d['raw'][j,k],'N1_preX_mm':d['methods']['pre'][j,1,k],'delta_mm':delta[j,k]})
   for path in sorted((W/stage).glob(f'*_{line}_{dev}.bin')):
    if path.name.startswith(('clean_','noise')):continue
    kn,mm,ff,z=load(path)
    if not kn:continue # 333715 has no reference/node, not a zero-error test.
    scenario,onset,_,_=path.stem.rsplit('_',3);onset=int(onset);j=index.get_indexer(z['ts']);xi=[names.index(n) for n in kn];truth=z['raw']-d['raw'][j][:,xi];zero=np.isfinite(truth)&(abs(truth)<1e-9)
    for mi,method in enumerate(methods):
     for layer in ['pre','cal']:
      response=z['methods'][layer][:,mi]-d['methods'][layer][j,mi][:,xi];base=z['methods'][layer][:,0]-d['methods'][layer][j,0][:,xi];extra=response-base;valid=zero&np.isfinite(extra)
      where=np.where(valid,abs(extra),-1);pos=np.unravel_index(np.argmax(where),where.shape)
      extras.append({'stage':stage,'line':line,'device_id':dev,'method':method,'layer':layer,'scenario':scenario,'onset_beijing':iso(onset),'max_extra_nontarget_key_mm':max(0,float(where[pos])),'worst_marker':kn[pos[1]] if where[pos]>=0 else '', 'worst_time_beijing':iso(z['ts'][pos[0]]) if where[pos]>=0 else '', 'meaning':'candidate paired response minus B0 paired response, only key points with zero injected increment'})
      for k,name in enumerate(kn):
       key=(line,dev,scenario,iso(onset),name,method,layer);loc=np.flatnonzero(idxw==key)
       if not len(loc):continue
       valid=np.flatnonzero(np.isfinite(response[:,k])&np.isfinite(truth[:,k]));delay=w.iloc[loc[0]].delay95_frames
       if len(valid):
        w.loc[loc,'first_valid_delay_frames']=valid[0]
        if np.isfinite(delay):
         w.loc[loc,'delay95_after_first_valid_frames']=delay-valid[0];w.loc[loc,'delay95_seconds_from_scheduled_onset']=(z['ts'][int(delay)]-onset)/1000;w.loc[loc,'delay95_seconds_after_first_valid']=(z['ts'][int(delay)]-z['ts'][valid[0]])/1000
  base=w[w.method.eq('B0_raw')].set_index(['line','device_id','scenario','onset_beijing','marker_name','layer'])
  b=base.reindex(pd.MultiIndex.from_frame(w[['line','device_id','scenario','onset_beijing','marker_name','layer']]))
  w['delay95_delta_vs_B0_frames']=w.delay95_frames.to_numpy()-b.delay95_frames.to_numpy()
  # These tables are the canonical waveform evidence. Delays from the
  # scheduled onset include missing input; the new columns separate this.
  for line,g in w.groupby('line'):
   for layer,z in g.groupby('layer'):write_parts(z,f'waveforms/{stage}_{line}_{layer}.csv')
  w.to_pickle(W/f'waveforms_{stage}.pkl')
  for (line,method,layer),g in w.groupby(['line','method','layer']):
   for group,mask in [('single_node_1_3mm',g.scenario.str.match(r'.*(?:YXJ|ZXJ).*_step[13]$')),('ramps_1_3hour',g.scenario.str.startswith('nodes_ramp')),('small_step',g.scenario.eq('small_node_step')),('mode_aligned',g.scenario.str.startswith('mode_step')),('multi_point',g.scenario.str.startswith('multiple_step'))]:
    z=g[mask&g.target_injected]
    if z.empty:continue
    safety.append({'stage':stage,'line':line,'method':method,'layer':layer,'case_group':group,'target_cases':len(z),'minimum_retention':z.retained_fraction.min(),'maximum_retention':z.retained_fraction.max(),'retention_outside_0p9_1p1':int((z.retained_fraction.lt(.9)|z.retained_fraction.gt(1.1)).sum()),'max_waveform_RMSE_extra_vs_B0_mm':z.extra_response_RMSE_vs_B0_mm.max(),'maximum_slope_fraction_bias_abs':z.slope_fraction_bias.abs().max(),'maximum_delay95_frames_after_first_valid':z.delay95_after_first_valid_frames.max(),'maximum_added_delay95_vs_B0_frames':z.delay95_delta_vs_B0_frames.max(),'no_95pct_delay_defined_count':int(z.delay95_frames.isna().sum()),'delays_greater5_count':int(z.delay95_after_first_valid_frames.gt(5).sum())})
 write(pd.DataFrame(changes),'N1_changed_observations.csv');write(pd.DataFrame(safety),'signal_safety_overview.csv');write_parts(pd.DataFrame(extras),'extra_nontarget_key.csv');print(pd.DataFrame(safety).query("stage=='validation' and layer=='pre'").to_string(index=False))

if __name__=='__main__':main()
