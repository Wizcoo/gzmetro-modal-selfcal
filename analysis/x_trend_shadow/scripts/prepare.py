from common import *
import sqlite3,argparse

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--exported-environment',action='store_true',help='Reuse committed causal environment alignment, without opening any SQLite');args=parser.parse_args()
 if args.exported_environment:
  for row in roster():
   line,dev=row['line'],row['device_id'];p=OLD/f'validation_{line}_{dev}.bin';assert sha(p)==row['raw_packet_SHA256'];names,d=packet_read(p);z=pd.read_csv(O/'environment'/f'{line}_{dev}.csv');assert np.array_equal(z.timestamp,d['t']);dst=W/line/dev;dst.mkdir(parents=True,exist_ok=True);np.savez_compressed(dst/'input.npz',t=d['t'],names=np.array(names),x=d['x'],y=d['y'],field=d['field'],temperature=z.temp.to_numpy(float),humidity=z.humidity.to_numpy(float),env_t=z.env_timestamp.to_numpy(float))
  return
 source=Path(os.environ.get('XS_PR4_REPORT',BASE/'x_preprocess_work_20261112/analysis/right_x_preprocess'));identity=pd.read_csv(source/'input_identity_validation.csv',dtype={'device_id':str});manifest=json.loads((source/'new_source_manifest.json').read_text(encoding='utf-8'));audits=[]
 for row in identity.to_dict('records'):
  line,dev=row['line'],row['device_id'];dst=W/line/dev;dst.mkdir(parents=True,exist_ok=True);p=OLD/f'validation_{line}_{dev}.bin';assert sha(p)==row['input_SHA256'];names,d=packet_read(p);t=d['t'];pieces=[];sources=[]
  if line=='right':
   old=Path(os.environ.get('XS_OLD_ENV_CACHE',BASE/'right_x_work_20261111/cache'))/f'EnvData_{dev}.pkl'
   if old.exists():
    z=pd.read_pickle(old);pieces.append(z);sources.append({'cache':str(old),'SHA256':sha(old)})
  for m in manifest:
   if m['line']!=line:continue
   p=DATA/m['source_file'];assert sha(p)==m['SHA256'];db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
   tab='EnvData_'+dev
   if db.execute('select 1 from sqlite_master where type=\'table\' and name=?',(tab,)).fetchone():
    cur=db.execute('select rowid as env_rowid,ts,Done,temp,innerTemp,innerLensTemp,humidity from "'+tab+'" where ts>=? and ts<=?',(int(t[0])-7200000,int(t[-1])));columns=[r[0] for r in cur.description];values=[];error=''
    try:
     while True:
      v=cur.fetchone()
      if v is None:break
      values.append(v)
    except sqlite3.DatabaseError as e:error=str(e)
    z=pd.DataFrame(values,columns=columns);pieces.append(z);sources.append({'database':m['source_file'],'SHA256':m['SHA256'],'rows':len(z),'read_error':error})
   db.close()
  e=pd.concat(pieces,ignore_index=True);e=e[e.Done.eq(1)&np.isfinite(pd.to_numeric(e.temp,errors='coerce'))].copy();e['ts']=pd.to_numeric(e.ts).round().astype('int64');payload=['ts','temp','humidity'];e=e.drop_duplicates(payload);conflict=e.duplicated('ts',keep=False);bad=int(conflict.sum());e=e[~conflict].sort_values('ts');e['env_timestamp']=e.ts
  aligned=pd.merge_asof(pd.DataFrame({'timestamp':t}),e[['env_timestamp','temp','humidity']],left_on='timestamp',right_on='env_timestamp',direction='backward',tolerance=90000)
  np.savez_compressed(dst/'input.npz',t=t,names=np.array(names),x=d['x'],y=d['y'],field=d['field'],temperature=aligned.temp.to_numpy(float),humidity=aligned.humidity.to_numpy(float),env_t=aligned.env_timestamp.to_numpy(float))
  save(aligned.assign(line=line,device_id=dev),'environment/'+line+'_'+dev+'.csv')
  audits.append({'line':line,'device_id':dev,'version':'V51' if line=='right' else 'V53','frames':len(t),'points':len(names),'start_beijing':iso(t[0]),'end_beijing':iso(t[-1]),'raw_packet':str(OLD/f'validation_{line}_{dev}.bin'),'raw_packet_SHA256':row['input_SHA256'],'env_valid_frames':int(aligned.temp.notna().sum()),'env_conflicting_rows_excluded':bad,'max_gap_minutes':row['max_gap_minutes'],'environment_sources':sources});print(line,dev,len(t),'environment',aligned.temp.notna().sum(),flush=True)
 save(pd.DataFrame([{k:v for k,v in a.items() if k!='environment_sources'} for a in audits]),'input_identity.csv');save_json({'inputs':audits,'raw_source_manifest':manifest,'no_database_write':True,'environment_alignment':'Done=1, conflict timestamps excluded; backward-only, <=90s; no interpolation','prior_inputs':'PR4 full11/05..11/12 surviving original timestamps and masks; damaged tails and gaps retained'},'data_provenance.json')

if __name__=='__main__':main()
