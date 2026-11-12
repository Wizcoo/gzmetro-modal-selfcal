from dataio import *
import argparse

def main(stage):
 inputs=pd.read_csv(O/f'input_identity_{stage}.csv',dtype={'device_id':str});keyrows=[];noiseall=[];mode=[];wave=[];extra=[];coverage=[]
 for q in inputs.to_dict('records'):
  line,dev=q['line'],q['device_id'];names,methods,fields,d=load(W/stage/f'clean_{line}_{dev}.bin');di={n:i for i,n in enumerate(fields)};t=d['ts'];dd=d['methods']['diag'];birth=pd.read_csv(W/stage/f'birth_{line}_{dev}.csv');allrows=[]
  for date,phase,st,en in windows(t,stage):
   native=(t>=st)&(t<en);actual=native&(dd[:,0,di['n_corrected']]>0)&(dd[:,0,di['gate']]>0)
   for i,name in enumerate(names):
    iskey=name.startswith(('YJ','YXJ','ZJ','ZXJ'));kind='node' if name.startswith(('YXJ','ZXJ')) else 'reference' if name.startswith(('YJ','ZJ')) else 'ordinary'
    for scope,mask in [('native_window',native)]+([('same_B0_active',actual)] if iskey and phase=='night' else []):
     if mask.sum()<20:continue
     series=[('raw','raw',d['raw'][:,i]),('observed_field','stored_cal',d['field'][:,i])]+[(method,layer,d['methods'][layer][:,mi,i]) for mi,method in enumerate(methods) for layer in ['pre','cal']]
     for method,layer,v in series:
      good=mask&np.isfinite(d['raw'][:,i])&np.isfinite(v)
      if good.sum()<20:continue
      row=metrics(t[good],v[good]);row.update(line=line,device_id=dev,marker_name=name,kind=kind,date=date,phase=phase,scope=scope,method=method,layer=layer,stage=stage,split='old_development' if line=='right' and date<'2026-11-07' else 'right_unseen_nights' if line=='right' else 'left_transfer')
      if scope=='native_window':allrows.append(row)
      if iskey:keyrows.append(row)
   for mi,method in enumerate(methods):
    z=dd[native,mi]
    if not len(z):continue
    coverage.append({'line':line,'device_id':dev,'date':date,'phase':phase,'method':method,'stage':stage,'frames':len(z),'B0_active_frames':int(actual.sum()),'degraded_frames':int((z[:,di['state_code']]==5).sum()),'pre_changed_point_frames':int(z[:,di['pre_changed']].sum()),'pre_eligible_point_frames':int(z[:,di['pre_eligible']].sum()),'input_point_frames':len(z)*len(names),'pre_us_median':np.median(z[:,di['pre_us']]),'core_us_median':np.median(z[:,di['core_us']]),'core_us_P99':np.quantile(z[:,di['core_us']],.99),'Y_mismatch_count':z[:,di['Y_mismatch_count']].sum(),'N3_confident_fraction':z[:,di['common_qualified']].mean(),'N3_projection_fail_frames':int(z[:,di['projection_failed']].sum()),'N3_max_projection_leakage':z[:,di['projection_leakage']].max(),'max_pre_delta_mm':z[:,di['max_pre_delta_mm']].max(),'learning_fit_RMS_mm_mean':np.nanmean(z[:,di['learning_fit_RMS_mm']]) if np.isfinite(z[:,di['learning_fit_RMS_mm']]).any() else np.nan})
  ar=pd.DataFrame(allrows)
  for phase,g in ar.groupby('phase'):write_parts(g,f'full_metrics/{stage}_{line}_{dev}_{phase}.csv')
  # Field records are observations only; mode stability uses actual simulator
  # A and learning sets, with subspace angles invariant to sign/rotation.
  base=birth[birth.method.eq('B0_raw')]
  for (method,nid),g in birth.groupby(['method','night_id']):
   b=base[base.night_id.eq(nid)].set_index('marker');g=g.set_index('marker').reindex(b.index);mask=g.learn.eq(1)&b.learn.eq(1);angle=np.nan
   if mask.sum()>=3:
    A=b.loc[mask,['A1','A2','A3']].to_numpy();B=g.loc[mask,['A1','A2','A3']].to_numpy();sv=np.linalg.svd(np.linalg.qr(A)[0].T@np.linalg.qr(B)[0],compute_uv=False);angle=np.degrees(np.arccos(np.clip(sv.min(),-1,1)))
   mode.append({'line':line,'device_id':dev,'stage':stage,'method':method,'night_id':nid,'date':pd.Timestamp(nid,unit='D').strftime('%Y-%m-%d'),'learn_count':int(g.learn.sum()),'use_count':int(g.use.sum()),'n_history':g.n_history.max(),'learn_Jaccard_vs_B0':(g.learn.eq(1)&b.learn.eq(1)).sum()/max(1,(g.learn.eq(1)|b.learn.eq(1)).sum()),'largest_subspace_angle_vs_B0_degrees':angle,'baseline_change_abs_max_mm':(g.baseline_mm-b.baseline_mm).abs().max(),'meaning':'changed statistics from full preprocessed history, not proven accuracy'})
  n=pd.read_csv(W/stage/f'noise_{line}_{dev}.csv');n['stage']=stage;n['kind']=np.where(n.marker.str.startswith(('YXJ','ZXJ')),'node',np.where(n.marker.str.startswith(('YJ','ZJ')),'reference','ordinary'));n['date']=pd.to_datetime(n.night_id,unit='D').dt.strftime('%Y-%m-%d');n=n[n.date.ge('2026-11-05')]
  if stage=='validation' and line=='right':n=n[n.date.ge('2026-11-07')]
  noiseall.append(n)
  index=pd.Index(t)
  for path in sorted((W/stage).glob(f'*_{line}_{dev}.bin')):
   if path.name.startswith(('clean_','noise')):continue
   kn,mm,ff,z=load(path);scenario,onset,_,_=path.stem.rsplit('_',3);onset=int(onset);j=index.get_indexer(z['ts']);assert (j>=0).all();xi=[names.index(n) for n in kn];truth=z['raw']-d['raw'][j][:,xi];late=z['ts']>=onset+210*60000
   for mi,method in enumerate(methods):
    diag=z['methods']['diag'][:,mi];extra.append({'stage':stage,'line':line,'device_id':dev,'scenario':scenario,'onset_beijing':iso(onset),'method':method,'max_nontarget_pre_response_mm':diag[:,di['max_nontarget_pre_response_mm']].max(),'max_nontarget_cal_response_mm':diag[:,di['max_nontarget_cal_response_mm']].max(),'Y_mismatch_count':diag[:,di['Y_mismatch_count']].sum()})
    for k,name in enumerate(kn):
     true=truth[:,k];finite=np.isfinite(true)
     if not finite.any():continue
     peak=np.nanmax(abs(true));target=peak>1e-9
     for layer in ['pre','cal']:
      response=z['methods'][layer][:,mi,k]-d['methods'][layer][j,mi,names.index(name)];base=z['methods'][layer][:,0,k]-d['methods'][layer][j,0,names.index(name)];valid=np.isfinite(response)&finite;ls=valid&late;amount=np.median(true[ls]) if ls.any() else np.nan;actual=np.median(response[ls]) if ls.any() else np.nan;delay=np.nan
      if abs(amount)>1e-9 and ('step' in scenario or scenario=='reference3'):
       ok=np.isfinite(response)&(response/amount>=.95)&(response/amount<=1.05)
       for h in range(len(ok)-4):
        if ok[h:h+5].all():delay=h;break
      slope=np.nan;slopetrue=np.nan;lag=np.nan
      if 'ramp' in scenario and target:
       duration=3 if '3h' in scenario else 1;mask=valid&(z['ts']<onset+duration*3600000);hours=(z['ts'][mask]-onset)/3600000
       if mask.sum()>=20:
        slope,intercept=np.polyfit(hours,response[mask],1);slopetrue=np.polyfit(hours,true[mask],1)[0];lag=-intercept/slope*3600 if abs(slope)>1e-9 else np.nan
      wave.append({'stage':stage,'line':line,'device_id':dev,'marker_name':name,'method':method,'layer':layer,'scenario':scenario,'onset_beijing':iso(onset),'target_injected':target,'peak_input_mm':peak,'stable_input_mm':amount,'stable_response_mm':actual,'retained_fraction':actual/amount if abs(amount)>1e-9 else np.nan,'response_RMSE_vs_known_input_mm':np.sqrt(np.mean((response[valid]-true[valid])**2)) if valid.any() else np.nan,'extra_response_RMSE_vs_B0_mm':np.sqrt(np.mean((response[valid]-base[valid])**2)) if valid.any() else np.nan,'positive_peak_bias_mm':np.nanmax(response)-np.nanmax(true),'negative_peak_bias_mm':np.nanmin(response)-np.nanmin(true),'max_abs_response_mm':np.nanmax(abs(response)),'delay95_frames':delay,'slope_mm_per_hour':slope,'slope_fraction_bias':slope/slopetrue-1 if abs(slopetrue)>1e-12 else np.nan,'ramp_equivalent_lag_seconds':lag,'interpretation':'paired observation-domain input response; not world displacement error'})
 # Persist only compact key tables and complete per-device metric partitions.
 for line,g in pd.DataFrame(keyrows).groupby('line'):write_parts(g,f'key_chain_metrics_{stage}_{line}.csv')
 write(pd.DataFrame(coverage),f'coverage_runtime_{stage}.csv');write(pd.DataFrame(mode),f'mode_stability_{stage}.csv');write(pd.DataFrame(extra),f'injection_non_target_{stage}.csv')
 waves=pd.DataFrame(wave)
 for line,g in waves.groupby('line'):
  for layer,z in g.groupby('layer'):write_parts(z,f'waveforms/{stage}_{line}_{layer}.csv')
 waves.to_pickle(W/f'waveforms_{stage}.pkl');noise=pd.concat(noiseall,ignore_index=True)
 for line,g in noise.groupby('line'):
  result=[]
  for keys,z in g.groupby(['line','device','method','noise_sigma_mm','marker','kind']):
   w=z.frames.to_numpy();r=dict(zip(['line','device_id','method','noise_sigma_mm','marker_name','kind'],keys));r['frames']=w.sum()
   for f in ['raw_noise_RMSE_mm','pre_noise_sensitivity_RMSE_mm','cal_noise_sensitivity_RMSE_mm']:r[f]=np.sqrt(np.average(z[f].to_numpy()**2,weights=w))
   result.append(r)
  write(pd.DataFrame(result),f'noise_sensitivity_{stage}_{line}.csv')
 noise.to_pickle(W/f'noise_{stage}.pkl');print('Key chain rows',len(keyrows),'waveform rows',len(wave),'non-target rows',len(extra));print(pd.DataFrame(coverage).groupby('method')[['pre_changed_point_frames','pre_eligible_point_frames','N3_max_projection_leakage']].agg(['sum','max']).to_string())
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--stage',choices=['old','validation'],required=True);main(a.parse_args().stage)
