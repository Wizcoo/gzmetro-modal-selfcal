from common import *
from features import all_features
import warnings

def correlation(a,b):
 ok=np.isfinite(a)&np.isfinite(b)
 return np.corrcoef(a[ok],b[ok])[0,1] if ok.sum()>=30 and np.std(a[ok])>1e-10 and np.std(b[ok])>1e-10 else np.nan

def main():
 diagnostic=[];quality=[];counter=[];selection=[]
 for q in roster():
  line,dev=q['line'],q['device_id'];src=load_data(line,dev);names=src['names'].tolist();t=src['t'];x=src['x'];field=np.where(np.isfinite(x),src['field'],np.nan);T=src['temperature'];d=np.load(W/line/dev/'normal.npz');base=d['base'];h,nights=clocks(t);_,res,slow,b=all_features(t,base,T);refs=[j for j,n in enumerate(names) if ref(n)];ad=pd.read_csv(O/'admission'/f'{line}_{dev}.csv');tempcols={}
  for lag in [0,15,60]:
   idx=np.searchsorted(t,t-lag*60000,side='right')-1;good=idx>=0;idx=np.maximum(0,idx);good&=t-lag*60000-t[idx]<=90000;v=T[idx].copy();v[~good]=np.nan;tempcols[lag]=v
  old=np.searchsorted(t,t-600000,side='right')-1;valid=old>=0;old=np.maximum(old,0);valid&=t-600000-t[old]<=90000;rate=(T-T[old])*6;rate[~valid]=np.nan
  for night in pd.date_range('2026-11-05','2026-11-11').strftime('%Y-%m-%d'):
   mask=(nights==night)&((h>=23+1/3)|(h<7));ids=np.flatnonzero(mask)
   if len(ids)<20:
    for name in names:quality.append(dict(line=line,device_id=dev,marker_name=name,night=night,native_frames=len(ids),valid_input_frames=0,valid_field_frames=0,status='night_missing',scope='23:20-next07:00, all markers represented'))
    continue
   for j,name in enumerate(names):
    others=[r for r in refs if r!=j];common=np.full(len(ids),np.nan)
    if len(others)>=2:
     with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);common=np.nanmedian(slow[ids][:,others],axis=1)
    row=dict(line=line,device_id=dev,marker_name=name,kind=kind(name),night=night,valid_rows=int(np.isfinite(x[ids,j]).sum()),temperature_span_C=np.nanmax(T[ids])-np.nanmin(T[ids]),residual_vs_temperature_rate_r=correlation(slow[ids,j],rate[ids]),residual_vs_other_reference_median_r=correlation(slow[ids,j],common),interpretation='association on causal10min state; not physical truth or fitting labels')
    for lag,v in tempcols.items():row[f'residual_vs_temperature_lag{lag}min_r']=correlation(slow[ids,j],v[ids])
    for method in ['A_thermal','C_reference']:
     z=ad[ad.night.eq(night)&ad.marker.eq(name)&ad.method.eq(method)]
     if len(z):row[method+'_past_validation_R2']=z.past_R2.iloc[0] if 'past_R2' in z else np.nan;row[method+'_admitted']=bool(z.admitted.iloc[0])
    diagnostic.append(row);quality.append(dict(line=line,device_id=dev,marker_name=name,night=night,native_frames=len(ids),valid_input_frames=int(np.isfinite(x[ids,j]).sum()),valid_field_frames=int(np.isfinite(field[ids,j]).sum()),status='available' if np.isfinite(x[ids,j]).sum()>=20 else 'insufficient_valid_observations',scope='23:20-next07:00, all markers represented'))
  if line=='right' and dev in ['780639173835','780639376393']:
   date='2026-11-06';bs=(nights==date)&(h>=22)&(h<23);ms=(nights==date)&((h>=23+1/3)|(h<7));bb=np.nanmean(x[bs][:,refs],axis=0)
   with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);rr=np.nanmedian(field[ms][:,refs]-bb,axis=1)
   old=field[ms];new=old-.35*rr[:,None];before=np.nanquantile(old,.95,axis=0)-np.nanquantile(old,.05,axis=0);after=np.nanquantile(new,.95,axis=0)-np.nanquantile(new,.05,axis=0)
   for j,n in enumerate(names):counter.append(dict(device_id=dev,marker_name=n,kind=kind(n),night=date,baseline='database stored_calX observation, not cold B0',before_P95_P05_mm=before[j],after_uniform35_P95_P05_mm=after[j],difference_mm=after[j]-before[j],formula='field-.35*median(field_reference-22to23 raw_reference_mean)',unit='mm'))
 save_parts(pd.DataFrame(diagnostic),'thermal_reference_diagnostics.csv');save(pd.DataFrame(quality),'marker_night_coverage.csv');save(pd.DataFrame(counter),'uniform35_counterexample.csv')
 c=pd.DataFrame(counter);print(c.groupby('device_id')[['before_P95_P05_mm','after_uniform35_P95_P05_mm']].median())
 save_json({'main_candidate':'D_L1trend','second_expanded':'B_event','A_and_C_also_expanded':True,'selection_evidence':'pilot/ABC_initial_comparison.csv, final focused comparison_focus.csv; D curved-trend model improves whole-window range beyond W3; B provides event-conservative comparison. No30-50pct parameter grid search.','D_W3_is_ablation_not_new_mechanism':True,'all_marker_visual_candidate':'D_L1trend','original_monitor_and_alarm_unchanged':True},'expansion_decision.json')

if __name__=='__main__':main()
