from common import *
from shadow import ShadowTrend
from l1_cpp import L1TrendCpp
LEGACY_METHODS=METHODS[:7]
from state_io import export_shadow,restore_shadow,export_l1,restore_l1
import pickle,copy,time,concurrent.futures,argparse,warnings

def quant(a,q,axis=0):
 with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);return np.nanquantile(a,q,axis=axis)

class Post:
 def __init__(self,k,t,base,w3,start):
  self.k=copy.deepcopy(k);self.k.model_override=self.k.models.get(self.k.night);p=base.shape[1];self.d=L1TrendCpp(p);self.dw=L1TrendCpp(p)
  # Stateless optimizer:15 prior native frames reconstruct the full memory.
  for j in range(max(0,start-15),start):self.d.step(t[j],base[j],0,False,0,3);self.dw.step(t[j],w3[j],0,False,0,3)
 def restart(self):
  self.k=restore_shadow(export_shadow(self.k),self.k.models);self.d=restore_l1(export_l1(self.d));self.dw=restore_l1(export_l1(self.dw))
 def step(self,t,base,w3,y,T,s,h,night):
  payload={'opaque_original_alarm':['unchanged',int(t)]};xx=base;yy=y;before=xx.tobytes()+yy.tobytes();r=self.k.step(t,xx,yy,T,s.base_gate,bool(s.base_ready),s.base_ncorrected,h,night,alarms=payload);d,qa=self.d.step(t,base,s.base_gate,bool(s.base_ready),s.base_ncorrected,h);inner,qb=self.dw.step(t,w3,s.w3_gate,bool(s.w3_ready),s.w3_ncorrected,h);dw=base+qa['gate']*(inner-base);assert before==xx.tobytes()+yy.tobytes() and r['monitor_x'] is xx and r['monitor_y'] is yy and r['alarms'] is payload
  r['L1_uncertified_points']=qa['nonconverged_points']+qb['nonconverged_points'];r['L1_numeric_bound_mm']=max(qa['primal_mm'],qb['primal_mm']);return np.column_stack([base,w3,r['trend_x'],d,dw]),r

def targets(scenario,names):
 n=len(names);target=next((i for i,s in enumerate(names) if node(s)),0);ordinary=next(i for i,s in enumerate(names) if not ref(s) and not node(s));reference=next((i for i,s in enumerate(names) if ref(s)),-1);mask=np.zeros(n,bool)
 if scenario=='ordinary_step3':mask[ordinary]=True
 elif scenario.startswith('cohort20'):mask=np.array([((37*i+11)%n)<max(1,int(np.floor(.2*n+.5))) for i in range(n)])
 elif scenario=='refs_nodes_step1':mask=np.array([ref(s) or node(s) for s in names])
 elif scenario=='reference_step3':mask[reference]=True
 elif scenario=='references_step1':mask=np.array([ref(s) for s in names])
 elif scenario not in ['thermal_only','restart']:mask[target]=True
 return mask

def waveform(scenario,t,onset,names):
 mask=targets(scenario,names);amp=3 if '3' in scenario else 1;h=(t-onset)/3600000.;a=np.full(len(t),amp,dtype=float)
 if scenario=='ramp1_1h':a=np.minimum(1.,h)
 if scenario=='ramp3_3h':a=np.minimum(3.,h)
 if scenario=='pulse1frame3':a[:]=0;a[0]=3
 if scenario=='pulse2frame3':a[:]=0;a[:2]=3
 if scenario in ['missing10','restart','thermal_only']:a[:]=0
 truth=a[:,None]*mask[None,:];nuisance=np.minimum(2.,2*h)*.4 if scenario.startswith('thermal_') else np.zeros(len(t));return truth,nuisance,mask

def rows_for_response(line,dev,scenario,onset,t,values,control,truth,names,gate,scope='whole_suffix',labels=None):
 response=values-control;baseline=response[:,:,0];extra=response-baseline[:,:,None];valid=np.isfinite(response)&np.isfinite(truth[:,:,None]);late=t>=t[-1]-1800000;rows=[];cohort=np.any(abs(truth)>1e-9,axis=0)
 for mi,method in enumerate(METHODS[:values.shape[2]] if labels is None else labels):
  actual=response[:,:,mi];b=baseline;ok=valid[:,:,mi];stable=quant(np.where(ok&late[:,None],actual,np.nan),.5);known=quant(np.where(ok&late[:,None],truth,np.nan),.5);bs=quant(np.where(ok&late[:,None],b,np.nan),.5);counts=ok.sum(axis=0);rmse=np.sqrt(np.divide(np.nansum(np.where(ok,(actual-truth)**2,np.nan),axis=0),counts,out=np.full(len(names),np.nan),where=counts>0));er=np.sqrt(np.divide(np.nansum(np.where(ok,extra[:,:,mi]**2,np.nan),axis=0),counts,out=np.full(len(names),np.nan),where=counts>0));peak=quant(np.where(ok,abs(actual),np.nan),1);truepeak=quant(np.where(ok,abs(truth),np.nan),1);maxextra=quant(np.where(ok,abs(extra[:,:,mi]),np.nan),1)
  for j,name in enumerate(names):
   if np.isfinite(actual[:,j]).sum()<10:continue
   delay=rel_delay=np.nan;first=np.flatnonzero(ok[:,j]);bdelay=np.nan
   if cohort[j] and ('step' in scenario or scenario in ['reference_step3','references_step1','thermal_structural_pair']):
    for target,label in [(known[j],'known'),(bs[j],'baseline')]:
     if abs(target)<.01:continue
     good=ok[:,j]&(actual[:,j]/target>=.95)&(actual[:,j]/target<=1.05);bgood=ok[:,j]&(b[:,j]/target>=.95)&(b[:,j]/target<=1.05)
     found=next((k for k in range(len(good)-2) if good[k:k+3].all()),None);bfound=next((k for k in range(len(bgood)-2) if bgood[k:k+3].all()),None)
     if label=='known' and found is not None:delay=(t[found]-onset)/1000
     if label=='baseline' and found is not None and bfound is not None:rel_delay=(t[found]-t[bfound])/1000;bdelay=(t[bfound]-onset)/1000
   slope=bslope=truth_slope=np.nan
   if scenario.startswith('ramp') and cohort[j]:
    dur=3 if '3h' in scenario else 1;ms=ok[:,j]&(t<onset+dur*3600000)
    if ms.sum()>=20:
     hours=(t[ms]-onset)/3600000.;slope=np.polyfit(hours,actual[ms,j],1)[0];bslope=np.polyfit(hours,b[ms,j],1)[0];truth_slope=np.polyfit(hours,truth[ms,j],1)[0]
   rows.append(dict(line=line,device_id=dev,scenario=scenario,onset_beijing=iso(onset),evaluation_scope=scope,method=method,marker_name=name,kind=kind(name),target=bool(cohort[j]),source_step_mask=bool(targets(scenario if scenario!='thermal_structural_pair' else 'thermal_step1',names)[j]),stable_known_mm=known[j],stable_response_mm=stable[j],B0_stable_response_mm=bs[j],retention=stable[j]/known[j] if abs(known[j])>1e-9 else np.nan,B0_retention=bs[j]/known[j] if abs(known[j])>1e-9 else np.nan,additional_amplitude_loss_mm=bs[j]-stable[j],waveform_RMSE_vs_known_mm=rmse[j],extra_waveform_RMSE_vs_B0_mm=er[j],max_extra_response_vs_B0_mm=maxextra[j],max_abs_response_mm=peak[j],known_peak_mm=truepeak[j],peak_retention=peak[j]/truepeak[j] if truepeak[j]>1e-9 else np.nan,peak_bias_mm=peak[j]-truepeak[j],delay95_known_seconds=delay,extra_delay95_vs_B0_seconds=rel_delay,B0_delay95_seconds=bdelay,first_valid_seconds=(t[first[0]]-onset)/1000 if len(first) else np.nan,slope_mm_per_hour=slope,B0_slope_mm_per_hour=bslope,known_slope_mm_per_hour=truth_slope,additional_slope_error_mm_per_hour=slope-bslope,active_B0_frames=int(np.sum(gate>=.99999)),frames=len(t),meaning='paired observation-domain response; not world-coordinate accuracy'))
 return rows

def one(q):
 line,dev=q['line'],q['device_id'];folder=W/line/dev;a=load_data(line,dev);t=a['t'];names=a['names'].tolist();T=a['temperature'];normal=np.load(folder/'normal.npz');base=normal['base'];w3=normal['w3'];y=normal['y'];statuses=pd.read_csv(folder/'normal_frames.csv');statusrows=list(statuses.itertuples(index=False));h,nights=clocks(t);saved=pickle.load((folder/'models_and_snapshots.pkl').open('rb'));allrows=[];audit=[];evidence=[];tick=time.monotonic()
 for onset,(start,kernel) in saved['snapshots'].items():
  paths=sorted(folder.glob('*_'+str(onset)+'.bin'));maximum=max((len(native_read(p)[1]) for p in paths),default=0)
  if not maximum:continue
  end=start+maximum;controller=Post(kernel,t,base,w3,start);control=np.full((maximum,len(names),len(LEGACY_METHODS)),np.nan)
  for ii in range(start,end):control[ii-start],_=controller.step(t[ii],base[ii],w3[ii],y[ii],T[ii],statusrows[ii],h[ii],nights[ii])
  # Short clean control must match the separately run complete streams.
  old=np.load(folder/'extended_candidates.npz');check=min(maximum,230);expected=np.concatenate([base[start:start+check,:,None],w3[start:start+check,:,None],old['out'][start:start+check]],axis=2);assert np.allclose(control[:check],expected,atol=1e-10,rtol=0,equal_nan=True),('snapshot mismatch',line,dev,onset)
  scenevalues={};scenets={}
  for path in paths:
   scenario=path.name[:-(len(str(onset))+5)];nn,d=native_read(path);assert nn==names;nt=len(d);ts=d['t'];assert np.array_equal(ts,t[start:start+nt]);st=pd.read_csv(path.with_name(path.stem+'_frames.csv'));sr=list(st.itertuples(index=False));controller=Post(kernel,t,base,w3,start);values=np.full((nt,len(names),len(LEGACY_METHODS)),np.nan);rs=np.zeros((nt,len(names)),bool);numeric_failed=0;numeric_bound=0.
   for j in range(nt):
    if scenario=='restart' and j==30:controller.restart()
    ii=start+j;temp=T[ii]
    if scenario.startswith('thermal_'):temp+=min(2.,2*(ts[j]-onset)/3600000.)
    values[j],info=controller.step(ts[j],d['base'][j],d['w3'][j],d['y'][j],temp,sr[j],h[ii],nights[ii]);rs[j]=info['event'];numeric_failed+=info['L1_uncertified_points'];numeric_bound=max(numeric_bound,info['L1_numeric_bound_mm'])
    assert d['y'][j].tobytes()==y[ii].tobytes(),'native Y persisted mismatch'
   if scenario=='restart':assert np.array_equal(values,control[:nt],equal_nan=True),'JSON restart changes candidate'
   truth,nuisance,mask=waveform(scenario,ts,onset,names);cc=control[:nt];gate=st.base_gate.to_numpy();allrows.extend(rows_for_response(line,dev,scenario,onset,ts,values,cc,truth+nuisance[:,None] if scenario.startswith('thermal_') else truth,names,gate));scenevalues[scenario]=values if scenario.startswith('thermal_') else None;scenets[scenario]=ts
   if scenario=='crossnight_step1':
    hh,ni=clocks(ts)
    for label,sub in [('night1_active',(ni==nights[start])&(gate>.99999)),('next_night_active',(ni!=nights[start])&(gate>.99999)&((hh>=23)|(hh<7)))]:
     if sub.sum()>=30:allrows.extend(rows_for_response(line,dev,scenario,onset,ts[sub],values[sub],cc[sub],truth[sub],names,gate[sub],label))
   audit.append(dict(line=line,device_id=dev,scenario=scenario,onset_beijing=iso(onset),frames=nt,targets=int(mask.sum()),baseline_ready=int(st.base_ready.iloc[0]),baseline_gate=st.base_gate.iloc[0],Y_bitwise=True,original_alarm_passthrough=True,model_freeze='snapshot-night bank for both clean and injected suffix, including next night',restart_exact=scenario=='restart',next_night_available=bool(np.any(nights[start:start+nt]!=nights[start])),L1_uncertified_point_frames=numeric_failed,L1_max_numeric_bound_mm=numeric_bound))
   # Continuous full-resolution evidence, selected mechanisms and all key
   # nodes plus the target/most affected non-target. No time subsampling.
   if dev in FOCUS and onset==epoch('2026-11-12 03:00') and scenario in ['node_step1','ramp3_3h','cohort20_step3','refs_nodes_step1','pulse1frame3','pulse2frame3','thermal_step1','missing10']:
    effect=abs((values-cc)[:,:,5]-(values-cc)[:,:,0]);zero=np.all(abs(truth)<1e-9,axis=0);err=np.where(zero[None,:],effect,-1);pos=np.unravel_index(np.nanargmax(np.nan_to_num(err,nan=-1)),err.shape);selected=sorted(set([j for j,n in enumerate(names) if node(n)]+list(np.flatnonzero(mask))[:1]+[int(pos[1])]))
    rows=[]
    for j in selected:
     for i,ts0 in enumerate(ts):
      r=dict(line=line,device_id=dev,marker_name=names[j],scenario=scenario,timestamp_ms=int(ts0),time_beijing=iso(ts0),known_physical_input_mm=truth[i,j],known_synthetic_thermal_nuisance_mm=nuisance[i],target=bool(mask[j]),base_gate=gate[i],source_original_Y_mm=d['y'][i,j],preserved_event=bool(rs[i,j]))
      for mi,m in enumerate(LEGACY_METHODS):r[m+'_response_mm']=values[i,j,mi]-cc[i,j,mi];r[m+'_injected_output_mm']=values[i,j,mi];r[m+'_clean_output_mm']=cc[i,j,mi]
      rows.append(r)
    save_parts(pd.DataFrame(rows),f'injection_windows/{line}_{dev}_{scenario}.csv')
   print(line,dev,iso(onset),scenario,'frames',nt,flush=True)
  if 'thermal_step1' in scenevalues and 'thermal_only' in scenevalues:
   v=scenevalues['thermal_step1'];c=scenevalues['thermal_only'];ts=scenets['thermal_step1'];truth,_,_=waveform('thermal_step1',ts,onset,names);allrows.extend(rows_for_response(line,dev,'thermal_structural_pair',onset,ts,v,c,truth,names,np.ones(len(ts))))
 save_parts(pd.DataFrame(allrows),f'safety/{line}_{dev}.csv');save(pd.DataFrame(audit),f'safety/{line}_{dev}_manifest.csv');r={'line':line,'device_id':dev,'elapsed_seconds':time.monotonic()-tick,'scene_runs':len(audit),'response_rows':len(allrows),'snapshot_controls_equal':True,'JSON_restart_equal':True,'Y_bitwise':True,'original_alarm_payload_unchanged':True};print(r,flush=True);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');p.add_argument('--device');a=p.parse_args();todo=[q for q in roster() if (not a.focus or q['device_id'] in FOCUS) and (a.device is None or q['device_id']==a.device)];rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for r in pool.map(one,todo):rows.append(r)
 save(rows,'safety_run_'+(a.device or ('focus' if a.focus else 'all'))+'.csv')

if __name__=='__main__':main()
