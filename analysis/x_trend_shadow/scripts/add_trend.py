from l1_cpp import L1TrendCpp as L1Trend
from common import *
import argparse,concurrent.futures,time

def job(q):
 line,dev=q['line'],q['device_id'];folder=W/line/dev;src=load_data(line,dev);d=np.load(folder/'normal.npz');old=np.load(folder/'candidates.npz');t=src['t'];base=d['base'];w3=d['w3'];status=pd.read_csv(folder/'normal_frames.csv');h,_=clocks(t);a=L1Trend(base.shape[1]);b=L1Trend(base.shape[1]);out=np.full((len(t),base.shape[1],2),np.nan);elig=np.zeros_like(out,bool);cost=[];diag=[];tick=time.monotonic()
 for i,ts in enumerate(t):
  start=time.perf_counter_ns();out[i,:,0],qa=a.step(ts,base[i],status.base_gate.iloc[i],bool(status.base_ready.iloc[i]),status.base_ncorrected.iloc[i],h[i]);inner,qb=b.step(ts,w3[i],status.w3_gate.iloc[i],bool(status.w3_ready.iloc[i]),status.w3_ncorrected.iloc[i],h[i]);out[i,:,1]=base[i]+qa['gate']*(inner-base[i]);cost.append((time.perf_counter_ns()-start)/1000);elig[i,:,0]=qa['eligible'];elig[i,:,1]=qb['eligible']&(qa['gate']>0);diag.append([qa['primal_mm'],qa['nonconverged_points'],qb['primal_mm'],qb['nonconverged_points']])
 np.savez_compressed(folder/'extended_candidates.npz',out=np.concatenate([old['out'],out],axis=2),eligible=np.concatenate([old['eligible'],elig],axis=2),mode=old['mode'],event=old['event'],diagnostics=old['diagnostics'],time_us=old['time_us'],D_time_us=np.array(cost),D_diagnostics=np.array(diag),night_blend_version=1);r={'line':line,'device_id':dev,'elapsed_seconds':time.monotonic()-tick,'two_L1_filters_mean_us':np.mean(cost),'two_L1_filters_P99_us':np.quantile(cost,.99),'numerical_endpoint_error_bound_max_mm':np.max(np.array(diag)[:,[0,2]]),'uncertified_point_frames':np.sum(np.array(diag)[:,[1,3]]),'solver':'D-L1-2 certified dual C++'};print(r,flush=True);return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');p.add_argument('--freeze',action='store_true');p.add_argument('--missing-only',action='store_true');a=p.parse_args()
 if a.freeze and not (O/'protocol_extension_D.json').exists():
  from datetime import datetime,timezone
  save_json({'frozen_UTC':datetime.now(timezone.utc).isoformat(),'version':'D-L1-1','reason':'ABC pilot did not reliably outperform W3; additional mechanism uses finite-memory curvature sparsity, not another percentage shrinkage or EMA','objective':'.5*||y-l||²+lambda*||D2 l||1; only current endpoint emitted','past_current_window':15,'lambda':'MAD(second differences)/sqrt6 * sqrt(12log(window)), floor sigma .01mm','rho':2,'ADMM_max_iterations':50,'ADMM_convergence_mm':1e-5,'reported_nonconvergence_threshold_mm':1e-4,'no_goal_range_parameter_search':True,'D_input':'B0 calX','D_W3_ablation_input':'independent W3 calX; not a distinct mechanism','code_SHA256':sha(O/'scripts/l1trend.py'),'ABC_parameters_unchanged':True},'protocol_extension_D.json')
 rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for r in pool.map(job,[q for q in roster() if (not a.focus or q['device_id'] in FOCUS) and (not a.missing_only or not (W/q['line']/q['device_id']/'extended_candidates.npz').exists())]):rows.append(r)
 save(rows,'D_run_'+('missing' if a.missing_only else 'focus' if a.focus else 'all')+'.csv')

if __name__=='__main__':main()
