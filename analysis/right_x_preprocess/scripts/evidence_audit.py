from dataio import *

def main():
 checks=0;values=0;noisechecks=0
 for e in pd.read_csv(O/'event_index.csv',dtype={'device_id':str}).to_dict('records'):
  line,dev=e['line'],e['device_id'];names,methods,_,d=load(W/'validation'/f'clean_{line}_{dev}.bin');idx=pd.Index(d['ts']);source=pd.read_pickle(W/f'validation_{line}_{dev}.pkl').set_index(['timestamp','markerName'])
  for path in (O/'windows').glob(f'{e["event_id"]}_*.csv'):
   z=pd.read_csv(path);rows=source.reindex(pd.MultiIndex.from_frame(z[['timestamp_ms','marker_name']].rename(columns={'timestamp_ms':'timestamp','marker_name':'markerName'})));present=rows._source_rowid.notna().to_numpy();assert np.array_equal(rows['_source_rowid'].to_numpy()[present],z['source_rowid'].to_numpy()[present]);j=idx.get_indexer(z.timestamp_ms);k=np.array([names.index(n) for n in z.marker_name]);expected=d['raw'][j,k]
   assert np.allclose(expected,z.rawX_mm,equal_nan=True,atol=1e-9,rtol=0);assert np.allclose(d['field'][j,k],z.field_calX_mm_observation_only,equal_nan=True,atol=1e-9,rtol=0);values+=len(z)*2
   for mi,m in enumerate(methods):
    for layer in ['pre','cal']:assert np.allclose(d['methods'][layer][j,mi,k],z[m+'_'+layer+'X_mm'],atol=1e-9,rtol=0,equal_nan=True);values+=len(z)
   checks+=1
 for path in (O/'windows').glob('injection_*.csv'):
  a=pd.read_csv(path,dtype={'device_id':str});dev=str(a.device_id.iloc[0]);line=a.line.iloc[0];scenario=a.scenario.iloc[0];n,methods,_,d=load(W/'validation'/f'clean_{line}_{dev}.bin');kn,_,_,z=load(W/'validation'/f'{scenario}_1794423600000_{line}_{dev}.bin');j=pd.Index(d['ts']).get_indexer(z['ts']);k=kn.index(a.marker_name.iloc[0]);ni=n.index(a.marker_name.iloc[0]);assert np.array_equal(a.timestamp_ms,z['ts']);truth=z['raw'][:,k]-d['raw'][j,ni];assert np.allclose(truth,a.known_observation_increment_mm,atol=1e-9,rtol=0,equal_nan=True);checks+=1
  for mi,m in enumerate(methods):
   for layer in ['pre','cal']:expected=z['methods'][layer][:,mi,k]-d['methods'][layer][j,mi,ni];assert np.allclose(expected,a[m+'_'+layer+'_paired_response_mm'],atol=1e-9,rtol=0,equal_nan=True);values+=len(a)
 # Recompute complete-night noise sensitivities independently from saved
 # compact key streams rather than C++ accumulators or summary intermediates.
 for stage in ['old','validation']:
  for q in pd.read_csv(O/f'input_identity_{stage}.csv',dtype={'device_id':str}).to_dict('records'):
   line,dev=q['line'],q['device_id'];names,methods,_,d=load(W/stage/f'clean_{line}_{dev}.bin');time=pd.to_datetime(d['ts'],unit='ms',utc=True).tz_convert('Asia/Shanghai');hour=time.hour+time.minute/60+time.second/3600;nightdates=(time.normalize()-pd.to_timedelta(np.where(hour<7,1,0),unit='D')).strftime('%Y-%m-%d');mask=((hour<7)|(hour>=23+1/3))&(nightdates>=('2026-11-07' if stage=='validation' and line=='right' else '2026-11-05'));summary=pd.read_csv(O/f'noise_sensitivity_{stage}_{line}.csv',dtype={'device_id':str});summary=summary[summary.device_id.eq(dev)]
   for level in [1,2,3]:
    kn,_,_,z=load(W/stage/f'noise{level}_{line}_{dev}.bin');sigma=[0,.034778565088664073,.06955713017732815,.1391142603546563][level]
    for ki,name in enumerate(kn):
     i=names.index(name)
     for mi,m in enumerate(methods):
      r=summary[summary.method.eq(m)&summary.marker_name.eq(name)&np.isclose(summary.noise_sigma_mm,sigma)].iloc[0]
      for layer in ['pre','cal']:
       response=z['methods'][layer][:,mi,ki]-d['methods'][layer][:,mi,i];valid=mask&np.isfinite(response);expected=np.sqrt(np.mean(response[valid]**2));actual=r[layer+'_noise_sensitivity_RMSE_mm'];assert abs(expected-actual)<1e-9,(stage,dev,name,m,layer,expected,actual);noisechecks+=1
 # The reported stress failure must be a direct difference of paired
 # responses at an actual zero-injection point, not maxima subtraction.
 p=pd.read_csv(O/'windows/injection_multiple_step3.csv');r=p[p.time_beijing.str.contains('03:59:44.833')].iloc[0];assert r.known_observation_increment_mm==0;stress=abs(r.B3_N3_cal_paired_response_mm-r.B0_raw_cal_paired_response_mm);assert abs(stress-3.12726683822)<1e-9;checks+=1
 (O/'evidence_validation.json').write_text(json.dumps({'passed':True,'CSV_source_windows_checked':checks,'CSV_numeric_values_checked':values,'independent_noise_RMSE_checks':noisechecks,'stress_extra_key_mm':stress},indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS',checks,values,noisechecks,'stress',stress)

if __name__=='__main__':main()
