from results import *
import ast,csv,platform,subprocess

def close(a,b,tol=2e-10):assert np.allclose(a,b,atol=tol,rtol=tol,equal_nan=True)
def same(a,b):assert np.array_equal(np.asarray(a).view('uint64'),np.asarray(b).view('uint64'))

def main():
    check={};normalpoints=0;normalframes=0;branches=0;Ycomparisons=0;fallback=0;cases=0;extraA=0.;legacyrows=0
    original=json.loads((R/'docs/source_manifest.json').read_text(encoding='utf-8'))
    for ver,meta in original['sources'].items():
        for f,s in meta['files'].items():assert sha(R/'versions'/ver/f)==s['sha256']
    check['production_V51_V53_SHA_unchanged']=True
    source_manifest=json.loads((R/'data/manifest.json').read_text(encoding='utf-8'));parts=0
    for source in source_manifest['sources']:
        if source['line']!='right':continue
        for table in source['tables']:
            for part in table['files']:assert sha(R/part['path'])==part['sha256'];parts+=1
    check['source_right_JSONL_parts_SHA_verified']=parts
    audit=pd.read_csv(O/'run_audit_final.csv');assert len(audit)==6 and audit.exit_code.eq(0).all() and audit.stdout.str.contains('Y_bitwise=PASS identity_bitwise=PASS').all()
    target=pd.read_csv(O/'injection_target_manifest.csv',dtype={'device_id':str});summary=pd.read_csv(O/'ablation_results.csv');manifest=pd.read_csv(O/'input_identity.csv',dtype={'device_id':str})
    injected_summary=pd.read_pickle(W/'injections_final.pkl');metrics_checked=0;loo_independence=0
    for dev in DEVS:
        names,modes,fields,d=load(W/'final'/f'normal_{dev}.bin');di={f:i for i,f in enumerate(fields)};assert len(modes)==10;normalpoints+=len(d)*len(names);normalframes+=len(d);branches+=len(modes);Ycomparisons+=len(d)*len(names)*(len(modes)-1)
        md=pd.read_pickle(C/f'Marker_{dev}.pkl');p=md.pivot(index='timestamp',columns='markerName',values=['x','y','RoiCalState']);assert names==sorted(md.markerName.unique());assert np.array_equal(d['ts'],p.index)
        for field,raw in [('x','rawx'),('y','rawy')]:
            v=p[field].reindex(columns=names).to_numpy(float,copy=True);v[p.RoiCalState.reindex(columns=names).to_numpy()!=1]=np.nan;same(d[raw],v)
        assert sha(W/f'{dev}.bin')==manifest.set_index('device_id').loc[dev,'input_sha256']
        assert not d['methods']['diag'][:,:,di['Y_mismatch_count']].any();same(d['methods']['x'][:,0],d['methods']['x'][:,1])
        ea_names,ea_modes,_,ea=load(W/'ea'/f'normal_{dev}.bin');assert ea_names==names
        for method in ea_modes:same(ea['methods']['x'][:,ea_modes.index(method)],d['methods']['x'][:,modes.index(method)])
        birth=pd.read_csv(W/'final'/f'birth_{dev}.csv')
        for nid,bs in birth.groupby('night_id'):
            ref=bs[bs.method.eq('identity')].sort_values('point_index')
            for method,g in bs.groupby('method'):
                g=g.sort_values('point_index');close(g[['A1','A2','A3','baseline_mm','cbar_mm']].to_numpy(),ref[['A1','A2','A3','baseline_mm','cbar_mm']].to_numpy(),0)
        for mi,m in enumerate(modes):
            if m in ['A','B0','B1','B2','E_Huber','E_full']:
                ix=d['methods']['diag'][:,mi,di['fallback_code']]>0;same(d['methods']['x'][ix,mi],d['methods']['x'][ix,0]);fallback+=int(ix.sum())
            if m=='A':extraA=max(extraA,float(np.nanmax(abs(d['methods']['x'][:,mi]-d['methods']['x'][:,0]))));assert extraA<=.2500000001
        # Independently evaluate all full-scope original/raw/field and candidate
        # LF/step summaries with a direct rolling-window definition.
        t=d['ts']
        for _,r in summary[summary.device_id.astype(str).eq(dev)].iterrows():
            i=names.index(r.marker_name);st=epoch(r.night+' 23:20');mask=(t>=st)&(t<st+460*60000)
            if r.scope=='same_original_active_frames':mask&=(d['methods']['diag'][:,0,di['n_corrected']]>0)&(d['methods']['diag'][:,0,di['gate']]>0)
            if 'LOPO' in r.method:
                a=modes.index('A');nid=int(pd.Timestamp(r.night).timestamp()/86400);br=birth[birth.method.eq('A')&birth.night_id.eq(nid)&birth.point_index.eq(i)].iloc[0];v=d['rawx'][:,i]-d['methods']['diag'][:,a,di['gate']]*(d['rawx'][:,i]-br.baseline_mm-d['methods']['loo'][:,a,i])
                if br.historical_explained_energy<.8:v=d['methods']['x'][:,a,i].copy()
                if r.method.startswith('V51_on'):v=np.where(np.isfinite(v),d['methods']['x'][:,0,i],np.nan)
            elif r.method=='raw_X':v=d['rawx'][:,i]
            elif r.method=='V51_field_observed':v=md[md.markerName.eq(r.marker_name)].set_index('timestamp').calX.reindex(t).to_numpy()
            else:v=d['methods']['x'][:,modes.index(r.method),i]
            mask&=np.isfinite(v)&np.isfinite(d['rawx'][:,i]);tt=t[mask];vv=v[mask];sm=[];start=0;runstart=0
            for j in range(len(tt)):
                if j and tt[j]-tt[j-1]>90000:runstart=j
                start=max(start,runstart)
                while tt[j]-tt[start]>=300000:start+=1
                sm.append(np.median(vv[start:j+1]) if j-start+1>=3 else np.nan)
            close([np.nanquantile(sm,.95)-np.nanquantile(sm,.05)],[r.LF_Q95_Q05_mm]);adj=(np.diff(tt)>=30000)&(np.diff(tt)<=90000);close([np.quantile(abs(np.diff(vv)[adj]),.99)],[r.step_abs_P99_mm]);assert len(tt)==r.rows;metrics_checked+=1
        # Optional legacy PR2 executable baseline, if already present locally.
        if os.environ.get('RX_PRIOR_REPLAY'):
            old=pd.read_csv(Path(os.environ['RX_PRIOR_REPLAY'])/f'V51_cold_none_{dev}.csv');ix=pd.Index(t).get_indexer(old.timestamp)
            for n,g in old.groupby('markerName'):
                j=pd.Index(t).get_indexer(g.timestamp);i=names.index(n);close(d['methods']['x'][j,0,i],g.replayX_mm,2e-12);close(d['y'][j,i],g.replayY_mm,2e-12);legacyrows+=len(g)
        for file in (W/'final').glob(f'*_{dev}.bin'):
            if file.name.startswith('normal_'):continue
            kn,mm,ff,z=load(file);assert mm==modes and ff==fields;scenario,onset,_=file.stem.rsplit('_',2);onset=int(onset);j=pd.Index(t).get_indexer(z['ts']);assert (j>=0).all();ix=[names.index(n) for n in kn];cases+=1;Ycomparisons+=len(z)*len(names)*(len(modes)-1);branches+=len(modes)
            row=target[target.device_id.eq(dev)&target.onset_beijing.eq(iso(onset))&target.scenario.eq(scenario)];assert len(row)==1;targets=str(row.target_names.iloc[0]).split('|');expected=d['rawx'][j][:,ix].copy();ey=d['rawy'][j][:,ix].copy();hrs=(z['ts']-onset)/3600000
            for k,n in enumerate(kn):
                if n not in targets:continue
                amp=row.amplitude_mm_at_target_or_max_key.iloc[0];delta=np.full(len(z),amp)
                if 'ramp' in scenario:delta=np.minimum(amp,hrs)
                if 'spike' in scenario:delta[1:]=0
                if scenario.startswith('modal'):
                    nid=int(pd.Timestamp(row.night.iloc[0]).timestamp()/86400);b=birth[birth.method.eq('identity')&birth.night_id.eq(nid)].set_index('point_index');keyids=[ii for ii,nn in enumerate(names) if nn.startswith(('YJ','YXJ')) and b.loc[ii,'use']==1];scale=max(abs(b.loc[keyids,'A1']));delta*=b.loc[names.index(n),'A1']/scale
                if scenario=='Y_settlement':ey[:,k]+=delta
                elif 'missing' in scenario:expected[hrs<1/6,k]=np.nan
                else:expected[:,k]+=delta
            close(z['rawx'],expected,2e-12);close(z['rawy'],ey,2e-12);same(z['methods']['x'][:,0],z['methods']['x'][:,1]);assert not z['methods']['diag'][:,:,di['Y_mismatch_count']].any()
            if scenario in ['single_ref1','single_ref3','reference_spike3']:
                a=modes.index('A')
                for k,n in enumerate(kn):
                    if n not in targets:continue
                    original=d['methods']['loo'][j,a,names.index(n)];modified=z['methods']['loo'][:,a,k];valid=np.isfinite(original)&np.isfinite(modified)
                    if valid.any():close(modified[valid]-original[valid],z['rawx'][valid,k]-d['rawx'][j[valid],names.index(n)]);loo_independence+=int(valid.sum())
            a=modes.index('A');extraA=max(extraA,float(np.nanmax(abs(z['methods']['x'][:,a]-z['methods']['x'][:,0]))) if len(kn) else 0);assert extraA<=.2500000001
            # Known absent-target cases independently verify snapshot clone
            # resumes all relevant channel state exactly, including D context.
            noop=(scenario.startswith('YXJ') and '_step' in scenario and scenario.split('_')[0] not in names) or (scenario=='Y_settlement' and 'YXJ5' not in names)
            if noop:
                for mi in range(len(modes)):same(z['methods']['x'][:,mi],d['methods']['x'][j,mi][:,ix])
    assert cases==336 and len(target)==336;assert branches==3420
    delay=pd.read_csv(O/'coefficient_delay_diagnostics.csv');valid=delay.response_identifiable.fillna(False).astype(bool)&delay.scenario.notna();ema=delay[valid&delay.method.eq('D_EMA')];kal=delay[valid&delay.method.eq('D_Kalman')];assert ema.coefficient_step95_delay_frames.max()<=5 and kal.coefficient_step95_delay_frames.max()<=5
    check.update(normal_full_device_frames=normalframes,normal_original_point_observations=normalpoints,independent_full_cold_streams=60,injection_cases=cases,injection_method_continuations=3360,Y_bitwise_point_comparisons_in_successful_driver_calls=Ycomparisons,identity_all_X_bitwise=True,normal_E_A_same_as_first_stage_bitwise=True,all_model_A_b_cbar_unchanged=True,strict_fallback_frames_checked=fallback,A_max_incremental_correction_mm=extraA,LOPO_target_injection_independence_rows_checked=loo_independence,source_input_shapes_and_reference_injections_checked=True,summary_LF_step_rows_independently_recomputed=metrics_checked,legacy_PR2_C0_reference_rows_checked=legacyrows,EMA_identifiable_step_cases=len(ema),EMA_max_delay_frames=ema.coefficient_step95_delay_frames.max(),Kalman_max_delay_frames=kal.coefficient_step95_delay_frames.max())
    files=[p for p in O.rglob('*') if p.is_file() and not any(x in p.parts for x in ['.work','__pycache__']) and p.name not in ['file_catalog.csv','validation.json']]
    catalog=[]
    for p in sorted(files):
        assert p.stat().st_size<2_000_000,str(p);rel=p.relative_to(O).as_posix()
        if p.suffix!='.png':raw=p.read_bytes();raw.decode('utf-8');assert b'\r\n' not in raw
        if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'))
        count=len(pd.read_csv(p)) if p.suffix=='.csv' else ''
        catalog.append({'path':rel,'bytes':p.stat().st_size,'rows_excluding_header':count,'sha256':sha(p),'window':'2026-11-05..07 Beijing, per-row night/scope or continuous03..05; see README','units':'X/Y/correction:mm_API; coefficients:normalized_modal_basis; fractions:dimensionless; coords:native_unverified; time:Unixms/Beijing','purpose':'reproducible research only; no candidate X0'})
    write(pd.DataFrame(catalog),'file_catalog.csv');check['catalogued_files']=len(catalog)
    result={'status':'PASS','checks':check,'not_claimed':['field-state-exact replay','world geometry or physical truth','new-night acceptance','candidate final X0 or deployment'],'catalog_excludes_catalog_and_validation':True}
    (O/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
