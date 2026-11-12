from common import *
from l1_cpp import L1TrendCpp
import concurrent.futures

def one(q):
 line,dev=q['line'],q['device_id'];f=W/line/dev;src=load_data(line,dev);n=np.load(f/'normal.npz');d=np.load(f/'final_candidates.npz')['out'][:,:,3];base=n['base'];t=src['t'];h,night=clocks(t);status=pd.read_csv(f/'normal_frames.csv');g=np.where(status.base_ready.eq(1)&status.base_ncorrected.gt(0)&((h>=23)|(h<7+1/3)),np.clip(status.base_gate,0,1),0.);k=L1TrendCpp(base.shape[1]);e=np.empty_like(base)
 for i,ts in enumerate(t):full,_=k.step(ts,base[i],1,True,len(src['names']),3);e[i]=full-base[i]
 assert np.allclose(d,base+g[:,None]*e,rtol=0,atol=1e-10,equal_nan=True)
 old=np.r_[0,np.arange(len(t)-1)];release=(g-g[old])[:,None]*e[old];dynamic=g[:,None]*(e-e[old]);delta=d-d[old];b=base-base[old];good=np.r_[False,(np.diff(t)>0)&(np.diff(t)<=90000)];err=delta-b-release-dynamic;assert np.nanmax(abs(err[good]))<1e-10
 rows=[]
 for date in sorted(set(night)):
  for label,mask in [('morning',(night==date)&(h>=6+50/60)&(h<7+40/60)),('night_start',(night==date)&(h>=22+40/60)&(h<23+40/60))]:
   ids=np.flatnonzero(mask&good)
   if not len(ids):continue
   for j,name in enumerate(src['names']):
    valid=ids[np.isfinite(release[ids,j])&np.isfinite(dynamic[ids,j])]
    if not len(valid):continue
    i=valid[int(np.argmax(abs(release[valid,j])))];rows.append(dict(line=line,device_id=dev,marker_name=name,kind=kind(name),night=date,transition=label,gate_change_term_abs_max_mm=abs(release[i,j]),gate_change_term_signed_mm=release[i,j],peak_gate_term_time_beijing=iso(t[i]),base_step_at_peak_mm=b[i,j],filter_change_term_at_peak_mm=dynamic[i,j],candidate_step_at_peak_mm=delta[i,j],gate_before=g[old[i]],gate_after=g[i],candidate_abs_step_max_in_window_mm=np.nanmax(abs(delta[valid,j])),B0_abs_step_max_in_window_mm=np.nanmax(abs(b[valid,j])),formula='delta(candidate)=delta(B0)+(g_t-g_prev)*e_prev+g_t*(e_t-e_prev); e=full_D-B0'))
 print('BOUNDARY',line,dev,flush=True);return rows
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=[r for batch in pool.map(one,roster()) for r in batch]
 save_parts(pd.DataFrame(rows),'transition_decomposition.csv');save_json({'passed':True,'formula_residual_abs_max_tolerance_mm':1e-10,'original_D_reconstructed':True,'gate_term_definition':'effect of changing blend gate with previous full correction held fixed; distinct from dynamic filter and original step'},'transition_decomposition_validation.json')
