from common import *
import argparse,warnings

def quant(v,q):
 with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);return np.nanquantile(v,q,axis=0)

def measure(t,v):
 out={'rows':np.isfinite(v).sum(axis=0),'P95_P05_mm':quant(v,.95)-quant(v,.05),'PV_mm':quant(v,1)-quant(v,0)}
 diff=abs(np.diff(v,axis=0));dt=np.diff(t);diff[(dt<=0)|(dt>90000)]=np.nan;out['step_P99_mm']=quant(diff,.99)
 sm=pd.DataFrame(v.reshape(len(t),-1),index=pd.to_datetime(t,unit='ms',utc=True)).rolling('5min',min_periods=3).mean().to_numpy(copy=True).reshape(v.shape)
 count=pd.DataFrame(np.isfinite(v).reshape(len(t),-1).astype(int),index=pd.to_datetime(t,unit='ms',utc=True)).rolling('5min',min_periods=1).sum().to_numpy().reshape(v.shape);expected=np.arange(len(t))-np.searchsorted(t,t-300000,side='right')+1;sm[count!=expected[:,None,None]]=np.nan
 gap=np.maximum.accumulate(np.where(np.r_[False,np.diff(t)>90000],t,0));sm[(gap>0)&(t-gap<300000)]=np.nan;out['slow5_P95_P05_mm']=quant(sm,.95)-quant(sm,.05);runs=np.cumsum(np.r_[False,np.diff(t)>90000]);bad=np.cumsum(~np.isfinite(v),axis=0)
 for mins in [30,60]:
  j=pd.Index(t).get_indexer(t-mins*60000,method='nearest',tolerance=90000);ok=j>=0;j=np.maximum(j,0);ok&=(runs==runs[j]);delta=abs(sm-sm[j]);delta[~ok]=np.nan;delta[bad!=bad[j]]=np.nan;out[f'slow{mins}min_change_P99_mm']=quant(delta,.99)
 a=v[t<t[0]+1800000];b=v[t>=t[-1]-1800000];out['first_last30_median_delta_mm']=quant(b,.5)-quant(a,.5)
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');a=p.parse_args();devices=[];allratios=[];transitions=[];allcounts=[]
 for q in roster():
  dev,line=q['device_id'],q['line']
  if a.focus and dev not in FOCUS:continue
  folder=W/line/dev;src=load_data(line,dev);d=np.load(folder/'normal.npz');c=np.load(folder/('final_candidates.npz' if (folder/'final_candidates.npz').exists() else 'extended_candidates.npz' if (folder/'extended_candidates.npz').exists() else 'candidates.npz'));t=src['t'];names=src['names'].tolist();base=d['base'];w3=d['w3'];out=c['out'];eligible=c['eligible'];diag=c['diagnostics'];mode=c['mode'];event=c['event'];status=pd.read_csv(folder/'normal_frames.csv');h,night=clocks(t);values=np.concatenate([base[:,:,None],w3[:,:,None],out,src['x'][:,:,None],src['field'][:,:,None]],axis=2);labels=METHODS[:out.shape[2]+2]+['Raw','Stored_calX'];n_alg=out.shape[2]+2;shared=status.base_ready.eq(1).to_numpy()&status.w3_ready.eq(1).to_numpy()&status.base_gate.ge(.99999).to_numpy()&status.w3_gate.ge(.99999).to_numpy()&status.base_ncorrected.gt(0).to_numpy()&status.w3_ncorrected.gt(0).to_numpy();rows=[]
  for date in sorted(set(night)):
   nw=(night==date)&((h>=23)|(h<7));ids=np.flatnonzero(nw)
   if len(ids)<20:continue
   for scope,mask in [('night23_07',nw),('shared_core_active',nw&shared)]:
    ids=np.flatnonzero(mask)
    if len(ids)<20:continue
    v=values[ids].copy();valid=np.isfinite(src['x'][ids])&np.isfinite(v[:,:,:n_alg]).all(axis=2);v[~valid]=np.nan;mm=measure(t[ids],v)
    for i,n in enumerate(names):
     for mi,m in enumerate(labels):
      if mm['rows'][i,mi]<20:continue
      r={f:float(z[i,mi]) for f,z in mm.items()};r.update(line=line,device_id=dev,marker_name=n,kind=kind(n),night=date,scope=scope,method=m,start_beijing=iso(t[ids[0]]),end_beijing=iso(t[ids[-1]]),development_or_forward='forward_historical' if date>='2026-11-09' else 'development',missing_source_or_window=bool(len(ids)<470))
      if mi<n_alg:
       delta=v[:,i,mi]-v[:,i,0];r['difference_vs_B0_abs_P99_mm']=quant(abs(delta)[:,None,None],.99)[0,0];r['difference_vs_B0_abs_max_mm']=quant(abs(delta)[:,None,None],1)[0,0];r['changed_fraction']=float(np.mean(abs(delta[np.isfinite(delta)])>1e-6));r['eligible_fraction']=float(eligible[ids,i,mi-2].mean()) if mi>=2 else 1.;r['motion_fraction']=float((mode[ids,i]==1).mean()) if mi==3 else np.nan;r['event_frames']=int(event[ids,i].sum()) if mi==3 else 0
       for f in ['P95_P05_mm','PV_mm','step_P99_mm','slow5_P95_P05_mm','slow30min_change_P99_mm','slow60min_change_P99_mm']:
        r['B0_'+f]=mm[f][i,0];r['W3_'+f]=mm[f][i,1];r['ratio_B0_'+f]=mm[f][i,mi]/mm[f][i,0] if mm[f][i,0]>1e-9 else np.nan;r['ratio_W3_'+f]=mm[f][i,mi]/mm[f][i,1] if mm[f][i,1]>1e-9 else np.nan
      rows.append(r)
   # Transition relative to original, includes morning taper to exact day.
   for label,wm in [('night_start',(night==date)&(h>=22+40/60)&(h<23+40/60)),('morning',(night==date)&(h>=6+50/60)&(h<7+40/60))]:
    js=np.flatnonzero(wm)
    if len(js)<3:continue
    dt=np.diff(t[js]);good=(dt>0)&(dt<=90000)
    for i,n in enumerate(names):
     for mi,m in enumerate(METHODS[2:n_alg]):
      extra=out[js,i,mi]-base[js,i];step=abs(np.diff(extra));step[~good]=np.nan;transitions.append(dict(line=line,device_id=dev,marker_name=n,night=date,transition=label,method=m,extra_step_max_mm=float(quant(step[:,None,None],1)[0,0]),extra_step_P99_mm=float(quant(step[:,None,None],.99)[0,0]),last_available_extra_mm=float(extra[-1]),unit='mm; paired extra change relative B0, original changes separate'))
  frame=pd.DataFrame(rows);save_parts(frame,f'metrics/{line}_{dev}.csv');allratios.append(frame[frame.method.isin(METHODS)&frame.scope.eq('night23_07')&frame.night.ge('2026-11-09')]);allcounts.append({'line':line,'device_id':dev,'points':len(names),'frames':len(t),'A_changed_point_frames':int((abs(out[:,:,0]-base)>1e-6).sum()),'B_changed_point_frames':int((abs(out[:,:,1]-base)>1e-6).sum()),'C_changed_point_frames':int((abs(out[:,:,2]-base)>1e-6).sum()),'A_eligible_point_frames':int(eligible[:,:,0].sum()),'B_eligible_point_frames':int(eligible[:,:,1].sum()),'C_eligible_point_frames':int(eligible[:,:,2].sum()),'reference_latch_frames':int(diag[:,2].sum()),'reference_quality_frames':int(diag[:,1].sum())})
  for keys,g in frame[frame.method.isin(METHODS)].groupby(['night','scope','method']):
   r=dict(zip(['night','scope','method'],keys),line=line,device_id=dev,markers=len(g))
   for f in ['P95_P05_mm','PV_mm','step_P99_mm','slow30min_change_P99_mm','slow60min_change_P99_mm']:
    r['median_'+f]=g[f].median();r['worst_'+f]=g[f].max();r['median_ratio_B0_'+f]=g['ratio_B0_'+f].median();r['median_ratio_W3_'+f]=g['ratio_W3_'+f].median();r['worst_ratio_B0_'+f]=g['ratio_B0_'+f].max();r['worst_marker_'+f]=g.loc[g[f].idxmax(),'marker_name']
   r['mean_eligible_fraction']=g.eligible_fraction.mean();r['mean_changed_fraction']=g.changed_fraction.mean();devices.append(r)
  print(line,dev,'metric rows',len(rows),flush=True)
 save_parts(pd.DataFrame(devices),'device_metrics_'+('focus' if a.focus else 'all')+'.csv');save_parts(pd.DataFrame(transitions),'night_day_transitions'+('_focus' if a.focus else '')+'.csv');save(allcounts,'candidate_coverage'+('_focus' if a.focus else '')+'.csv');d=pd.concat(allratios,ignore_index=True);summary=[]
 for (line,m),g in d.groupby(['line','method']):
  r={'line':line,'method':m,'marker_nights':len(g),'eligible_fraction_median':g.eligible_fraction.median(),'changed_fraction_median':g.changed_fraction.median()}
  for f in ['P95_P05_mm','PV_mm','step_P99_mm','slow30min_change_P99_mm','slow60min_change_P99_mm']:
   for control in ['B0','W3']:
    col='ratio_'+control+'_'+f;r['median_'+col]=g[col].median();r['worst_'+col]=g[col].max();r['worsened_over10pct_'+control+'_'+f]=int(g[col].gt(1.1).sum())
  summary.append(r)
 summary=pd.DataFrame(summary);save(summary,'comparison_'+('focus' if a.focus else 'all')+'.csv');print(summary[['line','method','marker_nights','median_ratio_B0_P95_P05_mm','median_ratio_W3_P95_P05_mm','median_ratio_B0_PV_mm','median_ratio_W3_PV_mm','median_ratio_B0_step_P99_mm','worst_ratio_B0_P95_P05_mm','changed_fraction_median']].to_string(index=False))

if __name__=='__main__':main()
