from run_replays import job
from relations import *
import concurrent.futures
def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:runs=list(ex.map(lambda d:job(d,'include_YJ','one_reference_step'),DEVS))
    write(pd.DataFrame(runs),'extra_reference_fault_runs.csv');rows=[]
    for mode in ['V51_cold','include_YJ']:
        for dev in DEVS:
            a=pd.read_csv(W/'replay_cache'/f'{mode}_none_{dev}.csv');b=pd.read_csv(W/'replay_cache'/f'{mode}_one_reference_step_{dev}.csv')
            if not len(a):continue
            g=a.merge(b,on=['timestamp','markerName'],suffixes=('_base','_inj'),validate='one_to_one');g=g[g.timestamp.ge(epoch('2026-11-07 03:00'))&g.timestamp.lt(epoch('2026-11-07 07:00'))&g.markerName.str.startswith('YXJ')]
            for name,z in g.groupby('markerName'):rows.append({'mode':mode,'channel':dev+':'+name,'max_spurious_YXJ_X_change_mm':(z.replayX_mm_inj-z.replayX_mm_base).abs().max(),'Y_changed_max_mm':(z.replayY_mm_inj-z.replayY_mm_base).abs().max(),'injection':'YJ7 only +1mm at 03:00 in all observers','interpretation':'controlled_source_sensitivity_not_world_geometry'})
    write(pd.DataFrame(rows),'source_reference_fault_sensitivity.csv');print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':main()
