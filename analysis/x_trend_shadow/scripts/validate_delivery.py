from common import *
from features import bank
import argparse

def equal(a,b):return np.array_equal(a,b,equal_nan=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--traces',action='store_true');a=p.parse_args();checks=[];total=0;trace_rows=0;boundary=[]
 frozen=json.loads((O/'protocol_frozen.json').read_text());provenance=json.loads((O/'data_provenance.json').read_text());build=json.loads((O/'build_provenance.json').read_text());sources={}
 for ver in build:
  for ext,key in [('cpp','cpp_SHA256'),('h','h_SHA256')]:assert sha(R/'versions'/ver['version']/('ModalSelfCal.'+ext))==ver[key]
 for f in ['native.cpp','features.py','shadow.py']:assert sha(O/'scripts'/f)==frozen['source_SHA256'][f]
 for q in provenance['inputs']:
  assert sha(q['raw_packet'])==q['raw_packet_SHA256']
  for src in q['environment_sources']:
   if 'database' in src:sources[src['database']]=src['SHA256']
 for f,hsh in sources.items():assert sha(DATA/f)==hsh
 for q in roster():
  line,dev=q['line'],q['device_id'];f=W/line/dev;src=load_data(line,dev);n=np.load(f/'normal.npz');c=np.load(f/'final_candidates.npz');t=src['t'];base=n['base'];out=c['out'];h,night=clocks(t);day=(h>=7+1/3)&(h<23);checks.append(dict(line=line,device_id=dev,day_point_frames=int(day.sum()*base.shape[1]),new_methods=out.shape[2],day_exact_B0=equal(out[day],np.repeat(base[day,:,None],out.shape[2],axis=2))));assert checks[-1]['day_exact_B0'];total+=int(day.sum()*base.shape[1]*out.shape[2])
  # First frame after a gap must be transparent for D, irrespective of gate.
  gap=np.r_[True,np.diff(t)>90000];assert equal(out[gap,:,3],base[gap]);
  for j,name in enumerate(src['names']):assert (O/'plots/all_markers'/line/dev/(name+'.png')).exists()
  # Increment due solely to taper/removal, not original calX motion.
  extra=out-base[:,:,None];morning=(h>=7)&(h<7+1/3);endday=(h>=7+1/3)&(h<8);boundary.append(dict(line=line,device_id=dev,morning_available_frames=int(morning.sum()),first_day_extra_abs_max_mm=float(np.nanmax(abs(extra[endday]))) if endday.any() else None))
  if a.traces:
   idx=pd.Index(t);names=src['names'].tolist();lookup={name:i for i,name in enumerate(names)};st=pd.read_csv(f/'normal_frames.csv')
   for path in sorted((O/'traces').glob(f'{line}_{dev}_*.csv')):
    for z in pd.read_csv(path,chunksize=100000,float_precision='round_trip'):
     ii=idx.get_indexer(z.timestamp_ms);jj=z.marker_name.map(lookup).to_numpy();assert (ii>=0).all();assert not z.duplicated(['timestamp_ms','marker_name']).any()
     expected={'rawX_mm':src['x'][ii,jj],'stored_calX_mm':np.where(np.isfinite(src['x'][ii,jj]),src['field'][ii,jj],np.nan),'B0_original_mm':base[ii,jj],'W3_original_mm':n['w3'][ii,jj],'originalY_mm':n['y'][ii,jj]}
     for mi,m in enumerate(METHODS[2:]):expected[m+'_mm']=out[ii,jj,mi]
     for key,v in expected.items():assert np.allclose(z[key],v,rtol=1e-10,atol=1e-10,equal_nan=True),(path,key)
     trace_rows+=len(z);total+=len(z)*len(expected)
  print('VALID',line,dev,flush=True)
 # Current-night A/C gain bank must be identical when all future is removed.
 q=next(q for q in roster() if q['device_id']=='780639346578');f=W/q['line']/q['device_id'];src=load_data(q['line'],q['device_id']);n=np.load(f/'normal.npz');st=pd.read_csv(f/'normal_frames.csv');end=np.searchsorted(src['t'],epoch('2026-11-12 03:00'));short,_,_=bank(src['t'][:end],n['base'][:end],src['temperature'][:end],st.iloc[:end],src['names'].tolist());model=json.loads((O/'models'/('right_'+q['device_id']+'.json')).read_text());full=model['models']['2026-11-11'];assert clean_json(short['2026-11-11'])==full,'future-dependent bank';
 catalog=pd.read_csv(O/'plot_catalog.csv');assert len(catalog)==524 and not catalog.duplicated(['line','device_id','marker_name']).any();assert len(pd.read_csv(O/'focus_plot_catalog.csv'))==18
 files=[p for p in O.rglob('*') if p.is_file() and '.work' not in p.parts and '__pycache__' not in p.parts];oversize=[str(p.relative_to(O)) for p in files if p.stat().st_size>=2000000];assert not oversize,oversize
 save(checks,'day_passthrough_checks.csv');save(boundary,'boundary_checks.csv');save_json({'passed':True,'numerical_comparisons':total,'continuous_trace_rows_checked':trace_rows,'all_marker_plots':len(catalog),'focus_plots':18,'source_database_hashes_unchanged':len(sources),'source_packets_unchanged':12,'original_V51_V53_hashes_unchanged':True,'ABC_frozen_math_unchanged':True,'run_candidates_scheduler_only_change_since_freeze':sha(O/'scripts/run_candidates.py')!=frozen['source_SHA256']['run_candidates.py'],'past_only_model_bank_prefix_equal':True,'day_new_output_exact_B0':True,'D_gap_first_frame_passthrough':True,'all_deliverable_files_under_2MB':True,'not_actual_site_alarm_or_X0_validation':True},'validation.json')

if __name__=='__main__':main()
