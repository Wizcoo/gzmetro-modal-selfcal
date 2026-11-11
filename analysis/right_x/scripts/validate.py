from analyze import *
import re,shutil
def main():
    report={'status':'PASS','checks':{},'limitations':['No solver/geometry/online config, state or cloud-publish implementation.','Statistical attenuation is not physical accuracy.']}
    # Independent recalculation from read-only input caches for every compact
    # marker summary row. This does not trust the primary metric implementation.
    main=pd.read_csv(OUT/'right_x_summary.csv',dtype={'device_id':str});checked=0;maxerr=0
    for p in C.glob('Marker_780*.pkl'):
        dev=p.stem.split('_')[1];d=tag(pd.read_pickle(p));v=d[d.RoiCalState.eq(1)&~d.ambiguous_business_key]
        for period in ['all_window','nominal_daytime','nominal_full_correction']:
            g=v if period=='all_window' else v[v.nominal_phase.eq('daytime' if period=='nominal_daytime' else 'full_correction')]
            for axis in ['X','Y']:
                raw=axis.lower();cal='cal'+axis;g=g[np.isfinite(g[raw])&np.isfinite(g[cal])]
                expected=g.groupby('markerName')[[raw,cal]].agg(['min','max'])
                rows=main[main.scope.eq('marker')&main.device_id.eq(dev)&main.axis.eq(axis)&main.period.eq(period)]
                for _,r in rows.iterrows():
                    for label,col in [('raw',raw),('cal',cal)]:
                        e=expected.loc[r.marker_name,(col,'max')]-expected.loc[r.marker_name,(col,'min')]
                        err=abs(e-r[label+'_pv_mm']);maxerr=max(maxerr,err)
                        if err>1e-6:raise ValueError(f'PV mismatch {dev} {r.marker_name} {period}')
                    z=g[g.markerName.eq(r.marker_name)].sort_values('timestamp');mask=z.timestamp.diff().between(30000,90000)
                    for label,col in [('raw',raw),('cal',cal)]:
                        e=z[col].diff().where(mask).abs().quantile(.99);given=r[label+'_step_abs_p99_mm']
                        if pd.notna(e) and abs(e-given)>1e-6:raise ValueError('Step P99 mismatch')
                    checked+=1
    report['checks']['all_marker_summary_PV_and_step99']={'rows':checked,'max_pv_difference_mm':maxerr,'tolerance_mm':1e-6}
    # All event upstream rows: source row IDs and original millisecond timestamps
    # must match exactly, with no missing or invented observations.
    events=pd.read_csv(OUT/'right_x_events.csv',dtype={'observing_device_candidates':str});index=pd.read_csv(OUT/'event_files.csv');up_checked=down_checked=0
    md=pd.read_pickle(C/'MarkerData.pkl')
    for _,e in events.iterrows():
        st=int(pd.Timestamp(e.start_beijing).timestamp()*1000);en=int(pd.Timestamp(e.end_beijing).timestamp()*1000)
        items=index[index.event_id.eq(e.event_id)]
        for dev in str(e.observing_device_candidates).split('|'):
            files=items[items.stage.eq('upstream_all_device_markers')&items.path.str.contains(dev)].path
            actual=pd.concat([pd.read_csv(OUT/f) for f in files],ignore_index=True)
            src=pd.read_pickle(C/f'Marker_{dev}.pkl');src=src[src.timestamp.between(st,en)]
            key=['timestamp','markerName','_source_rowid']
            a=actual[key].sort_values(key).reset_index(drop=True);b=src[key].sort_values(key).reset_index(drop=True)
            if not a.equals(b):
                # pandas string storage dtypes can differ while values agree.
                if a.astype(str).to_numpy().tolist()!=b.astype(str).to_numpy().tolist():raise ValueError(f'Event row set differs: {e.event_id} {dev}')
            for _,z in actual.iterrows():
                if int(pd.Timestamp(z.time_beijing).timestamp()*1000)!=int(z.timestamp):raise ValueError('Millisecond timestamp lost')
            up_checked+=len(actual)
        files=items[items.stage.eq('downstream')].path;actual=pd.concat([pd.read_csv(OUT/f) for f in files],ignore_index=True)
        src=md[md.timestamp.between(st,en)&md.markerName.isin(actual.markerName.unique())]
        key=['timestamp','markerName','_source_rowid'];a=actual[key].sort_values(key).astype(str).to_numpy().tolist();b=src[key].sort_values(key).astype(str).to_numpy().tolist()
        if a!=b:raise ValueError(f'Downstream event set differs {e.event_id}')
        down_checked+=len(actual)
    report['checks']['all_event_source_rowsets']={'events':len(events),'upstream_rows_checked':up_checked,'downstream_rows_checked':down_checked,'timestamp_resolution':'original milliseconds'}
    # Enforce size and safe format, and give each CSV explicit unit/window/rule
    # metadata without nonstandard CSV preambles.
    files=[p for p in OUT.rglob('*') if not any(x in p.parts for x in ['__pycache__','.cache'])];catalog=[]
    for p in files:
        if not p.is_file() or p.name in ['file_catalog.csv','validation.json']:continue
        if p.suffix not in ['.csv','.json','.md','.py'] and p.name not in ['.gitignore','.gitattributes']:raise ValueError(f'Unexpected output type {p}')
        if p.stat().st_size>=2000000:raise ValueError(f'File >= 2 MB: {p}')
        text=p.read_text(encoding='utf-8').replace('\r\n','\n');p.write_bytes(text.encode('utf-8'))
        if re.search(r'github_pat_[A-Za-z0-9_]{20}|gh[pousr]_[A-Za-z0-9]{20}|-----BEGIN [A-Z ]*PRIVATE KEY',text):raise ValueError(f'Unexpected credential pattern in output: {p.name}')
        if p.suffix=='.csv':
            d=pd.read_csv(p);n=len(d)
            if 'ts' in d and 'time_beijing' in d:
                expected=np.array([int(pd.Timestamp(x).timestamp()*1000) for x in d.time_beijing])
                if not np.array_equal(d.ts.to_numpy(),expected):raise ValueError(f'Float ts resolution lost: {p}')
            unit='coordinate_mm; correlation_dimensionless; timestamps_ms; environment_and_pose_native_units_explicit_or_unverified'
        else:n=0;unit='not_applicable'
        catalog.append({'path':str(p.relative_to(OUT)).replace('\\','/'),'bytes':p.stat().st_size,'rows_if_csv':n,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'analysis_start_beijing':'2026-11-05T00:00:00+08:00','analysis_end_inclusive_beijing':'2026-11-07T15:00:00+08:00','timezone':'Asia/Shanghai','units':unit,'phase_and_metrics':'metric_definitions.md; actual_gate/modes_ready_not_recorded','sampling':'all_rows_for_selected_stage_and_window_no_random_sampling'})
    write_csv(pd.DataFrame(catalog),'file_catalog.csv')
    report['checks']['file_contract']={'files':len(catalog)+2,'maximum_file_bytes':max(x['bytes'] for x in catalog),'all_files_below_2MB':True,'csv_unit_window_metadata':'file_catalog.csv + metric_definitions.md','formats':['UTF8 CSV','UTF8 JSON','UTF8 Markdown','self-authored Python scripts']}
    (OUT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
