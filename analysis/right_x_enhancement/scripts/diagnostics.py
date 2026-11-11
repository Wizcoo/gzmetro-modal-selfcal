from results import *

def main():
    rows=[];lags=[];history=[];spatial=[];series=[]
    for dev in DEVS:
        names,modes,fields,d=load(W/'final'/f'normal_{dev}.bin');di={n:i for i,n in enumerate(fields)};t=d['ts'];dd=d['methods']['diag'];birth=pd.read_csv(W/'final'/f'birth_{dev}.csv');keyids=[i for i,n in enumerate(names) if n.startswith(('YJ','YXJ'))]
        # Independent diagnostic decomposition, including per-order gated
        # contributions and explicit non-modal increment (only spatial B).
        for night in ['2026-11-05','2026-11-06']:
            nid=int(pd.Timestamp(night).timestamp()/86400);b=birth[birth.night_id.eq(nid)&birth.method.eq('identity')].set_index('point_index');st=epoch(night+' 23:20');en=st+460*60000;core=(t>=st)&(t<en)&(dd[:,0,di['n_corrected']]>0)
            history.append({'device_id':dev,'night':night,'history_nights_at_model_birth':int(b.n_history.max()),'C_recent_weighted_output_distinguishable':False,'reason':'First night cold model born02:00; second night23:00 has only one prior night. A single common historical weight cancels in S/N; no prospective two-history test night in data.'})
            for mi,method in enumerate(modes):
                if method=='identity':continue
                v=dd[:,mi,[di['v_used_1'],di['v_used_2'],di['v_used_3']]];gate=dd[:,mi,di['gate']];active=core&np.isfinite(v).all(axis=1)
                for lag in range(6):
                    target=np.flatnonzero(active);past=target-lag;ok=past>=0;target=target[ok];past=past[ok];gap=(t[target]-t[past])<=lag*90000+1;target=target[gap];past=past[gap];dv=dd[past,0][:,[di['v_used_1'],di['v_used_2'],di['v_used_3']]]-v[target];lags.append({'device_id':dev,'method':method,'night':night,'lag_frames':lag,'coefficient_RMS_vs_lagged_original':np.sqrt(np.mean(dv*dv)),'not_truth':'Observed coefficient lag proxy, not physical displacement delay'})
                for i in keyids:
                    if i not in b.index:continue
                    ai=b.loc[i,['A1','A2','A3']].to_numpy(float);contr=gate[:,None]*v*ai;cb=gate*b.loc[i,'cbar_mm'];total=d['rawx'][:,i]-d['methods']['x'][:,mi,i];extra=total-contr.sum(axis=1)+cb
                    for start in range(st,en,3600000):
                        mask=core&(t>=start)&(t<min(en,start+3600000))&np.isfinite(total)
                        if not mask.any():continue
                        z=birth[birth.method.eq(method)&birth.night_id.eq(nid)&birth.point_index.eq(i)];qual=z.YJ_group_qualified.iloc[0] if len(z) else np.nan
                        rows.append({'device_id':dev,'marker_name':names[i],'method':method,'night':night,'start_beijing':iso(start),'end_exclusive_beijing':iso(min(en,start+3600000)),'frames':int(mask.sum()),'reference_historical_energy_explained':b.loc[i,'historical_explained_energy'],'reference_group_historical_qualified':qual,'order1_mean_gated_mm':contr[mask,0].mean(),'order2_mean_gated_mm':contr[mask,1].mean(),'order3_mean_gated_mm':contr[mask,2].mean(),'cbar_mean_gated_mm':cb[mask].mean(),'total_mean_correction_mm':total[mask].mean(),'nonmodal_mean_increment_mm':extra[mask].mean(),'unit':'mm_API_contract; not physical truth'})
            # Continuous selected evidence: one core hour from each night,
            # including native coefficients and reference qualification.
            for marker in (['YXJ2','YJ2'] if dev.endswith('173835') else ['YXJ6','YJ6'] if dev.endswith('346578') else []):
                if marker not in names:continue
                i=names.index(marker);mask=(t>=epoch(('2026-11-06' if night=='2026-11-05' else '2026-11-07')+' 03:00'))&(t<epoch(('2026-11-06' if night=='2026-11-05' else '2026-11-07')+' 05:00'))
                z=pd.DataFrame({'timestamp':t[mask],'time_beijing':[iso(x) for x in t[mask]],'device_id':dev,'marker_name':marker,'raw_X_mm':d['rawx'][mask,i]})
                for mi,method in enumerate(modes):
                    if method=='identity':continue
                    z[method+'_X_mm']=d['methods']['x'][mask,mi,i]
                    if method in ['A','D_EMA','D_Kalman']:
                        for kk in range(3):z[method+f'_v{kk+1}']=dd[mask,mi,di[f'v_used_{kk+1}']]
                    if method=='A':z['A_current_reference_count']=dd[mask,mi,di['qualified_current_refs']];z['A_rejected_references']=dd[mask,mi,di['rejected_refs']]
                write(z,f'continuous/{dev}_{marker}_{night}.csv')
        for path in (W/'final').glob(f'modal_step*_{dev}.bin'):
            kn,mm,ff,z=load(path);_,onset,_=path.stem.rsplit('_',2);onset=int(onset);j=pd.Index(t).get_indexer(z['ts']);coefcols=[di[f'v_used_{i}'] for i in range(1,4)];delta=z['methods']['diag'][:,:,coefcols]-d['methods']['diag'][j][:,:,coefcols];late=z['ts']>=onset+210*60000;truth=np.median(delta[late,0],axis=0);norm=np.linalg.norm(truth)
            for mi,method in enumerate(modes):
                if method=='identity':continue
                identifiable=norm>1e-6;error=np.linalg.norm(delta[:,mi]-truth,axis=1)/max(norm,1e-10);delay=np.nan
                for h in range(len(z)-4):
                    if identifiable and np.all(error[h:h+5]<=.05):delay=h;break
                lags.append({'device_id':dev,'method':method,'night':iso(onset)[:10],'scenario':path.stem.rsplit('_',2)[0],'response_identifiable':identifiable,'source_coefficient_step_norm':norm,'coefficient_step95_delay_frames':delay,'coefficient_step95_delay_seconds':(z['ts'][int(delay)]-z['ts'][0])/1000 if np.isfinite(delay) else np.nan,'steady_coefficient_gain_vs_V51':np.linalg.norm(np.median(delta[late,mi],axis=0))/norm if identifiable else np.nan,'max_coefficient_transient_relative_error':error.max() if identifiable else np.nan,'not_truth':'known observation-mode input; compares to actual original V51 response, not world geometry; no key basis at333715 means no defined mode-shaped input'})
    write(pd.DataFrame(rows),'point_mode_contributions.csv');write(pd.DataFrame(lags),'coefficient_delay_diagnostics.csv');write(pd.DataFrame(history),'historical_adaptation_limits.csv')
    print('Mode decomposition, continuous evidence, timing and historical sufficiency exported')
if __name__=='__main__':main()
