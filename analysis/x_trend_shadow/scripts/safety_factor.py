from residual_factor import ResidualFactor
from safety import rows_for_response,waveform,targets
from common import *
import pickle,copy,time,argparse,concurrent.futures
from collections import deque

def encode(v):
 if isinstance(v,np.ndarray):return {'array':v.tolist(),'dtype':str(v.dtype)}
 if isinstance(v,deque):return {'deque':[encode(a) for a in v],'maxlen':v.maxlen}
 if isinstance(v,dict):return {k:encode(a) for k,a in v.items()}
 if isinstance(v,list):return [encode(a) for a in v]
 if isinstance(v,np.generic):return v.item()
 return v
def decode(v):
 if isinstance(v,dict):
  if 'array' in v:return np.array(v['array'],dtype=v['dtype'])
  if 'deque' in v:return deque([decode(a) for a in v['deque']],maxlen=v['maxlen'])
  return {k:decode(a) for k,a in v.items()}
 if isinstance(v,list):return [decode(a) for a in v]
 return v
def restart(k):
 d={key:value for key,value in k.__dict__.items() if key!='features'};d['features_state']=k.features.__dict__;d=decode(json.loads(json.dumps(encode(d),allow_nan=True)));q=ResidualFactor(k.names);q.features.__dict__.update(d.pop('features_state'));q.__dict__.update(d);return q

def one(q):
 line,dev=q['line'],q['device_id'];f=W/line/dev;src=load_data(line,dev);t=src['t'];names=src['names'].tolist();normal=np.load(f/'normal.npz');base=normal['base'];full=np.load(f/'factor.npz')['out'];status=list(pd.read_csv(f/'normal_frames.csv').itertuples(index=False));h,nights=clocks(t);snap=pickle.load((f/'factor_snapshots.pkl').open('rb'));rows=[];audit=[];tick=time.monotonic()
 for onset,(start,state) in snap.items():
  paths=sorted(f.glob('*_'+str(onset)+'.bin'));maximum=max((len(native_read(p)[1]) for p in paths),default=0)
  if not maximum:continue
  k=copy.deepcopy(state);control=np.full((maximum,len(names),2),np.nan)
  for j in range(maximum):
   ii=start+j;s=status[ii];out,_=k.step(t[ii],base[ii],s.base_gate,bool(s.base_ready),s.base_ncorrected,h[ii],nights[ii]);control[j]=np.column_stack([base[ii],out])
  assert np.allclose(control[:,:,1],full[start:start+maximum],rtol=0,atol=1e-10,equal_nan=True),'E clean prefix mismatch'
  paired={}
  for p in paths:
   scenario=p.name[:-(len(str(onset))+5)];nn,d=native_read(p);assert nn==names;nt=len(d);ts=d['t'];st=pd.read_csv(p.with_name(p.stem+'_frames.csv'));sr=list(st.itertuples(index=False));k=copy.deepcopy(state);v=np.full((nt,len(names),2),np.nan)
   for j in range(nt):
    if scenario=='restart' and j==30:k=restart(k)
    ii=start+j;s=sr[j];out,_=k.step(ts[j],d['base'][j],s.base_gate,bool(s.base_ready),s.base_ncorrected,h[ii],nights[ii]);v[j]=np.column_stack([d['base'][j],out]);assert d['y'][j].tobytes()==normal['y'][ii].tobytes()
   if scenario=='restart':assert np.array_equal(v,control[:nt],equal_nan=True),'E restart changed values'
   truth,nuisance,mask=waveform(scenario,ts,onset,names);known=truth+nuisance[:,None] if scenario.startswith('thermal_') else truth
   result=rows_for_response(line,dev,scenario,onset,ts,v,control[:nt],known,names,st.base_gate.to_numpy(),labels=['B0_original','E_residual_factor']);rows.extend(r for r in result if r['method']=='E_residual_factor')
   if scenario.startswith('thermal_'):paired[scenario]=(v,ts)
   if scenario=='crossnight_step1':
    for label,sub in [('night1_active',(nights[start:start+nt]==nights[start])&st.base_gate.gt(.99999).to_numpy()),('next_night_active',(nights[start:start+nt]!=nights[start])&st.base_gate.gt(.99999).to_numpy())]:
     if sub.sum()>=30:
      rr=rows_for_response(line,dev,scenario,onset,ts[sub],v[sub],control[:nt][sub],truth[sub],names,st.base_gate.to_numpy()[sub],label,['B0_original','E_residual_factor']);rows.extend(r for r in rr if r['method']=='E_residual_factor')
   audit.append(dict(line=line,device_id=dev,scenario=scenario,onset_beijing=iso(onset),frames=nt,snapshot_control_equal=True,JSON_restart_equal=True,Y_bitwise=True,original_monitor_unmodified=True,model_policy='causal own injected history; basis updates until01:30; no clean future history borrowed'))
   if dev in FOCUS and onset==epoch('2026-11-12 03:00') and scenario in ['node_step1','ramp3_3h','cohort20_step3','refs_nodes_step1','pulse1frame3','thermal_step1']:
    effect=abs((v-control[:nt])[:,:,1]-(v-control[:nt])[:,:,0]);err=np.where(~mask[None,:],effect,-1);worst=np.unravel_index(np.nanargmax(np.nan_to_num(err,nan=-1)),err.shape)[1];js=sorted(set([i for i,n in enumerate(names) if node(n)]+list(np.flatnonzero(mask))[:1]+[int(worst)]));ev=[]
    for i in js:
     for j in range(nt):ev.append(dict(line=line,device_id=dev,marker_name=names[i],scenario=scenario,timestamp_ms=int(ts[j]),known_input_mm=truth[j,i],known_synthetic_nuisance_mm=nuisance[j],B0_response_mm=v[j,i,0]-control[j,i,0],E_response_mm=v[j,i,1]-control[j,i,1],E_injected_output_mm=v[j,i,1],E_clean_output_mm=control[j,i,1]))
    save_parts(pd.DataFrame(ev),f'injection_windows_E/{line}_{dev}_{scenario}.csv')
  if 'thermal_step1' in paired and 'thermal_only' in paired:
   v,ts=paired['thermal_step1'];c,_=paired['thermal_only'];truth,_,_=waveform('thermal_step1',ts,onset,names);rr=rows_for_response(line,dev,'thermal_structural_pair',onset,ts,v,c,truth,names,np.ones(len(ts)),labels=['B0_original','E_residual_factor']);rows.extend(r for r in rr if r['method']=='E_residual_factor')
 save_parts(pd.DataFrame(rows),f'safety_E/{line}_{dev}.csv');save(audit,f'safety_E/{line}_{dev}_manifest.csv');r=dict(line=line,device_id=dev,scene_runs=len(audit),response_rows=len(rows),elapsed_seconds=time.monotonic()-tick);print(r,flush=True);return r

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');a=p.parse_args()
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(one,[q for q in roster() if not a.focus or q['device_id'] in FOCUS]))
 save(rows,'safety_E_run_'+('focus' if a.focus else 'all')+'.csv')
