from shadow import *
import argparse,time,concurrent.futures,pickle

def run_one(q):
 line,dev=q['line'],q['device_id'];folder=W/line/dev;a=load_data(line,dev);d=np.load(folder/'normal.npz');status=pd.read_csv(folder/'normal_frames.csv');t=a['t'];T=a['temperature'];names=a['names'].tolist();x=d['base'];y=d['y'];gates=status.base_gate.to_numpy();ready=status.base_ready.to_numpy();ncorrected=status.base_ncorrected.to_numpy();states=status.base_state.to_numpy();tick=time.monotonic();models,admission,features=bank(t,x,T,status,names);kernel=ShadowTrend(names,models);h,nights=clocks(t);out=np.full((len(t),len(names),3),np.nan);modes=np.zeros((len(t),len(names)),np.int8);events=modes.copy();eligible=np.zeros_like(out,bool);diagnostics=[];snapshots={};times=[]
 onsets=[epoch('2026-11-10 03:00'),epoch('2026-11-12 03:00')]
 for i,ts in enumerate(t):
  for onset in onsets:
   if i and ts>=onset and t[i-1]<onset:
    import copy
    snapshots[onset]=(i,copy.deepcopy(kernel))
  xx,yy=x[i],y[i];before=xx.tobytes()+yy.tobytes();alarms={'original_state':states[i]};tick0=time.perf_counter_ns();r=kernel.step(ts,xx,yy,T[i],gates[i],bool(ready[i]),ncorrected[i],h[i],nights[i],alarms=alarms);times.append((time.perf_counter_ns()-tick0)/1000)
  assert before==xx.tobytes()+yy.tobytes() and r['monitor_x'] is xx and r['monitor_y'] is yy and r['alarms'] is alarms
  out[i]=r['trend_x'];modes[i]=r['event_mode'];events[i]=r['event'];eligible[i]=r['eligible'];diagnostics.append([r['gate'],r['reference_quality'],r['reference_event_latched'],np.nanmedian(r['thermal_gain'])])
 np.savez_compressed(folder/'candidates.npz',out=out,mode=modes,event=events,eligible=eligible,diagnostics=np.array(diagnostics),time_us=times)
 with (folder/'models_and_snapshots.pkl').open('wb') as f:pickle.dump({'models':models,'snapshots':snapshots},f)
 admission['line']=line;admission['device_id']=dev;save(admission,'admission/'+line+'_'+dev+'.csv');save_json({'names':names,'models':models,'implementation':'x-trend-shadow-v1','units':'mm; temperature degC; scalar gains dimensionless','not_monitor_or_alarm_model':True},'models/'+line+'_'+dev+'.json')
 r={'line':line,'device_id':dev,'elapsed_seconds':time.monotonic()-tick,'frames':len(t),'points':len(names),'mean_us':float(np.mean(times)),'P99_us':float(np.quantile(times,.99)),'Y_unchanged':True,'monitor_and_alarm_unchanged':True};print(r,flush=True);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');p.add_argument('--missing-only',action='store_true');a=p.parse_args();rows=[]
 # numpy small linear algebra benefits from independent device threads;
 # each owns all model/state/history and never writes another device.
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for q in pool.map(run_one,[q for q in roster() if (not a.focus or q['device_id'] in FOCUS) and (not a.missing_only or not (W/q['line']/q['device_id']/'candidates.npz').exists())]):rows.append(q)
 save(rows,'candidate_run_'+('missing' if a.missing_only else 'focus' if a.focus else 'all')+'.csv')

if __name__=='__main__':main()
