"""Read-only evidence checks; writes validation.json and file_catalog.csv only."""
from relations import *
import hashlib,sys,platform,csv

def close(a,b):
    assert np.allclose(np.asarray(a,float),np.asarray(b,float),atol=2e-9,rtol=2e-10,equal_nan=True)

def independent_lf(t,v):
    # Recompute from exported values, including native gaps and invalid rows.
    good=np.isfinite(v);t=np.asarray(t)[good];v=np.asarray(v)[good]
    out=[];cuts=np.r_[0,np.flatnonzero(np.diff(t)>90000)+1,len(t)]
    for a,b in zip(cuts[:-1],cuts[1:]):
        z=pd.Series(v[a:b],index=pd.to_datetime(t[a:b],unit='ms',utc=True))
        out.extend(z.rolling('5min',min_periods=3).median().tolist())
    return np.nanquantile(out,.95)-np.nanquantile(out,.05)

def main():
    checks={};refs=load_refs();expected=refs.groupby('channel').size();total=0
    paths=list((O/'observed_traces').glob('*.csv'));assert len(paths)==20
    for p in paths:
        q=pd.read_csv(p,dtype={'observing_device_id':str});ch=q.observing_device_id.iloc[0]+':'+q.markerName.iloc[0]
        src=refs[refs.channel.eq(ch)].sort_values('timestamp');q=q.sort_values('timestamp')
        assert len(q)==expected[ch] and not q.timestamp.duplicated().any()
        assert np.array_equal(q.timestamp,src.timestamp)
        for f in ['x','y','calX','calY','RoiCalState','_source_rowid']:close(q[f],src[f])
        assert np.array_equal(q.source_db,src.source_db) and np.array_equal(q.valid,src.valid)
        total+=len(q)
    checks['full_resolution_observed_rows_match_deduplicated_source']=total
    checks['observed_channels']=len(paths)
    metrics=pd.read_csv(O/'candidate_metrics.csv');n=0;ymatches=0
    for p in (O/'candidate_traces').glob('*.csv'):
        q=pd.read_csv(p,dtype={'observing_device_id':str});ch=q.observing_device_id.iloc[0]+':'+q.markerName.iloc[0];fold=q.fold.iloc[0]
        assert q.fit_night.iloc[0]!=q.holdout_night.iloc[0] and q.candidate_Y_equals_recorded_calY.all()
        src=refs[refs.channel.eq(ch)].set_index('timestamp').loc[q.timestamp]
        close(q.calY,src.calY);ymatches+=len(q)
        st=epoch(q.holdout_night.iloc[0]+' 23:20');en=st+460*60000
        core=q.timestamp.ge(st)&q.timestamp.lt(en)&q.valid
        methods={'raw_X':'x','V51_field_record':'calX','A_YJ_guided':'A_X_mm','B_graph_residual':'B_X_mm'}
        for scope,mask in [('all_valid_with_recorded_fallback',core),('paired_candidate_available',core&q.A_applied&(q.B_applied if ':YXJ' in ch else True))]:
            if mask.sum()<20:continue
            for method,col in methods.items():
                row=metrics[metrics.fold.eq(fold)&metrics.channel.eq(ch)&metrics.method.eq(method)&metrics.evaluation_scope.eq(scope)]
                assert len(row)==1
                ts=q.loc[mask,'timestamp'].to_numpy();v=q.loc[mask,col].to_numpy();finite=np.isfinite(v);ts=ts[finite];v=v[finite];dt=np.diff(ts)
                close([independent_lf(ts,v)],[row.lowfreq_p95_p05_range_mm.iloc[0]])
                adj=(dt>=30000)&(dt<=90000);close([np.quantile(abs(np.diff(v)[adj]),.99)],[row.step_abs_p99_mm.iloc[0]])
                assert len(v)==row.n.iloc[0];n+=1
    assert n==len(metrics)
    checks['candidate_summary_rows_independently_recomputed_from_CSV']=n
    checks['candidate_Y_rows_equal_recorded_Y']=ymatches
    models=pd.read_csv(O/'frozen_response_models.csv');audit=pd.read_csv(O/'reference_group_qualification.csv').fillna('')
    bound={'YXJ2':'780639298317','YXJ3':'780639333715','YXJ4':'780639346578','YXJ5':'780639376393','YXJ6':'780639414923'}
    for _,r in models.iterrows():
        assert r.fit_night!=r.holdout_night
        if not r.qualified:continue
        if r.method=='B_graph_residual':assert set(json.loads(r.groups))<={r.channel.split(':')[0],bound[r.channel.split(':')[1]]}
    for _,r in audit.iterrows():
        if r.excluded_physical_reference:assert all(c.split(':')[1]!=r.excluded_physical_reference for c in r.input_references.split('|') if c)
    checks['frozen_fit_nights_B_endpoint_scope_and_global_YJ_LOPO_verified']=True
    inj=pd.read_csv(O/'displacement_injection_results.csv');count=0
    for p in (O/'injection_traces').glob('*.csv'):
        q=pd.read_csv(p);scenario=q.scenario.iloc[0];ch=q.channel.iloc[0];method=q.method.iloc[0]
        before=q.timestamp.lt(epoch('2026-11-07 03:00'));close(q.loc[before,'raw_injection_X_mm'],0);close(q.loc[before,'raw_injection_Y_mm'],0)
        close(q.candidate_output_delta_Y_mm,q.source_V51_output_delta_Y_mm)
        mask=q.timestamp.ge(epoch('2026-11-07 04:30'))&q.timestamp.lt(epoch('2026-11-07 07:00'))
        axis='Y' if scenario=='target_Y_settlement' else 'X';row=inj[inj.scenario.eq(scenario)&inj.channel.eq(ch)&inj.method.eq(method)];assert len(row)==1
        truth=q.loc[mask,'raw_injection_'+axis+'_mm'].median();delta=q.loc[mask,'candidate_output_delta_'+axis+'_mm'].median()
        close([truth,delta],row[['raw_injected_increment_mm','candidate_increment_mm']].iloc[0])
        if abs(truth)>.5:close([delta/truth],row.retained_fraction_if_target_injected)
        else:close([q.loc[mask,'candidate_output_delta_'+axis+'_mm'].abs().max()],row.spurious_change_if_target_not_injected_mm)
        count+=1
    assert count==72 and len(inj)==108
    checks['full_injection_traces_checked']=count
    runs=pd.concat([pd.read_csv(O/'controlled_replay_runs.csv'),pd.read_csv(O/'extra_reference_fault_runs.csv')]);assert len(runs)==60 and runs.exit_code.eq(0).all()
    for dev in DEVS:
        base=pd.read_csv(W/'replay_cache'/f'V51_cold_none_{dev}.csv')
        for mode in ['include_YJ','exclude_YXJ']:
            q=pd.read_csv(W/'replay_cache'/f'{mode}_none_{dev}.csv');close(q.replayY_mm,base.replayY_mm)
    checks['successful_actual_source_runs']=len(runs)
    checks['source_prefix_variants_Y_identical_to_default_source']=True
    pr=json.loads((O/'provenance.json').read_text(encoding='utf-8'));repo=Path(os.environ.get('YJ_ANALYSIS_REPOSITORY',Path(__file__).resolve().parents[3]))
    manifest=json.loads((repo/'docs/source_manifest.json').read_text(encoding='utf-8'))
    for version,s in manifest['sources'].items():
        for file,meta in s['files'].items():assert hashlib.sha256((repo/'versions'/version/file).read_bytes()).hexdigest()==meta['sha256']
    assert hashlib.sha256((repo/'data/manifest.json').read_bytes()).hexdigest()==pr['input_manifest_sha256']
    input_manifest=json.loads((repo/'data/manifest.json').read_text(encoding='utf-8'));parts=0
    for source in input_manifest['sources']:
        if source['line']!='right':continue
        for table in source['tables']:
            for part in table['files']:
                assert hashlib.sha256((repo/part['path']).read_bytes()).hexdigest()==part['sha256'];parts+=1
    checks['right_input_gzip_parts_SHA256_verified']=parts
    checks['production_V51_V53_hashes_unchanged']=True
    files=[p for p in O.rglob('*') if p.is_file() and '.work' not in p.parts and '__pycache__' not in p.parts and p.name not in ['file_catalog.csv','validation.json']]
    catalog=[]
    for p in sorted(files):
        assert p.stat().st_size<2_000_000,str(p)
        rel=p.relative_to(O).as_posix();rows='';start='';end=''
        if p.suffix=='.csv':
            q=pd.read_csv(p);rows=len(q)
            if 'timestamp' in q and len(q):start=iso(int(q.timestamp.min()));end=iso(int(q.timestamp.max()))
            elif 'start_beijing' in q and len(q):start=str(q.start_beijing.min());end=str(q.end_exclusive_beijing.max()) if 'end_exclusive_beijing' in q else ''
        if p.suffix!='.png':
            raw=p.read_bytes();raw.decode('utf-8');assert b'\r\n' not in raw
        role='raw/cal reference observation' if rel.startswith('observed_traces/') else 'derived candidate with fallback' if rel.startswith('candidate_traces/') else 'known observation-domain injection increments' if rel.startswith('injection_traces/') else 'actual downstream only' if rel.startswith('downstream_traces/') else 'descriptive/model/protocol/source; see methodology'
        catalog.append({'path':rel,'bytes':p.stat().st_size,'rows_excluding_header':rows,'start_beijing_if_timestamp_column':start,'end_last_observation_or_exclusive_if_summary':end,'scope':role,'units':'X/Y/cal/candidate/delta:mm_API_contract; r/fraction:dimensionless; slope:mm_per_mm; timestamp:Unix_ms; scale/center:native_unverified; see methodology','window_rule':'full03day or fold/event as file/row; night core23:20-07:00 Beijing; see methodology','sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    write(pd.DataFrame(catalog),'file_catalog.csv')
    checks['catalogued_files_excluding_catalog_and_validation']=len(files)
    checks['all_files_under_2MB_and_text_UTF8_LF']=True
    result={'status':'PASS','checks':checks,'precision':'exported CSV compare atol2e-9 rtol2e-10','limitations':['Not exact deployed-state replay','No serial geometry or recomputed candidate X0','No physical ground truth or blind prospective acceptance','Variation reduction is not accuracy'],'catalog_excludes_itself_and_validation':True}
    (O/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
