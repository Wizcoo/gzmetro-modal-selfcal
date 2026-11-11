from results import *

def main():
    rows=[]
    for dev in DEVS:
        names,_,_,_=load(W/'final'/f'normal_{dev}.bin');b=pd.read_csv(W/'final'/f'birth_{dev}.csv')
        for path in sorted((W/'final').glob(f'*_{dev}.bin')):
            if path.name.startswith('normal_'):continue
            scenario,onset,_=path.stem.rsplit('_',2);onset=int(onset);night=(pd.Timestamp(onset,unit='ms',tz='UTC').tz_convert('Asia/Shanghai')-pd.Timedelta(days=1)).strftime('%Y-%m-%d');nid=int(pd.Timestamp(night).timestamp()/86400);bb=b[b.method.eq('identity')&b.night_id.eq(nid)];learn=bb[bb.learn.eq(1)];high=int(learn.loc[learn.leverage.idxmax()].point_index);refs=[n for n in names if n.startswith('YJ')];keys=[n for n in names if n.startswith(('YJ','YXJ'))];target=[];axis='X';shape='step';amp=3 if scenario.endswith('3') else 1
            if scenario.startswith('YXJ') and '_step' in scenario:target=[scenario.split('_')[0]] if scenario.split('_')[0] in names else []
            elif scenario.startswith('YXJ_ramp'):target=[n for n in names if n.startswith('YXJ')];shape='ramp';amp=3 if '3_3h' in scenario else 1
            elif scenario.startswith('single_ref'):target=['YJ7'] if 'YJ7' in refs else refs[:1]
            elif scenario.startswith('multiple_ref'):target=refs
            elif scenario.startswith('coherent'):target=keys
            elif scenario.startswith('learner'):target=[names[high]];shape='first_real_frame_pulse' if 'spike' in scenario else 'step'
            elif scenario=='reference_spike3':target=['YJ7'] if 'YJ7' in refs else refs[:1];shape='first_real_frame_pulse'
            elif scenario.startswith('modal'):target=[names[int(i)] for i in bb[bb.use.eq(1)].point_index] if keys else [];shape='original_A1_normalized_by_max_key_loading';amp=3 if '3' in scenario else 1
            elif scenario=='missing_refs':target=refs;shape='NaN10min_then_recovery';amp=np.nan
            elif scenario=='missing_learners':target=[names[int(i)] for i in learn.point_index];shape='NaN10min_then_recovery';amp=np.nan
            elif scenario=='Y_settlement':target=['YXJ5'] if 'YXJ5' in names else [];axis='Y';amp=-1
            rows.append({'device_id':dev,'night':night,'onset_beijing':iso(onset),'scenario':scenario,'axis':axis,'input_shape':shape,'amplitude_mm_at_target_or_max_key':amp,'target_names':'|'.join(target),'target_present':bool(target),'highest_leverage_learning_point':names[high],'highest_historical_leverage':learn.leverage.max(),'geometry':'observation_domain_only; no world projection','state':'same pre03 memory snapshot; no refit'})
    write(pd.DataFrame(rows),'injection_target_manifest.csv')
if __name__=='__main__':main()
