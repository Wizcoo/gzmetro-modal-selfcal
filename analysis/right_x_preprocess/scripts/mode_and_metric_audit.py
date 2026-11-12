from dataio import *

def main():
 records=[];checks=0
 for e in pd.read_csv(O/'event_index.csv',dtype={'device_id':str}).to_dict('records'):
  line,dev=e['line'],e['device_id'];names,methods,fields,d=load(W/'validation'/f'clean_{line}_{dev}.bin');di={n:i for i,n in enumerate(fields)};idx=names.index(e['marker_name']);st=epoch(e['date']+' 23:20');mask=(d['ts']>=st)&(d['ts']<st+460*60000);birth=pd.read_csv(W/'validation'/f'birth_{line}_{dev}.csv');nid=(pd.Timestamp(e['date'])-pd.Timestamp('1970-01-01')).days
  for mi,method in enumerate(methods):
   b=birth[birth.method.eq(method)&birth.night_id.eq(nid)&birth.marker.eq(e['marker_name'])]
   if len(b)!=1:continue
   b=b.iloc[0];loadings=b[['A1','A2','A3']].to_numpy(float)
   for j in np.flatnonzero(mask):
    z=d['methods']['diag'][j,mi];r={f:float(z[i]) for i,f in enumerate(fields)};r.update(event_id=e['event_id'],line=line,device_id=dev,marker_name=e['marker_name'],timestamp_ms=int(d['ts'][j]),time_beijing=iso(d['ts'][j]),method=method,model_night_id=nid,point_use=int(b.use),point_learn=int(b.learn),cbar_mm=b.cbar_mm)
    vv=z[[di['v1'],di['v2'],di['v3']]]
    for k in range(3):r[f'A{k+1}']=loadings[k];r[f'gate_A{k+1}_v{k+1}_mm']=z[di['gate']]*loadings[k]*vv[k]
    expected=z[di['gate']]*(loadings@vv-b.cbar_mm);actual=d['methods']['pre'][j,mi,idx]-d['methods']['cal'][j,mi,idx];r['common_correction_mm']=actual;r['gate_cbar_offset_mm']=-z[di['gate']]*b.cbar_mm
    if b.use and np.isfinite(actual) and z[di['n_corrected']]>0:assert abs(expected-actual)<1e-10;checks+=1
    records.append(r)
  # Independent brute-force rolling median and adjacent quantile check.
  active=mask&(d['methods']['diag'][:,0,di['gate']]>0)&(d['methods']['diag'][:,0,di['n_corrected']]>0)
  for mi,method in enumerate(methods):
   v=d['methods']['cal'][:,mi,idx];good=active&np.isfinite(d['raw'][:,idx])&np.isfinite(v);t=d['ts'][good];x=v[good];smooth=[];runstart=0
   for j in range(len(t)):
    if j and t[j]-t[j-1]>90000:runstart=j
    a=x[runstart:j+1][t[runstart:j+1]>t[j]-300000];smooth.append(np.median(a) if len(a)>=3 else np.nan)
   lf=np.nanquantile(smooth,.95)-np.nanquantile(smooth,.05);adj=np.diff(t);step=np.quantile(abs(np.diff(x)[(adj>=30000)&(adj<=90000)]),.99)
   if method!='B0_raw':
    target=pd.read_csv(O/'heldout_key_AB.csv',dtype={'device_id':str});r=target[target.line.eq(line)&target.device_id.eq(dev)&target.marker_name.eq(e['marker_name'])&target.date.eq(e['date'])&target.method.eq(method)].iloc[0];assert abs(lf-r.LF_Q95_Q05_mm)<1e-10 and abs(step-r.step_abs_P99_mm)<1e-10;checks+=2
 write_parts(pd.DataFrame(records),'mode_trace_windows.csv');(O/'mode_metric_validation.json').write_text(json.dumps({'passed':True,'independent_checks':checks,'formula':'pre-cal = gate*(A1*v1+A2*v2+A3*v3-cbar); mode axes may rotate between branches, so coefficient-only cross-branch comparison is not physical.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS',checks)

if __name__=='__main__':main()
