from common import *
import argparse

def load(p):
    with p.open('rb') as f:
        def u():return struct.unpack('<I',f.read(4))[0]
        def s():return f.read(u()).decode()
        n=u();names=[s() for _ in range(n)];nm=u();modes=[s() for _ in range(nm)];nd=u();diags=[s() for _ in range(nd)];nf=u();offset=f.tell()
    inner=np.dtype([('x','<f8',(n,)),('loo','<f8',(n,)),('diag','<f8',(nd,))]);dt=np.dtype([('ts','<i8'),('rawx','<f8',(n,)),('rawy','<f8',(n,)),('y','<f8',(n,)),('methods',inner,(nm,))])
    assert p.stat().st_size==offset+nf*dt.itemsize,(p,offset,nf,dt)
    data=np.memmap(p,dtype=dt,mode='r',offset=offset,shape=(nf,));return names,modes,diags,data

def evaluate(stage):
    rows=[];birth=[];diagrows=[];runtime=[];agreement=[];injections=[];sourcecheck=[]
    for dev in DEVS:
        names,modes,fields,d=load(W/stage/f'normal_{dev}.bin');di={n:i for i,n in enumerate(fields)};t=d['ts'];keys=[i for i,n in enumerate(names) if n.startswith(('YJ','YXJ'))];md=pd.read_pickle(C/f'Marker_{dev}.pkl')
        b=pd.read_csv(W/stage/f'birth_{dev}.csv');b['device_id']=dev;b['marker_name']=[names[i] for i in b.point_index];birth.append(b)
        for night in ['2026-11-05','2026-11-06']:
            st=epoch(night+' 23:20');en=st+460*60000;core=(t>=st)&(t<en);dd=d['methods']['diag'];baseactive=(dd[:,0,di['n_corrected']]>0)&(dd[:,0,di['gate']]>0)
            for mi,method in enumerate(modes):
                valid=core&baseactive;v=dd[valid,mi];cpu=v[:,di['process_us']];allcpu=dd[(t>=epoch(night+' 22:00'))&(t<en+20*60000),mi,di['process_us']];runtime.append({'device_id':dev,'method':method,'night':night,'core_active_frames':int(valid.sum()),'process_us_median':np.median(cpu),'process_us_P99':np.quantile(cpu,.99),'process_us_max':np.max(cpu),'whole_night_process_us_P99':np.quantile(allcpu,.99),'whole_night_process_us_max':allcpu.max(),'Y_bitwise_mismatch_count':v[:,di['Y_mismatch_count']].sum(),'enhancement_active_fraction':v[:,di['enhancement_active']].mean(),'fallback_fraction':(v[:,di['fallback_code']]>0).mean(),'effective_learning_count_min':np.min(v[:,di['effective_learning_count']]),'learning_count_min':np.min(v[:,di['n_frame_learn_valid']]),'degraded_frames':int((core&(dd[:,mi,di['modes_ready']]>0)&(dd[:,mi,di['gate']]>0)&(dd[:,mi,di['n_corrected']]==0)).sum()),'mean_delta_v_norm':np.mean(v[:,di['delta_v_norm']]),'ref_qualified_count_median':np.median(v[:,di['qualified_current_refs']]),'ref_rejected_count_max':np.max(v[:,di['rejected_refs']])})
            for i in keys:
                field=md[md.markerName.eq(names[i])].set_index('timestamp').calX.reindex(t).to_numpy();series=[('raw_X',d['rawx'][:,i]),('V51_field_observed',field)]+[(m,d['methods']['x'][:,mi,i]) for mi,m in enumerate(modes) if m!='identity']
                if names[i].startswith('YJ'):
                    for mi,m in enumerate(modes):
                        if m in ['A','EA']:
                            lv=d['methods']['loo'][:,mi,i].copy();v=np.full(len(t),np.nan)
                            for nid,bg in b[b.method.eq(m)&b.point_index.eq(i)].groupby('night_id'):
                                masknight=np.asarray((pd.to_datetime(t,unit='ms',utc=True).tz_convert('Asia/Shanghai')-pd.Timedelta(hours=12)).date)==pd.Timestamp(nid,unit='D').date()
                                rawz=d['rawx'][:,i]-bg.baseline_mm.iloc[0];gate=dd[:,mi,di['gate']]
                                v[masknight]=d['rawx'][masknight,i]-gate[masknight]*(rawz[masknight]-lv[masknight])
                                # A reference never admitted to the constraint is
                                # already independent at the current frame.
                                if bg.historical_explained_energy.iloc[0]<.8:v[masknight]=d['methods']['x'][masknight,mi,i]
                            series.append((m+'_LOPO',v))
                            series.append(('V51_on_'+m+'_LOPO_rows',np.where(np.isfinite(v),d['methods']['x'][:,0,i],np.nan)))
                for scope,mask in [('nominal_core_including_cold_wait',core),('same_original_active_frames',core&baseactive)]:
                    for method,v in series:
                        good=mask&np.isfinite(d['rawx'][:,i])&np.isfinite(v)
                        if good.sum()<20:continue
                        r=metrics(t[good],v[good]);r.update(device_id=dev,marker_name=names[i],channel=dev+':'+names[i],kind='YXJ' if names[i].startswith('YXJ') else 'YJ',method=method,night=night,scope=scope,start_beijing=iso(st),end_exclusive_beijing=iso(en),interpretation='variation_not_physical_error; field_not_same_condition_AB');rows.append(r)
            # 30-minute contiguous summaries retain model coefficients and
            # qualification without flooding the PR with duplicate series.
            for bucket in range(st,en,1800000):
                mask=(t>=bucket)&(t<min(en,bucket+1800000))
                for mi,method in enumerate(modes):
                    z=dd[mask,mi];r={'device_id':dev,'method':method,'night':night,'start_beijing':iso(bucket),'end_exclusive_beijing':iso(min(en,bucket+1800000)),'frames':int(mask.sum())}
                    for f in fields:
                        a=z[:,di[f]];finite=a[np.isfinite(a)];r[f+'_mean']=np.mean(finite) if len(finite) else np.nan
                    diagrows.append(r)
        for path in sorted((W/stage).glob(f'*_{dev}.bin')):
            if path.name.startswith('normal_'):continue
            kn,mm,ff,z=load(path);assert mm==modes and ff==fields;scenario,onset,_=path.stem.rsplit('_',2);onset=int(onset);j=pd.Index(t).get_indexer(z['ts']);assert (j>=0).all();settled=(z['ts']>=onset+210*60000)&(z['ts']<onset+240*60000);truth=z['rawx']-d['rawx'][j][:,[names.index(n) for n in kn]]
            for mi,method in enumerate(modes):
                if method=='identity':continue
                q=z['methods']['diag'][:,mi];overall=q[:,di['max_nontarget_all_delta_mm']].max();keymax=q[:,di['max_nontarget_key_delta_mm']].max() if len(kn) else np.nan
                injections.append({'device_id':dev,'night':iso(onset)[:10],'scenario':scenario,'method':method,'channel':'ALL_non_target_points','raw_target_increment_mm':0,'retained_fraction':np.nan,'median_output_increment_mm':np.nan,'max_abs_output_delta_mm':overall,'max_key_nontarget_delta_mm':keymax,'Y_mismatch_count':q[:,di['Y_mismatch_count']].sum(),'interpretation':'observation_coordinate_injection_not_world_displacement'})
                for ki,name in enumerate(kn):
                    idx=names.index(name);dx=z['methods']['x'][:,mi,ki]-d['methods']['x'][j,mi,idx];dy=z['y'][:,ki]-d['y'][j,idx];tv=truth[:,ki];axis='X'
                    if scenario=='Y_settlement':tv=z['rawy'][:,ki]-d['rawy'][j,idx];dx=dy;axis='Y'
                    target=np.nanmedian(abs(tv[settled])) if np.isfinite(tv[settled]).any() else np.nan;actual=np.nanmedian(tv[settled]) if np.isfinite(tv[settled]).any() else np.nan;inc=np.nanmedian(dx[settled]) if np.isfinite(dx[settled]).any() else np.nan
                    # A pulse has no settled increment; report peak separately.
                    nz=np.flatnonzero(np.isfinite(tv)&(abs(tv)>1e-9));delay=np.nan
                    if len(nz) and ('step' in scenario):
                        signal=dx/tv;ok=np.isfinite(signal)&(signal>=.95)&(signal<=1.05);first=nz[0]
                        for jj in range(first,len(ok)-4):
                            if ok[jj:jj+5].all():delay=jj-first;break
                    injections.append({'device_id':dev,'night':iso(onset)[:10],'scenario':scenario,'method':method,'channel':dev+':'+name,'axis':axis,'raw_target_increment_mm':actual,'retained_fraction':inc/actual if abs(actual)>.000001 else np.nan,'median_output_increment_mm':inc,'max_abs_output_delta_mm':np.nanmax(abs(dx)) if np.isfinite(dx).any() else np.nan,'max_key_nontarget_delta_mm':keymax,'step_95pct_retention_delay_frames':delay,'target_peak_injection_mm':np.nanmax(abs(tv)) if np.isfinite(tv).any() else np.nan,'Y_mismatch_count':q[:,di['Y_mismatch_count']].sum(),'measurement_start_beijing':iso(onset+210*60000),'measurement_end_exclusive_beijing':iso(onset+240*60000),'interpretation':'observation_coordinate_injection_not_world_displacement'})
    result=pd.DataFrame(rows);write(result,'ablation_results.csv');write(pd.concat(birth,ignore_index=True),'model_birth_diagnostics.csv');write(pd.DataFrame(runtime),'runtime_and_failure.csv')
    # The requested diagnostics stay compact; full replay coefficients and
    # point vectors can be regenerated in .work binary caches.
    dg=pd.DataFrame(diagrows);selected=['device_id','method','night','start_beijing','end_exclusive_beijing','frames']+[f+'_mean' for f in ['v0_1','v0_2','v0_3','v_used_1','v_used_2','v_used_3','n_frame_learn_valid','n_history','gate','modes_ready','enhancement_active','fallback_code','effective_learning_count','downweighted_below_half','max_leverage','qualified_current_refs','rejected_refs','delta_v_norm','learning_RMS_before_mm','learning_RMS_after_mm','temporal_reset']];write(dg[selected],'reference_and_mode_diagnostics.csv')
    if injections:
        inj=pd.DataFrame(injections)
        # Full result matrix is split deterministically by injection family.
        target=inj[~inj.channel.eq('ALL_non_target_points')]
        write(target[target.channel.str.contains(':YXJ')],'injection_YXJ_channels.csv')
        for night,g in target[target.channel.str.contains(':YJ')].groupby('night'):write(g,f'injection_YJ_{night}.csv')
        write(inj[inj.channel.eq('ALL_non_target_points')],'injection_results.csv')
        inj.to_pickle(W/f'injections_{stage}.pkl')
    result.to_pickle(W/f'metrics_{stage}.pkl')
    z=result[result.scope.eq('same_original_active_frames')&result.kind.eq('YXJ')];p=z.pivot_table(index=['night','channel'],columns='method',values='LF_Q95_Q05_mm');print(p.round(5).to_string());print('Source birth eligibility\n',pd.concat(birth).query('use==1 and marker_name.str.startswith("YJ")',engine='python')[['device_id','method','night_id','marker_name','historical_explained_energy','YJ_group_qualified','B_qualified','B_LOPO_gain']].to_string(index=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',default='ea');a=p.parse_args();evaluate(a.stage)
