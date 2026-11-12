from dataio import *
import subprocess

def equal(a,b):return np.array_equal(a,b,equal_nan=True)
def main():
 checks=[];gaps=[];diags=[];count=0
 def check(name,ok,**info):
  assert bool(ok),(name,info);checks.append({'check':name,'passed':True,**info})
 lock=json.loads((O/'implementation_freeze.json').read_text())
 for name,h in lock['algorithm_SHA256'].items():check('locked_'+name,sha(O/'scripts'/name)==h)
 for suffix in ['cpp','h']:check('V51_'+suffix,sha(R/'versions/V51'/f'ModalSelfCal.{suffix}')==lock[f'original_V51_{suffix}_SHA256'])
 for ver in ['V51','V53']:
  for suffix in ['cpp','h']:
   f=f'versions/{ver}/ModalSelfCal.{suffix}';blob=subprocess.check_output(['git','show','4ce0ac6c8a99674ffebc0f0f8af699c575da54aa:'+f],cwd=R)
   check(ver+'_original_git_bytes_'+suffix,sha(R/f)==hashlib.sha256(blob).hexdigest())
 p=json.loads((O/'protocol_frozen.json').read_text());h=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();check('frozen_protocol_semantics',h==json.loads((O/'freeze_record.json').read_text())['semantic_protocol_SHA256'])
 for source in json.loads((O/'new_source_manifest.json').read_text()):check('source_readonly_'+source['source_file'],sha(DATA/source['source_file'])==source['SHA256'])
 for stage in ['old','validation']:
  inputs=pd.read_csv(O/f'input_identity_{stage}.csv',dtype={'device_id':str})
  for q in inputs.to_dict('records'):
   line,dev=q['line'],q['device_id'];names,methods,fields,d=load(W/stage/f'clean_{line}_{dev}.bin');ix={f:i for i,f in enumerate(fields)};ts=d['ts'];dd=d['methods']['diag'];count+=len(ts)*len(names)*len(methods)
   check(f'{stage}_{dev}_input_hash',sha(W/f'{stage}_{line}_{dev}.bin')==q['input_SHA256'])
   raw=pd.read_pickle(W/f'{stage}_{line}_{dev}.pkl');pivot=raw.pivot(index='timestamp',columns='markerName',values=['x','y','RoiCalState']);x=pivot.x.reindex(columns=names).to_numpy(float,copy=True);y=pivot.y.reindex(columns=names).to_numpy(float,copy=True);valid=pivot.RoiCalState.reindex(columns=names).to_numpy()==1;x[~valid|~np.isfinite(x)]=np.nan;y[~valid|~np.isfinite(y)]=np.nan
   check(f'{stage}_{dev}_source_rawY_timestamps',equal(x,d['raw']) and equal(y,d['yinput']) and equal(ts,pivot.index.to_numpy()))
   check(f'{stage}_{dev}_B0_pre_raw',equal(d['methods']['pre'][:,0],d['raw']))
   check(f'{stage}_{dev}_validity',all(equal(np.isfinite(d['methods']['pre'][:,m]),np.isfinite(d['raw'])) for m in range(len(methods))))
   check(f'{stage}_{dev}_Y_diag',np.all(dd[:,:,ix['Y_mismatch_count']]==0))
   check(f'{stage}_{dev}_projection',np.max(dd[:,-1,ix['projection_leakage']])<1e-9,maximum=float(np.max(dd[:,-1,ix['projection_leakage']])))
   for m in range(len(methods)):
    a=d['raw']-d['methods']['pre'][:,m];b=d['methods']['pre'][:,m]-d['methods']['cal'][:,m];c=d['raw']-d['methods']['cal'][:,m];z=np.isfinite(c);check(f'{stage}_{dev}_{m}_correction_accounting',np.max(abs((a+b-c)[z]),initial=0)<1e-12)
   for a,b in zip(ts[:-1][np.diff(ts)>90000],ts[1:][np.diff(ts)>90000]):gaps.append({'stage':stage,'line':line,'device_id':dev,'last_before_gap_beijing':iso(a),'first_after_gap_beijing':iso(b),'gap_minutes':(b-a)/60000})
   if stage=='old':
    oldnames,_,_,old=load_pr3(OLD/'final'/f'normal_{dev}.bin');check(dev+'_PR3_timestamp_names',oldnames==names and equal(ts,old['ts']));check(dev+'_PR3_B0_exact',equal(d['methods']['cal'][:,0],old['methods']['x'][:,0]));check(dev+'_PR3_Y_exact',equal(d['youtput'],old['y']));check(dev+'_N1_normal_identity',equal(d['methods']['pre'][:,1],d['raw']))
   elif line=='right':
    on,_,_,od=load(W/'old'/f'clean_right_{dev}.bin');check(dev+'_unchanged_old_prefix',names==on and equal(d['raw'][:len(od)],od['raw']) and equal(d['methods']['cal'][:len(od)],od['methods']['cal']) and equal(d['methods']['pre'][:len(od)],od['methods']['pre']))
   for day,phase,st,en in windows(ts,stage):
    mask=(ts>=st)&(ts<en);local=np.flatnonzero(mask);possible=int((en-st)/60000);active=mask&(dd[:,0,ix['gate']]>0)&(dd[:,0,ix['n_corrected']]>0)
    diags.append({'stage':stage,'line':line,'device_id':dev,'date':day,'phase':phase,'expected_nominal_minute_frames':possible,'native_frames':len(local),'B0_active_frames':int(active.sum()),'first_beijing':iso(ts[local[0]]) if len(local) else '', 'last_beijing':iso(ts[local[-1]]) if len(local) else '', 'coverage_fraction_nominal':len(local)/possible,'note':'native timestamps, no fill; midnight-to07 belongs to preceding date night'})
   # Every output (noise and known-waveform) was guarded in C++ at every
   # full-point Y value. Independently recheck all persisted key Y values.
   idx=pd.Index(ts)
   for path in (W/stage).glob(f'*_{line}_{dev}.bin'):
    if path.name.startswith('clean_'):continue
    kn,_,ff,z=load(path);j=idx.get_indexer(z['ts']);cols=[names.index(n) for n in kn];check(path.stem+'_Y_persisted',equal(z['yinput'],d['yinput'][j][:,cols]) and equal(z['youtput'],d['youtput'][j][:,cols]) and np.all(z['methods']['diag'][:,:,ff.index('Y_mismatch_count')]==0))
 write(pd.DataFrame(gaps),'time_gaps.csv');write(pd.DataFrame(diags),'time_coverage.csv')
 result={'passed':True,'checks':len(checks),'clean_point_method_frames':count,'checks_detail':checks,'Y_test':'C++ memcmp every full-point method, all3 complete noisy histories and all waveform suffixes; Python independent check every persisted Y','missing_tails':'See new_source_manifest errors; complete damaged tails are unknowable; only surviving accessible observations used.'}
 (O/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS',len(checks),'checks',count,'clean point-method frames')

if __name__=='__main__':main()
