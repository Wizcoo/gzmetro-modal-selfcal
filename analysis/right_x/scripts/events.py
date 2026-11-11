from analyze import *

def select_events(md,up):
    membership={n:sorted({dev for dev,d in up.items() if n in set(d.markerName)}) for n in md.markerName.unique()}
    specs=[{'marker':'YD2603','center':'2026-11-05 11:45','start':'2026-11-05 09:45','end':'2026-11-05 13:15','selection':'largest_daytime_offset_and_observation_reset'},
           {'marker':'YD1604','center':'2026-11-05 12:49:41.412','start':'2026-11-05 11:30','end':'2026-11-05 13:30','selection':'largest_initial_value_adjustment'}]
    md=md.copy();md['night']=md.night_date
    for night in ['2026-11-05','2026-11-06']:
        used=set()
        pool=md[md.nominal_phase.eq('full_correction')&md.night.eq(night)&md.markerName.str.startswith('YD')]
        rank=[]
        for name,g in pool.groupby('markerName'):
            g=g.sort_values('timestamp');s=pd.Series(g.x0.values,index=pd.to_datetime(g.timestamp,unit='ms',utc=True))
            sm=s.rolling('5min',min_periods=3).median();r=sm.rolling('60min',min_periods=20).max()-sm.rolling('60min',min_periods=20).min()
            if r.notna().any():
                ts=r.idxmax().value//1000000;rank.append((float(r.max()),name,int(ts-30*60000)))
        rank.sort(reverse=True)
        for dev in sorted(up):
            candidate=next(((score,name,ts) for score,name,ts in rank if dev in membership[name] and name not in used),None)
            if candidate:
                score,name,ts=candidate;used.add(name)
                specs.append({'marker':name,'center_ms':ts,'start_ms':ts-45*60000,'end_ms':ts+45*60000,'selection':f'largest_60min_sustained_x0_range_for_observing_device_{dev}_night_{night}','selection_score_mm':score})
    for date in ['2026-11-06','2026-11-07']:
        pool=md[md.date_beijing.eq(date)&md.nominal_phase.eq('daytime')&md.markerName.str.startswith('YD')]
        best=None
        for name,g in pool.groupby('markerName'):
            g=g.sort_values('timestamp');s=pd.Series(g.x0.values,index=pd.to_datetime(g.timestamp,unit='ms',utc=True));sm=s.rolling('5min',min_periods=3).median();r=sm.rolling('60min',min_periods=20).max()-sm.rolling('60min',min_periods=20).min()
            if r.notna().any() and (best is None or r.max()>best[0]):best=(float(r.max()),name,int(r.idxmax().value//1000000-30*60000))
        if best:
            score,name,ts=best;specs.append({'marker':name,'center_ms':ts,'start_ms':ts-45*60000,'end_ms':ts+45*60000,'selection':f'largest_daytime_60min_sustained_x0_range_{date}','selection_score_mm':score})
    return specs,membership

def main_events():
    md=pd.read_pickle(C/'md_tagged.pkl');sd=tag(pd.read_pickle(C/'SubDeviceDisData.pkl'))
    up={p.stem.split('_')[1]:tag(pd.read_pickle(p)) for p in C.glob('Marker_780*.pkl')}
    specs,membership=select_events(md,up);rows=[];files=[];common=pd.read_pickle(C/'common.pkl');eventsdir=OUT/'right_x_windows'
    for idx,spec in enumerate(specs,1):
        event=f'RX{idx:02}';name=spec['marker'];parents=membership[name]
        if 'center_ms' not in spec:
            for k in ['start','end','center']:spec[k+'_ms']=int(pd.Timestamp(spec[k],tz=TZ).timestamp()*1000)
        st,en=spec['start_ms'],spec['end_ms'];target=md[md.markerName.eq(name)&md.timestamp.between(st,en)].sort_values('timestamp')
        section=int(name[2:4])
        nearby=[n for n in md.markerName.unique() if n.startswith('YD') and len(n)>=6 and abs(int(n[2:4])-section)<=1]
        nearby=sorted(set(nearby+[name]))
        down=md[md.markerName.isin(nearby)&md.timestamp.between(st,en)].copy();down['event_id']=event;down['time_beijing']=down.timestamp.map(iso)
        down['x0_identity_residual_mm']=down.x0-(down.filteredX0-down.initX);down['actual_cloud_value']='not_available'
        files.extend([{'event_id':event,'stage':'downstream','path':p,'unit':'mm_for_coordinate_columns','mapping':'stored_fields_no_solver_stage_assumption'} for p in split_csv(down.drop(columns=['phase_key']),f'right_x_windows/{event}/downstream.csv')])
        fullup=[];allcorr=[];pointstats=[]
        for dev in parents:
            d=up[dev];g=d[d.timestamp.between(st,en)].copy();g['event_id']=event;g['time_beijing']=g.timestamp.map(iso);g['observing_device_id']=dev
            g['rawX_mm']=g.x;g['rawY_mm']=g.y;g['calX_mm']=g.calX;g['calY_mm']=g.calY;g['correctionX_mm']=g.x-g.calX;g['correctionY_mm']=g.y-g.calY
            g['valid_observation']=g.RoiCalState.eq(1)&~g.ambiguous_business_key;g['actual_gate']='not_recorded';g['actual_modes_ready']='not_recorded'
            # Every marker of every candidate parent is retained, so local
            # differences and peer corrections can be inspected without sampling.
            columns=['event_id','timestamp','time_beijing','observing_device_id','markerName','markerIndex','markerPos','RoiCalState','valid_observation','rawX_mm','calX_mm','correctionX_mm','rawY_mm','calY_mm','correctionY_mm','scale','centerX','centerY','source_db','_source_rowid','nominal_phase','night_date','actual_gate','actual_modes_ready']
            files.extend([{'event_id':event,'stage':'upstream_all_device_markers','path':p,'unit':'mm_interface_contract','mapping':'observed_marker_table_device'} for p in split_csv(g[[k for k in columns if k in g]],f'right_x_windows/{event}/upstream_{dev}.csv')])
            v=g[g.valid_observation];t=v[v.markerName.eq(name)].sort_values('timestamp');other=v[v.markerName.ne(name)&v.markerName.str.startswith('YD')]
            cm=other.pivot(index='timestamp',columns='markerName',values='x');cm=(cm-cm.iloc[:10].median()).median(axis=1)
            cs=common[common.device_id.eq(dev)&common.axis.eq('X')&common.timestamp.between(st,en)]
            pointstats.append({'event_id':event,'device_id':dev,'marker_name':name,'raw_x_pv_mm':t.x.max()-t.x.min(),'cal_x_pv_mm':t.calX.max()-t.calX.min(),'raw_y_pv_mm':t.y.max()-t.y.min(),'cal_y_pv_mm':t.calY.max()-t.calY.min(),'max_abs_correction_x_mm':(t.x-t.calX).abs().max(),'max_abs_correction_y_mm':(t.y-t.calY).abs().max(),'point_nonzero_correction_fraction':(t.x-t.calX).abs().gt(1e-6).mean(),'valid_fraction':g[g.markerName.eq(name)].RoiCalState.eq(1).mean(),'raw_x_vs_peer_common_r':corr(t.x,cm.reindex(t.timestamp)),'device_frames_with_observed_correction_fraction':cs.nonzero_correction_marker_fraction.gt(0).mean(),'matched_target_rows':len(t),'actual_gate':'not_recorded','actual_modes_ready':'not_recorded'})
            e=tag(pd.read_pickle(C/f'EnvData_{dev}.pkl'),'ts');e=e[e.timestamp.between(st,en)].copy();e['event_id']=event;e['time_beijing']=e.timestamp.map(iso);e['field_units']='temp_degC_humidity_percent_other_units_unverified'
            files.extend([{'event_id':event,'stage':'environment','path':p,'unit':'mixed_see_field_units','mapping':'device_table_timestamp'} for p in split_csv(e,f'right_x_windows/{event}/environment_{dev}.csv')])
            sp=pd.read_pickle(C/f'SinglePoint_{dev}.pkl');sp=sp[sp.ts.between(st,en)&sp.pointName.eq(name)].copy()
            if len(sp):
                sp['event_id']=event;sp['time_beijing']=sp.ts.map(iso);sp['relation']='pointName_exact_name_candidate_only';sp['field_units']='unverified'
                files.extend([{'event_id':event,'stage':'singlepoint_name_candidate','path':p,'unit':'unverified','mapping':'name_match_not_confirmed_business_key'} for p in split_csv(sp,f'right_x_windows/{event}/singlepoint_{dev}.csv')])
        sub=sd[sd.timestamp.between(st,en)].copy();sub['event_id']=event;sub['time_beijing']=sub.timestamp.map(iso);sub['pose_units']='unverified'
        files.extend([{'event_id':event,'stage':'device_displacement_pose_all_six','path':p,'unit':'coordinate_mm_pose_unverified','mapping':'deviceId_field'} for p in split_csv(sub,f'right_x_windows/{event}/device_pose.csv')])
        overview=common[common.timestamp.between(st,en)].copy();overview['event_id']=event
        files.extend([{'event_id':event,'stage':'cross_device_common_all_real_frames','path':p,'unit':'mm','mapping':'device_table_identity'} for p in split_csv(overview,f'right_x_windows/{event}/cross_device_common.csv')])
        write_csv(pd.DataFrame(pointstats),f'right_x_windows/{event}/target_parent_metrics.csv')
        ts=target.timestamp.values;dt=target.timestamp.diff().between(30000,90000);step=target.x0.diff().where(dt);ix=step.abs().idxmax() if step.notna().any() else target.index[0]
        pos=target.index.get_loc(ix);prev=target.iloc[max(0,pos-1)];cur=target.loc[ix]
        ic=target.initX.diff();maxi=ic.abs().max();pstat=pointstats[0]
        classification='association_only_residual_or_unknown_chain'
        if maxi>.01:classification='initial_value_change_contributes_to_x0'
        elif all(x['point_nonzero_correction_fraction']==0 for x in pointstats) and any(x['device_frames_with_observed_correction_fraction']>.5 for x in pointstats):classification='target_not_corrected_while_peers_corrected'
        elif any(x['cal_x_pv_mm']>1.3*x['raw_x_pv_mm']+.1 for x in pointstats):classification='target_variation_increased_after_recorded_correction'
        elif all(x['point_nonzero_correction_fraction']==0 for x in pointstats):classification='no_recorded_target_correction_in_window'
        row={'event_id':event,'marker_name':name,'observing_device_candidates':'|'.join(parents),'mapping_status':'same_name_timestamp_candidates_not_solver_topology','start_beijing':iso(st),'end_beijing':iso(en),'trigger_time_beijing':iso(spec['center_ms']),'unit':'mm','selection_rule':spec['selection'],'x0_pv_mm':target.x0.max()-target.x0.min(),'x0_robust_p99_p01_mm':target.x0.quantile(.99)-target.x0.quantile(.01),'y0_pv_mm':target.y0.max()-target.y0.min(),'max_adjacent_x0_step_mm':step.abs().max(),'max_step_time_beijing':iso(cur.timestamp),'delta_x0_at_max_step_mm':cur.x0-prev.x0,'delta_filteredX0_at_max_step_mm':cur.filteredX0-prev.filteredX0,'delta_initX_at_max_step_mm':cur.initX-prev.initX,'max_abs_initX_step_mm':maxi,'target_valid_upstream_rows':sum(x['matched_target_rows'] for x in pointstats),'nominal_phases':'|'.join(sorted(target.nominal_phase.unique())),'actual_gate':'not_recorded','actual_modes_ready':'not_recorded','evidence_class':classification,'confirmed':'Stored raw/cal, filtered/init/x0 relationships only; see target_parent_metrics and continuous CSV.','needs_verification':'Physical truth; online state use/learn/gate; exact solver topology/geometry; publication and filter implementation.'}
        for k in ['raw_x_pv_mm','cal_x_pv_mm','raw_y_pv_mm','cal_y_pv_mm','point_nonzero_correction_fraction','valid_fraction','raw_x_vs_peer_common_r','device_frames_with_observed_correction_fraction']:row['first_candidate_'+k]=pstat[k]
        rows.append(row);print(event,name,parents,round(row['x0_pv_mm'],3),classification,flush=True)
    write_csv(pd.DataFrame(rows),'right_x_events.csv');write_csv(pd.DataFrame(files),'event_files.csv')
    # Full-night continuity evidence for the event target set, all valid/invalid
    # flags retained. No random sampling, no replacement by an aggregate trace.
    targets=sorted({s['marker'] for s in specs})
    for night in ['2026-11-05','2026-11-06']:
        start=int(pd.Timestamp(night+' 20:00',tz=TZ).timestamp()*1000);end=start+13*3600000
        g=md[md.markerName.isin(targets)&md.timestamp.between(start,end)].copy();g['time_beijing']=g.timestamp.map(iso)
        split_csv(g,f'right_x_windows/continuous_nights/downstream_{night}.csv')
        for dev,d in up.items():
            g=d[d.markerName.isin(targets)&d.timestamp.between(start,end)].copy();g['time_beijing']=g.timestamp.map(iso);g['observing_device_id']=dev
            split_csv(g,f'right_x_windows/continuous_nights/upstream_{dev}_{night}.csv')
    # Initial-value changes are fully enumerated, not only the worst marker.
    changes=[]
    for name,g in md.groupby('markerName'):
        g=g.sort_values('timestamp');dx=g.initX.diff();dy=g.initY.diff();mask=dx.abs().gt(.00011)|dy.abs().gt(.00011)
        for i in g.index[mask]:changes.append({'marker_name':name,'timestamp':int(g.at[i,'timestamp']),'time_beijing':iso(g.at[i,'timestamp']),'delta_initX_mm':dx.loc[i],'delta_initY_mm':dy.loc[i]})
    write_csv(pd.DataFrame(changes),'initial_value_changes.csv')
    print('EVENTS COMPLETE',len(rows),'evidence files',len(files),flush=True)
if __name__=='__main__':main_events()
