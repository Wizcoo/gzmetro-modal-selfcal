from common import *
import argparse,sqlite3

COLS=['markerIndex','markerName','markerPos','RoiCalState','scale','centerX','centerY','x','y','calX','calY','timestamp']
def packet(line,dev,d,tag):
 keys=['timestamp','markerName','markerIndex','markerPos'];payload=[c for c in COLS if c in d]
 before=len(d);d=d.drop_duplicates(payload,keep='first');amb=d.duplicated(keys,keep=False);conflicts=int(amb.sum());d['ambiguous']=amb
 # Do not choose a convenient conflicting observation. Keep audit records,
 # and exclude its complete business key from the executable input.
 d=d[~amb].sort_values('timestamp',kind='stable').copy();d.to_pickle(W/f'{tag}_{line}_{dev}.pkl')
 names=sorted(d.markerName.unique());p=d.pivot(index='timestamp',columns='markerName',values=['x','y','calX','RoiCalState']);t=p.index.to_numpy();x=p.x.reindex(columns=names).to_numpy(float,copy=True);y=p.y.reindex(columns=names).to_numpy(float,copy=True);cal=p.calX.reindex(columns=names).to_numpy(float,copy=True);valid=p.RoiCalState.reindex(columns=names).to_numpy()==1;x[~valid|~np.isfinite(x)]=np.nan;y[~valid|~np.isfinite(y)]=np.nan
 seed=int(hashlib.sha256((line+dev).encode()).hexdigest()[:12],16)+20261112;noise=np.random.default_rng(seed).standard_normal(x.shape)
 path=W/f'{tag}_{line}_{dev}.bin'
 with path.open('wb') as f:
  f.write(struct.pack('<I',len(names)))
  for n in names:b=n.encode();f.write(struct.pack('<I',len(b)));f.write(b)
  f.write(struct.pack('<I',len(t)))
  for j,ts in enumerate(t):f.write(struct.pack('<q',ts));f.write(x[j].astype('<f8').tobytes());f.write(y[j].astype('<f8').tobytes());f.write(cal[j].astype('<f8').tobytes());f.write(noise[j].astype('<f8').tobytes())
 gaps=np.diff(t);return {'line':line,'device_id':dev,'tag':tag,'points':len(names),'frames':len(t),'source_rows':before,'exact_duplicates_removed':before-len(d)-conflicts,'conflict_rows_excluded':conflicts,'input_SHA256':sha(path),'start_beijing':iso(t[0]),'end_beijing':iso(t[-1]),'max_gap_minutes':gaps.max()/60000 if len(gaps) else 0,'noise_seed':seed,'order':'lexicographic point names embedded; original real timestamps; no interpolation'}

def main():
 a=argparse.ArgumentParser();a.add_argument('--stage',choices=['old','validation'],required=True);a=a.parse_args();freeze=json.loads((O/'freeze_record.json').read_text());proto=json.loads((O/'protocol_frozen.json').read_text(encoding='utf-8'));semantic=hashlib.sha256(json.dumps(proto,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();assert semantic==freeze.get('semantic_protocol_SHA256',semantic) and (sha(O/'protocol_frozen.json')==freeze['protocol_SHA256'] or 'semantic_protocol_SHA256' in freeze);records=[];sources=[]
 if a.stage=='old':
  for p in sorted(CACHE.glob('Marker_780*.pkl')):
   d=pd.read_pickle(p);assert not d.ambiguous_business_key.any();records.append(packet('right',p.stem.split('_')[1],d,'old'))
 else:
  implementation=json.loads((O/'implementation_freeze.json').read_text());assert implementation['before_validation_signal_read']
  for file,h in implementation['algorithm_SHA256'].items():assert sha(O/'scripts'/file)==h
  # Right uses the exact old frozen observations, then new source volumes.
  # Left is an independent transfer stream; damaged volumes are read-only,
  # surviving rows and all gaps are reported rather than synthesized.
  for line,folder,prefix,ids in [('right','右线','1793052366195',[8,9,10]),('left','左线/NewDevice','1793507670403',[3,4,5,6,7])]:
   chunks={}
   if line=='right':
    for p in sorted(CACHE.glob('Marker_780*.pkl')):chunks[p.stem.split('_')[1]]=[pd.read_pickle(p)[COLS+['source_db','_source_rowid']].copy()]
   for idx in ids:
    p=DATA/folder/f'{prefix}_DataBaseFile_{idx}.db';stat=p.stat();assert not Path(str(p)+'-wal').exists();source={'line':line,'source_file':str(p.relative_to(DATA)).replace('\\','/'),'bytes':stat.st_size,'SHA256':sha(p),'read_mode':'ro immutable, no repair','tables':[]}
    c=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);tables=[r[0] for r in c.execute("select name from sqlite_master where type='table' and name glob 'Marker_780*'")]
    for table in sorted(tables):
     start=epoch('2026-11-07 15:00')+1 if line=='right' else epoch('2026-11-05 00:00');q='select rowid as _source_rowid,'+','.join('"'+k+'"' for k in COLS)+' from "'+table+'" where timestamp>=? and timestamp<=?';parts=[];err=''
     try:
      cur=c.execute(q,(start,epoch('2026-11-12 12:00')));cols=[r[0] for r in cur.description]
      while True:
       rr=cur.fetchmany(5000)
       if not rr:break
       parts.append(pd.DataFrame.from_records(rr,columns=cols))
     except sqlite3.DatabaseError as e:
      err=str(e);last=int(parts[-1]._source_rowid.max()) if parts else 0;extra=[];seek_errors=0
      # fetchmany discards its unfinished Python batch on SQLite errors.
      # Re-read only the uncommitted suffix row-by-row, without repairs.
      suffix='select rowid as _source_rowid,'+','.join('"'+k+'"' for k in COLS)+' from "'+table+'" NOT INDEXED where rowid>? and timestamp>=? and timestamp<=? order by rowid'
      try:
       cur=c.execute(suffix,(last,start,epoch('2026-11-12 12:00')))
       while True:
        r=cur.fetchone()
        if r is None:break
        extra.append(r);last=int(r[0])
      except sqlite3.DatabaseError:
       # If the rightmost rowid is readable, point seeks can recover later
       # valid records past a damaged leaf. Unknown tails remain explicit.
       try:
        upper=c.execute('select max(rowid) from "'+table+'"').fetchone()[0]
        if upper is not None and int(upper)-last<=20000:
         exact='select rowid as _source_rowid,'+','.join('"'+k+'"' for k in COLS)+' from "'+table+'" NOT INDEXED where rowid=? and timestamp>=? and timestamp<=?'
         for rid in range(last+1,int(upper)+1):
          try:
           r=c.execute(exact,(rid,start,epoch('2026-11-12 12:00'))).fetchone()
           if r is not None:extra.append(r)
          except sqlite3.DatabaseError:seek_errors+=1
        else:err+='; unbounded_or_large_tail_not_invented'
       except sqlite3.DatabaseError:err+='; max_rowid_unreadable_tail_unknown'
      if extra:parts.append(pd.DataFrame.from_records(extra,columns=cols))
      err+=f'; rowwise_salvaged={len(extra)}; unreadable_rowid_seeks={seek_errors}'
     d=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=['_source_rowid']+COLS);d['source_db']=p.stem;chunks.setdefault(table.split('_')[1],[]).append(d);source['tables'].append({'table':table,'read_rows':len(d),'error':err,'first_ms':int(d.timestamp.min()) if len(d) else None,'last_ms':int(d.timestamp.max()) if len(d) else None})
    c.close();assert p.stat().st_size==stat.st_size and p.stat().st_mtime_ns==stat.st_mtime_ns,'Source changed during read; do not mix snapshots';sources.append(source);print(line,p.name,'read',sum(t['read_rows'] for t in source['tables']),'errors',[(t['table'],t['error']) for t in source['tables'] if t['error']],flush=True)
   for dev,parts in chunks.items():records.append(packet(line,dev,pd.concat(parts,ignore_index=True),'validation'))
  (O/'new_source_manifest.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 write(pd.DataFrame(records),f'input_identity_{a.stage}.csv');print(pd.DataFrame(records)[['line','device_id','frames','points','start_beijing','end_beijing','max_gap_minutes','conflict_rows_excluded']].to_string(index=False))
if __name__=='__main__':main()
