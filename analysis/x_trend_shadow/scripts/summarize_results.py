from common import *

def concat(pattern):return pd.concat([pd.read_csv(p,dtype={'device_id':str}) for p in sorted(O.glob(pattern))],ignore_index=True)

def main():
 normal=concat('metrics/*.csv');keys=['line','device_id','marker_name','night','scope','method'];assert not normal.duplicated(keys).any(),'stale duplicate metric partitions';late=normal[normal.scope.eq('night23_07')&normal.night.ge('2026-11-09')&normal.method.isin(METHODS)];details=[];keysums=[]
 for (line,method),g in late.groupby(['line','method']):
  for label,z in [('all',g),('key',g[g.kind.isin(['reference','node'])]),('node',g[g.kind.eq('node')])]:
   r=dict(line=line,method=method,channel_group=label,marker_nights=len(z),start_night='2026-11-09',end_night='2026-11-11')
   for f in ['P95_P05_mm','PV_mm','step_P99_mm','slow30min_change_P99_mm','slow60min_change_P99_mm']:
    for control in ['B0','W3']:
     col='ratio_'+control+'_'+f;r['median_'+col]=z[col].median();r['worst_'+col]=z[col].max();r['worse10pct_'+control+'_'+f]=int(z[col].gt(1.1).sum())
   keysums.append(r)
   if method in ['A_thermal','B_event','C_reference','D_L1trend','D_W3_L1trend','E_residual_factor']:
    for f in ['P95_P05_mm','PV_mm','step_P99_mm']:
     worst=z.nlargest(1,'ratio_B0_'+f)
     if len(worst):details.append(dict(worst.iloc[0].to_dict(),worst_metric=f,channel_group=label))
 save(pd.DataFrame(keysums),'key_and_all_overview.csv');save(pd.DataFrame(details),'worst_marker_cases.csv')
 paths=[p for p in sorted((O/'safety').glob('*.csv')) if not p.stem.endswith('_manifest')];s=pd.concat([pd.read_csv(p,dtype={'device_id':str}) for p in paths+[p for p in sorted((O/'safety_E').glob('*.csv')) if not p.stem.endswith('_manifest')]],ignore_index=True);sk=['line','device_id','scenario','onset_beijing','evaluation_scope','method','marker_name'];assert not s.duplicated(sk).any(),'stale duplicate safety partitions';sums=[];fails=[]
 for (line,method,scenario),g in s[s.evaluation_scope.eq('whole_suffix')].groupby(['line','method','scenario']):
  z=g[g.target];nt=g[~g.target];r=dict(line=line,method=method,scenario=scenario,target_cases=len(z),nontarget_cases=len(nt),minimum_retention=z.retention.min(),median_retention=z.retention.median(),maximum_retention=z.retention.max(),max_abs_additional_amplitude_loss_mm=z.additional_amplitude_loss_mm.abs().max(),median_additional_amplitude_loss_mm=z.additional_amplitude_loss_mm.median(),max_extra_waveform_RMSE_vs_B0_mm=z.extra_waveform_RMSE_vs_B0_mm.max(),median_extra_waveform_RMSE_vs_B0_mm=z.extra_waveform_RMSE_vs_B0_mm.median(),maximum_extra_delay95_vs_B0_seconds=z.extra_delay95_vs_B0_seconds.max(),median_extra_delay95_vs_B0_seconds=z.extra_delay95_vs_B0_seconds.median(),no_known95_delay_cases=int(z.delay95_known_seconds.isna().sum()),maximum_additional_slope_error_abs_mm_per_hour=z.additional_slope_error_mm_per_hour.abs().max(),median_additional_slope_error_abs_mm_per_hour=z.additional_slope_error_mm_per_hour.abs().median(),minimum_peak_retention=z.peak_retention.min(),median_peak_retention=z.peak_retention.median(),maximum_peak_retention=z.peak_retention.max(),max_extra_nontarget_peak_mm=nt.max_extra_response_vs_B0_mm.max());sums.append(r)
  if method in ['D_L1trend','A_thermal','C_reference','B_event','E_residual_factor']:
   for field,subset in [('additional_amplitude_loss_mm',z),('extra_delay95_vs_B0_seconds',z),('max_extra_response_vs_B0_mm',nt),('additional_slope_error_mm_per_hour',z)]:
    if subset[field].notna().any():
     w=subset.loc[subset[field].abs().idxmax()].to_dict();w['failure_metric']=field;fails.append(w)
 save(pd.DataFrame(sums),'signal_safety_overview.csv');save_parts(pd.DataFrame(fails),'injection_failure_index.csv')
 manifests=concat('safety/*_manifest.csv');save(manifests,'injection_manifest.csv');facts={'normal_overview':keysums,'safety':sums,'all_scenes':len(manifests),'all_safety_rows':len(s),'scene_Y_all_equal':bool(manifests.Y_bitwise.all()),'scene_original_alarm_passthrough':bool(manifests.original_alarm_passthrough.all()),'scene_numeric_failed_point_frames':int(manifests.L1_uncertified_point_frames.sum()),'scene_max_numeric_bound_mm':manifests.L1_max_numeric_bound_mm.max(),'worst_cases':details};save_json(facts,'result_facts.json')
 print(pd.DataFrame(keysums).query("channel_group=='key'")[['line','method','marker_nights','median_ratio_B0_P95_P05_mm','median_ratio_W3_P95_P05_mm','worst_ratio_B0_P95_P05_mm','median_ratio_B0_PV_mm','median_ratio_B0_slow60min_change_P99_mm']].to_string(index=False));print(pd.DataFrame(sums).query("method=='D_L1trend'").to_string(index=False));print('SCENES',len(manifests),'rows',len(s),'uncertified',manifests.L1_uncertified_point_frames.sum())

if __name__=='__main__':main()
