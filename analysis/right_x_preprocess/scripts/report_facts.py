from common import *

def main():
 facts={};c=pd.read_csv(O/'heldout_key_AB.csv',dtype={'device_id':str});summary=[]
 for keys,g in c.groupby(['line','method']):
  r=dict(zip(['line','method'],keys),channel_nights=len(g))
  for kind,z in [('all',g),('node',g[g.kind.eq('node')]),('reference',g[g.kind.eq('reference')])]:
   for f in ['LF_Q95_Q05_mm','step_abs_P99_mm']:
    r[kind+'_'+f+'_ratio_median']=z['ratio_'+f].median();r[kind+'_'+f+'_ratio_worst']=z['ratio_'+f].max();r[kind+'_'+f+'_gt1p1_count']=int(z['ratio_'+f].gt(1.1).sum())
  summary.append(r)
 write(pd.DataFrame(summary),'comparison_overview.csv');facts['key_overview']=summary
 cov=pd.read_csv(O/'coverage_runtime_validation.csv',dtype={'device_id':str});cov=cov[(cov.line.eq('right')&cov.date.ge('2026-11-07'))|cov.line.eq('left')];cost=[]
 for keys,g in cov.groupby(['line','method']):
  r=dict(zip(['line','method'],keys),pre_changed_point_frames=int(g.pre_changed_point_frames.sum()),pre_eligible_point_frames=int(g.pre_eligible_point_frames.sum()),frames=int(g.frames.sum()),pre_us_median_of_windows=g.pre_us_median.median(),core_us_median_of_windows=g.core_us_median.median(),pre_us_largest_window_median=g.pre_us_median.max(),core_us_largest_window_P99=g.core_us_P99.max(),degraded_frames=int(g.degraded_frames.sum()),N3_qualified_fraction=np.average(g.N3_confident_fraction,weights=g.frames),projection_fail_frames=int(g.N3_projection_fail_frames.sum()));cost.append(r)
 write(pd.DataFrame(cost),'runtime_overview.csv');facts['cost']=cost
 modes=pd.read_csv(O/'mode_stability_validation.csv',dtype={'device_id':str});modes=modes[(modes.line.eq('right')&modes.date.ge('2026-11-07'))|modes.line.eq('left')]
 facts['mode_learning']=[dict(line=l,method=m,changed_learning_nights=int(g.learn_Jaccard_vs_B0.lt(.99999).sum()),median_max_subspace_angle_deg=g.largest_subspace_angle_vs_B0_degrees.median(),worst_max_subspace_angle_deg=g.largest_subspace_angle_vs_B0_degrees.max()) for (l,m),g in modes.groupby(['line','method'])]
 safety=pd.read_csv(O/'signal_safety_overview.csv');facts['signal_safety']=safety[safety.stage.eq('validation')&safety.method.isin(['B0_raw','B2_N2_ab','B3_N3'])].to_dict('records')
 extra=pd.concat([pd.read_csv(p,dtype={'device_id':str}) for p in O.glob('extra_nontarget_key*.csv')]);facts['extra_propagation']=[dict(line=l,method=m,layer=layer,max_extra_nontarget_key_mm=g.max_extra_nontarget_key_mm.max(),worst=g.nlargest(1,'max_extra_nontarget_key_mm').to_dict('records')[0]) for (l,m,layer),g in extra[extra.stage.eq('validation')].groupby(['line','method','layer'])]
 n=pd.read_csv(O/'old_noise_components.csv');facts['old_noise']=[dict(kind=k,lag1_median=g.C0_residual_step_lag1_r.median(),sigma_proxy_mm_median=g.second_difference_white_sigma_proxy_mm.median(),common_correlation_median=g.raw_step_vs_C0_common_step_r.median()) for k,g in n.groupby('kind')]
 def clean(x):
  if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
  if isinstance(x,list):return [clean(v) for v in x]
  if isinstance(x,float) and not np.isfinite(x):return None
  return x
 (O/'report_facts.json').write_text(json.dumps(clean(facts),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n');print(pd.DataFrame(summary).to_string(index=False));print(pd.DataFrame(cost).to_string(index=False));print(pd.DataFrame(facts['mode_learning']).to_string(index=False));print(safety[safety.stage.eq('validation')&safety.method.isin(['B0_raw','B3_N3'])].to_string(index=False))

if __name__=='__main__':main()
