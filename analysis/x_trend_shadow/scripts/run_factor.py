from residual_factor import *
import argparse,pickle,copy,time,concurrent.futures

def one(q):
 line,dev=q['line'],q['device_id'];folder=W/line/dev;src=load_data(line,dev);d=np.load(folder/'normal.npz');t=src['t'];x=d['base'];names=src['names'].tolist();st=pd.read_csv(folder/'normal_frames.csv');status=list(st.itertuples(index=False));h,nights=clocks(t);kernel=ResidualFactor(names);out=np.full_like(x,np.nan);eligible=np.zeros(x.shape,bool);sparse=eligible.copy();diag=[];models=[];snapshots={};times=[];tick=time.monotonic();lastmodel=-1
 for i,ts in enumerate(t):
  for onset in [epoch('2026-11-10 03:00'),epoch('2026-11-12 03:00')]:
   if i and ts>=onset and t[i-1]<onset:snapshots[onset]=(i,copy.deepcopy(kernel))
  before=x[i].tobytes();start=time.perf_counter_ns();out[i],info=kernel.step(ts,x[i],status[i].base_gate,bool(status[i].base_ready),status[i].base_ncorrected,h[i],nights[i]);times.append((time.perf_counter_ns()-start)/1000);assert before==x[i].tobytes();eligible[i]=info['eligible'];sparse[i]=info['sparse'];diag.append([info['rank'],info['broad_support_fraction'],info['model_id'],np.sum(info['new_sparse'])])
  if info['model_id']!=lastmodel and kernel.A is not None:
   for j,name in enumerate(names):models.append(dict(line=line,device_id=dev,marker_name=name,time_beijing=iso(ts),model_id=info['model_id'],rank=info['rank'],A1=kernel.A[j,0],A2=kernel.A[j,1] if kernel.A.shape[1]>1 else np.nan,participation1=info['participation'][0],participation2=info['participation'][1] if len(info['participation'])>1 else np.nan,sparse_excluded=bool(info['sparse'][j])))
   lastmodel=info['model_id']
 np.savez_compressed(folder/'factor.npz',out=out,eligible=eligible,sparse=sparse,diagnostics=np.array(diag),time_us=times)
 with (folder/'factor_snapshots.pkl').open('wb') as f:pickle.dump(snapshots,f)
 save_parts(pd.DataFrame(models),f'factor_models/{line}_{dev}.csv');r={'line':line,'device_id':dev,'elapsed_seconds':time.monotonic()-tick,'mean_us':np.mean(times),'P99_us':np.quantile(times,.99),'active_point_frames':int(eligible.sum()),'changed_point_frames':int((abs(out-x)>1e-6).sum()),'model_versions':kernel.model_id,'monitor_unchanged':True};print(r,flush=True);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');p.add_argument('--freeze',action='store_true');a=p.parse_args()
 if a.freeze:
  from datetime import datetime,timezone
  save_json({'version':'E-residual-factor-1','frozen_UTC':datetime.now(timezone.utc).isoformat(),'motivation':'D narrows overall range but not30/60min drift; prior residual PCA shows broad low-rank correlation. This additional mechanism estimates common slow increments and protects sparse local persistent changes.','training':'past90 full-correction samples, min60; ordinary markers only; update every30 active frames until01:30, with initial no-history bootstrap allowed; no current or future sample in the covariance used for current solve','rank_max':2,'ordinary_min':8,'valid_and_unmasked_ordinary_min_fraction':.6,'spatial_participation_min_fraction':.35,'eigenvalue_above_median_noise_multiple':1.5,'robust_frame_Huber_sigma':2.5,'local_sustained_component_mm_floor':.35,'local_sustained_sigma_multiple':4,'local_memory_minutes':200,'common_increment_RC_minutes':15,'max_correction_mm':1.5,'max_correction_increment_mm_per_minute':.1,'reference_node_role':'YJ/ZJ/YXJ/ZXJ never drive factor solve or ordinary covariance; all point gains separate, no uniform shrinkage','assumption':'most observations share broad device disturbance, actual local motion comparatively sparse; broad real common motion cannot be identified without independent truth','code_SHA256':sha(O/'scripts/residual_factor.py'),'not_a_new_physical_measurement_or_alarm_channel':True},'protocol_extension_E.json')
 rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for r in pool.map(one,[q for q in roster() if not a.focus or q['device_id'] in FOCUS]):rows.append(r)
 save(rows,'E_run_'+('focus' if a.focus else 'all')+'.csv')

if __name__=='__main__':main()
