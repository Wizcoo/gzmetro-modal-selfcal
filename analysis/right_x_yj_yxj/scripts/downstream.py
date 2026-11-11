from relations import *
def main():
    d=pd.read_pickle(W/'refs.pkl');md=pd.read_pickle(C/'MarkerData.pkl');sd=pd.read_pickle(C/'SubDeviceDisData.pkl');rows=[]
    for ch,g in d[d.markerName.str.startswith('YXJ')].groupby('channel'):
        name=g.markerName.iloc[0];node=md[md.markerName.eq(name)].copy();bound=node.deviceId.dropna().loc[lambda s:s.ne('')].unique();bounddev=bound[0] if len(bound)==1 else ''
        if bounddev:
            device=sd[sd.deviceId.eq(bounddev)].rename(columns={c:'bound_device_'+c for c in sd if c not in ['timestamp','deviceId']});node=node.merge(device,on=['timestamp','deviceId'],how='left',validate='one_to_one')
        for seg,st,en in SEGMENTS:
            a=g[g.timestamp.ge(st)&g.timestamp.lt(en)&g.valid];n=node[node.timestamp.ge(st)&node.timestamp.lt(en)]
            for upfield in ['x','calX']:
                for downfield in ['x','x0','filteredX0','initX','bound_device_x','bound_device_x0']:
                    if downfield not in n:continue
                    x=pd.Series(a[upfield].values,index=a.timestamp);y=pd.Series(n[downfield].values,index=n.timestamp);s=pair_stats(smooth(x),smooth(y));s.update({'channel':ch,'yxj_name':name,'explicit_bound_device_id':bounddev,'segment':seg,'upstream_field':upfield,'downstream_field':downfield,'start_beijing':iso(st),'end_exclusive_beijing':iso(en),'downstream_distinct_values':n[downfield].nunique(),'status':'constant_no_information' if n[downfield].nunique()<2 else 'observed_association_only','coefficient_unit':'mm_per_mm_not_solver_Jacobian'});rows.append(s)
        # Actual observed fields only: no candidate is substituted into x0.
        j=g.merge(node[['timestamp','x','x0','filteredX0','initX','deviceId']],on='timestamp',suffixes=('_up','_down'),how='left');j['time_beijing']=j.timestamp.map(iso);j['cloud_publication']='not_available';j['serial_recomputed_candidate_x0']='not_available'
        keep=['timestamp','time_beijing','observing_device_id','markerName','RoiCalState','x_up','calX','x_down','filteredX0','initX','x0','deviceId','cloud_publication','serial_recomputed_candidate_x0'];write(j[keep],f'downstream_traces/{ch.replace(":","_")}.csv')
    write(pd.DataFrame(rows),'observed_downstream_associations.csv')
    # Use fit-night raw same-name response once for all output methods; do not
    # recalibrate each method on the holdout just to improve agreement.
    tr=pd.read_pickle(W/'candidate_traces.pkl');out=[]
    for fold,fitnight,testnight in [('primary_05_to_06','2026-11-05','2026-11-06'),('reverse_06_to_05','2026-11-06','2026-11-05')]:
        fitstart=epoch(fitnight+' 23:20');fitend=fitstart+460*60000
        a=d[d.channel.eq('780639346578:YXJ6')&d.timestamp.ge(fitstart)&d.timestamp.lt(fitend)&d.valid];b=d[d.channel.eq('780639376393:YXJ6')&d.timestamp.ge(fitstart)&d.timestamp.lt(fitend)&d.valid]
        coef=pair_stats(smooth(pd.Series(a.x.values,index=a.timestamp)),smooth(pd.Series(b.x.values,index=b.timestamp)))['slope_b_per_a']
        teststart=epoch(testnight+' 23:20');testend=teststart+460*60000
        z=tr[tr.fold.eq(fold)&tr.markerName.eq('YXJ6')&tr.valid&tr.timestamp.ge(teststart)&tr.timestamp.lt(testend)]
        for field in ['x','calX','A_X_mm','B_X_mm']:
            a=z[z.observing_device_id.eq('780639346578')];b=z[z.observing_device_id.eq('780639376393')];s1=smooth(pd.Series(a[field].values,index=a.timestamp));s2=smooth(pd.Series(b[field].values,index=b.timestamp));bv=align(s2,s1.index);m=np.isfinite(bv)&np.isfinite(s1);dis=bv[m]-coef*s1.values[m];dis-=np.median(dis)
            stats=pair_stats(s1,s2);out.append({'fold':fold,'fit_night':fitnight,'test_night':testnight,'field':field,'fit_raw_coefficient_frozen':coef,'heldout_pair_r':stats.get('r',np.nan),'heldout_pair_slope':stats.get('slope_b_per_a',np.nan),'response_sign_stable':np.sign(coef)==np.sign(stats.get('slope_b_per_a',np.nan)),'centered_disagreement_abs_p99_mm':np.quantile(abs(dis),.99) if len(dis) else np.nan,'caution':'sensor-response agreement proxy, not geometric closure or displacement accuracy'})
    write(pd.DataFrame(out),'yxj6_cross_observer_consistency.csv')
    print('Downstream observational links and consistency metrics ready')
if __name__=='__main__':main()
