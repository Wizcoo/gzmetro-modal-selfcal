from analyze import *

def max_duration(ts,mask):
    longest=0;start=None;last=None
    for t,ok in zip(ts,mask):
        if not ok:start=None;last=None;continue
        if start is None or last is None or t-last>90000:start=t
        last=t;longest=max(longest,(t-start)/60000)
    return longest
def main():
    ef=OUT/'right_x_events.csv';ev=pd.read_csv(ef,dtype={'observing_device_candidates':str});md=pd.read_pickle(C/'md_tagged.pkl');sd=pd.read_pickle(C/'SubDeviceDisData.pkl')
    for i,row in ev.iterrows():
        st=int(pd.Timestamp(row.start_beijing).timestamp()*1000);en=int(pd.Timestamp(row.end_beijing).timestamp()*1000);dev=str(row.observing_device_candidates).split('|')[0]
        g=md[md.markerName.eq(row.marker_name)&md.timestamp.between(st,en)].sort_values('timestamp');s=pd.Series(g.x0.values,index=pd.to_datetime(g.timestamp,unit='ms',utc=True));base=g.loc[g.timestamp<g.timestamp.min()+600000,'x0'].median();sm=s.rolling('5min',min_periods=3).median();off=sm-base
        ev.loc[i,'sustained5min_offset_abs_max_mm']=off.abs().max();ev.loc[i,'longest_run_local_offset_gt1mm_minutes']=max_duration(g.timestamp.values,off.abs().gt(1).values);ev.loc[i,'last10min_minus_first10min_x0_mm']=g.loc[g.timestamp>g.timestamp.max()-600000,'x0'].median()-base
        env=pd.read_pickle(C/f'EnvData_{dev}.pkl');env=env[env.ts.between(st,en)].sort_values('ts')
        for field,unit in [('temp','degC'),('humidity','percent')]:
            ev.loc[i,f'first_candidate_{field}_min_{unit}']=env[field].min();ev.loc[i,f'first_candidate_{field}_max_{unit}']=env[field].max()
        pose=sd[sd.deviceId.eq(dev)&sd.timestamp.between(st,en)]
        for field in ['Pitch','Yaw']:ev.loc[i,f'first_candidate_{field}_pv_native_unit_unverified']=pose[field].max()-pose[field].min()
        d=pd.read_pickle(C/f'Marker_{dev}.pkl');d=d[d.markerName.eq(row.marker_name)&d.timestamp.between(st,en)].sort_values('timestamp')
        ev.loc[i,'first_candidate_invalid_rows']=int(d.RoiCalState.ne(1).sum());ev.loc[i,'first_candidate_RoiCalState_transitions']=int(d.RoiCalState.ne(d.RoiCalState.shift()).iloc[1:].sum())
        valid=d.RoiCalState.eq(1);point=d[valid]
        if len(point):
            pb=point.loc[point.timestamp<point.timestamp.min()+600000,'calX'].median();peak=point.loc[(point.calX-pb).abs().idxmax(),'timestamp'];db=g.loc[(g.x0-base).abs().idxmax(),'timestamp']
            ev.loc[i,'first_candidate_calX_peak_time_beijing']=iso(peak);ev.loc[i,'x0_peak_time_beijing']=iso(db);ev.loc[i,'peak_lag_minutes_x0_minus_calX']=float((db-peak)/60000)
    write_csv(ev,'right_x_events.csv')
    # Fix compact main-table projection without rerunning unchanged metrics.
    sf=pd.read_pickle(C/'marker_metrics.pkl')
    dev=sf.groupby(['device_id','axis','period'],as_index=False).agg(raw_pv_mm=('raw_pv_mm','median'),cal_pv_mm=('cal_pv_mm','median'),raw_step_abs_p99_mm=('raw_step_abs_p99_mm','median'),cal_step_abs_p99_mm=('cal_step_abs_p99_mm','median'),nonzero_correction_fraction=('nonzero_correction_fraction','median'),n_rows=('n_rows','sum'),roi_valid_fraction=('roi_valid_fraction','mean'))
    dev['scope']='device_median_of_marker_metrics';dev['marker_name']='all_markers_median';dev['unit']='mm';dev['start_beijing']=iso(md.timestamp.min());dev['end_beijing']=iso(md.timestamp.max());dev['pv_reduction_fraction']=1-dev.cal_pv_mm/dev.raw_pv_mm
    old=pd.read_csv(OUT/'right_x_summary.csv',nrows=0).columns.tolist();main=pd.concat([dev,sf],ignore_index=True);write_csv(main[old],'right_x_summary.csv')
    # Audit sample availability for all event/parent records, with clear units.
    for filename in ['explicit_device_marker_mapping.csv','environment_quality.csv','upstream_downstream_associations.csv']:
        f=OUT/filename;a=pd.read_csv(f,dtype={'device_id':str});a['analysis_start_beijing']=iso(md.timestamp.min());a['analysis_end_beijing']=iso(md.timestamp.max());a['nominal_phase_rule']='metric_definitions.md';write_csv(a,filename)
    print(ev[['event_id','marker_name','start_beijing','end_beijing','x0_pv_mm','sustained5min_offset_abs_max_mm','longest_run_local_offset_gt1mm_minutes','first_candidate_temp_min_degC','first_candidate_temp_max_degC','first_candidate_Pitch_pv_native_unit_unverified','first_candidate_Yaw_pv_native_unit_unverified','first_candidate_invalid_rows','peak_lag_minutes_x0_minus_calX']].to_string(index=False))
if __name__=='__main__':main()
