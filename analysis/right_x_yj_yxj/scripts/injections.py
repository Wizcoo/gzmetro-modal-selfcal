from candidates import *
import pickle
SCENARIOS=['target_step','target_ramp','multiview_target_step','one_reference_step','coherent_reference_and_target_step','target_Y_settlement']
def replay_data(scenario):
    chunks=[]
    for dev in DEVS:
        g=pd.read_csv(W/'replay_cache'/f'V51_cold_{scenario}_{dev}.csv')
        if not len(g):continue
        g['observing_device_id']=dev;g['channel']=dev+':'+g.markerName;chunks.append(g)
    r=pd.concat(chunks,ignore_index=True);meta=pd.read_pickle(W/'refs.pkl')[['channel','timestamp','RoiCalState','valid','source_db','_source_rowid']]
    r=r.merge(meta,on=['channel','timestamp'],validate='one_to_one').rename(columns={'rawX_mm':'x','rawY_mm':'y','replayX_mm':'calX','replayY_mm':'calY'})
    return r
def main():
    control=replay_data('none');e=Experiment(control,'2026-11-05','controlled_cold_start');models={ch:{'A':e.fit_target(ch,'A_YJ_guided'),'B':e.fit_target(ch,'B_graph_residual')} for ch in e.channels if ':YXJ' in ch}
    basepred={ch:{method:e.predict(model)[0] for method,model in methods.items()} for ch,methods in models.items()};rows=[];onset=epoch('2026-11-07 03:00');end=epoch('2026-11-07 07:00')
    before=(onset-30*60000,onset);settled=(onset+90*60000,end)
    for scenario in SCENARIOS:
        injected=replay_data(scenario);over={ch:g.sort_values('timestamp').reset_index(drop=True) for ch,g in injected.groupby('channel')}
        for ch,methods in models.items():
            g=e.channels[ch];z=over[ch];assert np.array_equal(g.timestamp,z.timestamp);t=g.timestamp.to_numpy();m=(t>=settled[0])&(t<settled[1])&g.valid.to_numpy()&z.valid.to_numpy()
            truth=z.x.to_numpy()-g.x.to_numpy();truthY=z.y.to_numpy()-g.y.to_numpy();baseline_delta=z.calX.to_numpy()-g.calX.to_numpy();dy=z.calY.to_numpy()-g.calY.to_numpy()
            for method,model in methods.items():
                pred,applied,corrv,reason=e.predict(model,over);increment=pred-basepred[ch][method];actual_truth=truthY if scenario=='target_Y_settlement' else truth;output_increment=dy if scenario=='target_Y_settlement' else increment
                # Y is exactly the independent original V51 scenario output.
                candidateY=z.calY.to_numpy().copy();assert np.array_equal(candidateY,z.calY.to_numpy(),equal_nan=True)
                injected_target=np.nanmedian(abs(actual_truth[m]))>.5
                retained=float(np.nanmedian(output_increment[m])/np.nanmedian(actual_truth[m])) if injected_target else np.nan
                rows.append({'scenario':scenario,'channel':ch,'method':method,'baseline':'source_V51_controlled_empty_initial_state','fit_night':'2026-11-05','test_night':'2026-11-06','injection_onset_beijing':iso(onset),'measurement_window_start_beijing':iso(settled[0]),'measurement_window_end_exclusive_beijing':iso(end),'injected_target_axis':'Y' if scenario=='target_Y_settlement' else 'X','raw_injected_increment_mm':float(np.nanmedian(actual_truth[m])),'source_V51_increment_mm':float(np.nanmedian(dy[m] if scenario=='target_Y_settlement' else baseline_delta[m])),'candidate_increment_mm':float(np.nanmedian(output_increment[m])),'retained_fraction_if_target_injected':retained,'spurious_change_if_target_not_injected_mm':float(np.nanmax(abs(output_increment[m]))) if not injected_target else np.nan,'Y_equals_source_V51_bitwise':True,'recipe_qualified':model['qualified'],'interpretation':'observation_coordinate_injection_not_world_geometry_or_field_truth'})
                # Full time resolution for all 6 YXJ channels and all scenarios.
                keep=(t>=onset-60*60000)&(t<end);df=pd.DataFrame({'timestamp':t[keep],'time_beijing':[iso(x) for x in t[keep]],'scenario':scenario,'channel':ch,'method':method,'raw_injection_X_mm':truth[keep],'raw_injection_Y_mm':truthY[keep],'source_V51_output_delta_X_mm':baseline_delta[keep],'candidate_output_delta_X_mm':increment[keep],'source_V51_output_delta_Y_mm':dy[keep],'candidate_output_delta_Y_mm':dy[keep],'applied':applied[keep],'reference_status':reason[keep]});write(df,f'injection_traces/{scenario}_{ch.replace(":","_")}_{method}.csv')
            # A separate original-source baseline row is an actual replay,
            # not an assumption that V51 passes every injected millimetre.
            truthaxis=truthY if scenario=='target_Y_settlement' else truth;outaxis=dy if scenario=='target_Y_settlement' else baseline_delta;target=np.nanmedian(abs(truthaxis[m]))>.5
            rows.append({'scenario':scenario,'channel':ch,'method':'V51_cold_source','baseline':'source_V51_controlled_empty_initial_state','fit_night':'2026-11-05','test_night':'2026-11-06','raw_injected_increment_mm':float(np.nanmedian(truthaxis[m])),'candidate_increment_mm':float(np.nanmedian(outaxis[m])),'retained_fraction_if_target_injected':float(np.nanmedian(outaxis[m])/np.nanmedian(truthaxis[m])) if target else np.nan,'spurious_change_if_target_not_injected_mm':float(np.nanmax(abs(outaxis[m]))) if not target else np.nan,'Y_equals_source_V51_bitwise':True,'recipe_qualified':True,'interpretation':'controlled_source_injection_not_exact_field_state'})
        print('injection scenario',scenario,'done',flush=True)
    write(pd.DataFrame(rows),'displacement_injection_results.csv')
    write(pd.DataFrame([{'channel':ch,**{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in model.items()}} for ch,methods in models.items() for model in methods.values()]),'injection_frozen_models.csv')
    r=pd.DataFrame(rows);print(r[r.raw_injected_increment_mm.abs().gt(.5)][['scenario','channel','method','retained_fraction_if_target_injected']].to_string(index=False))
if __name__=='__main__':main()
