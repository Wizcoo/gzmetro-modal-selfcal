from relations import *
import subprocess,concurrent.futures,time
SCENARIOS=['none','target_step','target_ramp','multiview_target_step','one_reference_step','coherent_reference_and_target_step','target_Y_settlement']
def job(dev,mode,scenario):
    root=W/'replay_cache';out=root/f'{mode}_{scenario}_{dev}.csv';start=time.monotonic()
    p=subprocess.run([str(root/'replay.exe'),str(root/f'{dev}.bin'),str(out),dev,mode,scenario],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    if p.returncode:raise RuntimeError(p.stdout or f'{mode} {scenario} {dev} failed {p.returncode}')
    return {'device_id':dev,'mode':mode,'scenario':scenario,'elapsed_seconds':time.monotonic()-start,'output_csv':out.name,'stdout':p.stdout.strip(),'exit_code':p.returncode,'bytes':out.stat().st_size}
def main():
    jobs=[(d,m,'none') for m in ['V51_cold','include_YJ','exclude_YXJ'] for d in DEVS]+[(d,'V51_cold',s) for s in SCENARIOS if s!='none' for d in DEVS]
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as e:
        fs=[e.submit(job,*args) for args in jobs]
        for f in concurrent.futures.as_completed(fs):r=f.result();rows.append(r);print(r['mode'],r['scenario'],r['device_id'],round(r['elapsed_seconds'],2),flush=True)
    write(pd.DataFrame(rows),'controlled_replay_runs.csv')
    # Export only reference-channel derivatives; working binaries, input packs
    # and multi-megabyte process intermediates stay outside the review branch.
    allrows=[]
    for mode in ['V51_cold','include_YJ','exclude_YXJ']:
        chunks=[]
        for dev in DEVS:
            p=W/'replay_cache'/f'{mode}_none_{dev}.csv';g=pd.read_csv(p)
            if not len(g):continue
            g['observing_device_id']=dev;g['channel']=dev+':'+g.markerName;g['mode']=mode;chunks.append(g)
        z=pd.concat(chunks,ignore_index=True);z.to_pickle(W/f'{mode}.pkl')
        if mode=='V51_cold':
            field=pd.read_pickle(W/'refs.pkl')[['channel','timestamp','calX']];j=z.merge(field,on=['channel','timestamp']);st=epoch('2026-11-06 23:20');en=epoch('2026-11-07 07:00');j=j[j.timestamp.ge(st)&j.timestamp.lt(en)]
            a=j.groupby('channel').apply(lambda q:pd.Series({'max_abs_replay_minus_field_mm':(q.replayX_mm-q.calX).abs().max(),'median_abs_difference_mm':(q.replayX_mm-q.calX).abs().median()}),include_groups=False).reset_index();write(a,'cold_replay_vs_field_discrepancy.csv')
        for night in ['2026-11-05','2026-11-06']:
            st=epoch(night+' 23:20');en=st+460*60000
            for ch,g in z[z.timestamp.ge(st)&z.timestamp.lt(en)].groupby('channel'):
                finite=np.isfinite(g.replayX_mm);s=g.loc[finite,['timestamp','replayX_mm']].set_index('timestamp').replayX_mm;sm=smooth(s);dt=np.diff(s.index);dx=np.diff(s.values);adj=(dt>=30000)&(dt<=90000)
                allrows.append({'mode':mode,'night_date':night,'channel':ch,'rows':len(g),'finite_rows':int(finite.sum()),'active_gate_fraction':g.gateX.gt(0).mean(),'modes_ready_fraction':g.modes_readyX.eq(1).mean(),'lowfreq_p95_p05_range_mm':sm.quantile(.95)-sm.quantile(.05),'step_abs_p99_mm':np.quantile(abs(dx[adj]),.99) if adj.sum() else np.nan,'interpretation':'controlled_cold_start_ablation_not_field_replay','history_before_start':'empty'})
    write(pd.DataFrame(allrows),'source_prefix_ablation_metrics.csv')
if __name__=='__main__':main()
