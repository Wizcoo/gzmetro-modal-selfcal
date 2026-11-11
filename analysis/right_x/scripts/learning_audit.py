from analyze import *
def main():
    rows=[];mappings=[];md=pd.read_pickle(C/'MarkerData.pkl');sd=pd.read_pickle(C/'SubDeviceDisData.pkl')
    bound=md[md.deviceId.ne('')].merge(sd,on=['timestamp','deviceId'],suffixes=('_markerdata','_device'),how='left')
    for (name,dev),g in bound.groupby(['markerName','deviceId']):
        r={'marker_name':name,'device_id':dev,'bound_rows':len(g),'mapping':'explicit_MarkerData_deviceId','sd_matched_rows':int(g.x0_device.notna().sum())}
        for k in ['x','y','x0','y0']:r[k+'_max_abs_difference']= (g[k+'_markerdata']-g[k+'_device']).abs().max()
        mappings.append(r)
    write_csv(pd.DataFrame(mappings),'explicit_device_marker_mapping.csv')
    for p in C.glob('Marker_780*.pkl'):
        dev=p.stem.split('_')[1];d=tag(pd.read_pickle(p))
        for night in ['2026-11-05','2026-11-06']:
            st=int(pd.Timestamp(night+' 22:00',tz=TZ).timestamp()*1000);refend=st+3600000;lend=st+4*3600000;coreend=st+9*3600000
            allframes=d.loc[d.timestamp.ge(st)&d.timestamp.lt(lend),'timestamp'].nunique()
            for name,g in d.groupby('markerName'):
                ref=g[g.timestamp.ge(st)&g.timestamp.lt(refend)];learn=g[g.timestamp.ge(st)&g.timestamp.lt(lend)];core=g[g.timestamp.ge(refend+1200000)&g.timestamp.lt(coreend)]
                for axis in ['X','Y']:
                    raw=axis.lower();cal='cal'+axis
                    valid=learn.RoiCalState.eq(1)&np.isfinite(learn[raw]);rv=ref.RoiCalState.eq(1)&np.isfinite(ref[raw]);cv=core.RoiCalState.eq(1)&np.isfinite(core[raw])&np.isfinite(core[cal])
                    rows.append({'device_id':dev,'marker_name':name,'axis':axis,'night_date':night,'window_start_beijing':iso(st),'window_end_exclusive_beijing':iso(lend),'unit':'mm','device_observed_frames':allframes,'expected_nominal_frames':240,'marker_ref_valid_frames':int(rv.sum()),'marker_learn_valid_frames':int(valid.sum()),'observed_valid_fraction':float(valid.sum()/allframes) if allframes else np.nan,'would_meet_default_min_ref_10':bool(rv.sum()>=10),'would_meet_default_valid_ratio_0_8':bool(valid.sum()>=.8*allframes) if allframes else False,'raw_ref_mean_mm':ref.loc[rv,raw].mean(),'raw_learn_std_mm':learn.loc[valid,raw].std(),'core_valid_rows':int(cv.sum()),'core_nonzero_correction_fraction':(core.loc[cv,raw]-core.loc[cv,cal]).abs().gt(1e-6).mean(),'actual_use_flag':'not_recorded','actual_learn_flag':'not_recorded','qualification_inference':'conditional_on_callers_invalid_to_NaN_and_default_config; historical_3_nights_unavailable'})
    write_csv(pd.DataFrame(rows),'learning_window_audit.csv')
    print(pd.DataFrame(mappings).to_string(index=False))
    print(pd.DataFrame(rows).query("marker_name in ['YD3104','YD2603']")[['device_id','marker_name','axis','night_date','marker_ref_valid_frames','observed_valid_fraction','raw_learn_std_mm','core_nonzero_correction_fraction']].to_string(index=False))
if __name__=='__main__':main()
