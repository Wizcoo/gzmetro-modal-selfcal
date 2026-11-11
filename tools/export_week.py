"""Read-only SQLite export; standard library only. Originals are never repaired."""
import argparse,base64,gzip,hashlib,json,sqlite3
from pathlib import Path
from datetime import datetime,timedelta,timezone

TZ=timezone(timedelta(hours=8))
START=int(datetime(2026,11,5,tzinfo=TZ).timestamp()*1000)
END=int(datetime(2026,11,12,tzinfo=TZ).timestamp()*1000)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def stamp(x):return datetime.fromtimestamp(x/1000,TZ).isoformat(timespec='milliseconds') if x is not None else None
def write_json(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def export_table(c,table,dest,start,end):
    name,sql=table
    q='"'+name.replace('"','""')+'"'
    schema=list(c.execute(f'PRAGMA table_info({q})'))
    cols=[s[1] for s in schema]
    tc='timestamp' if 'timestamp' in cols else 'ts' if 'ts' in cols else None
    result={'table':name,'sql':sql,'columns':[{'name':s[1],'sqlite_type':s[2]} for s in schema],
            'time_column':tc,'rows':0,'files':[],'unreadable_rowid_ranges':[],
            'min_timestamp':None,'max_timestamp':None,'daily_rows':{}}
    if tc is None:
        result['status']='excluded_no_time_column';return result
    try:
        lo=c.execute(f'SELECT rowid FROM {q} ORDER BY rowid ASC LIMIT 1').fetchone()
        hi=c.execute(f'SELECT rowid FROM {q} ORDER BY rowid DESC LIMIT 1').fetchone()
        if not lo:result['status']='empty_table';return result
    except sqlite3.DatabaseError as e:
        # Some rotated copies have a broken right-most btree reference while a
        # forward aggregate still reads all rows. Do not discard those tables.
        try:
            bounds=c.execute(f'SELECT min(rowid),max(rowid) FROM {q}').fetchone()
            lo=(bounds[0],);hi=(bounds[1],)
            result['bounds_method']='forward_aggregate_after_reverse_scan_error'
            if lo[0] is None:result['status']='empty_table';return result
        except sqlite3.DatabaseError:
            try:
                lo=c.execute(f'SELECT rowid FROM {q} LIMIT 1').fetchone()
                seq=c.execute('SELECT seq FROM sqlite_sequence WHERE name=?',(name,)).fetchone()
                if not lo or not seq:raise ValueError('No safe rowid upper bound')
                hi=seq
                result['bounds_method']='autoincrement_high_water_mark_after_scan_error'
            except (sqlite3.DatabaseError,ValueError) as fallback:
                result.update(status='unreadable_table',error=str(e),bounds_error=str(fallback));return result
    writer=None;outpath=None;npart=0;partrows=0;preview=[]
    def close_part():
        nonlocal writer
        if writer:
            writer.close();writer=None
            result['files'].append({'path':str(outpath.relative_to(dest.parents[2])).replace('\\','/'),
                                    'rows':partrows,'bytes':outpath.stat().st_size,'sha256':sha(outpath)})
    def emit(row):
        nonlocal writer,outpath,npart,partrows
        if writer is None:
            dest.mkdir(parents=True,exist_ok=True)
            npart+=1;partrows=0;outpath=dest/f'{name}.part{npart:03}.jsonl.gz'
            writer=gzip.open(outpath,'wt',encoding='utf-8',compresslevel=6,newline='\n')
        values={k:({'$binary_base64':base64.b64encode(v).decode()} if isinstance(v,bytes) else v) for k,v in zip(['_source_rowid']+cols,row)}
        writer.write(json.dumps(values,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
        partrows+=1;result['rows']+=1
        ts=values[tc]
        result['min_timestamp']=ts if result['min_timestamp'] is None else min(ts,result['min_timestamp'])
        result['max_timestamp']=ts if result['max_timestamp'] is None else max(ts,result['max_timestamp'])
        day=stamp(ts)[:10];result['daily_rows'][day]=result['daily_rows'].get(day,0)+1
        if len(preview)<3:preview.append(values)
        if partrows>=100000:close_part()
    def scan(a,b):
        try:
            rows=c.execute(f'SELECT rowid,* FROM {q} WHERE rowid>=? AND rowid<=? AND "{tc}">=? AND "{tc}"<?',(a,b,start,end)).fetchall()
        except sqlite3.DatabaseError as e:
            if b-a<16:
                result['unreadable_rowid_ranges'].append({'start':a,'end':b,'error':str(e)})
                return
            mid=(a+b)//2;scan(a,mid);scan(mid+1,b);return
        for row in rows:emit(row)
    for a in range(lo[0],hi[0]+1,20000):scan(a,min(a+19999,hi[0]))
    close_part()
    if preview:write_json(dest/f'{name}.preview.json',preview)
    result['status']='partial_corrupt' if result['unreadable_rowid_ranges'] else 'complete_read'
    result['min_time_beijing']=stamp(result['min_timestamp']);result['max_time_beijing']=stamp(result['max_timestamp'])
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve()
    if (out/'manifest.json').exists():raise SystemExit('Output already contains manifest; choose a fresh output directory.')
    manifest={'window':{'start_inclusive':stamp(START),'end_exclusive':stamp(END),'timezone':'Asia/Shanghai'},
        'format':'UTF-8 JSON Lines, gzip; JSON null retains SQL NULL; _source_rowid added for provenance',
        'row_count_semantics':'Exported source rows, not deduplicated observations. Table and DB identities are separate.',
        'source_selection':{'left':'Current Nov-01 database family, volumes 3-7 overlapping the window.',
            'right':'Current Oct-27 family, volume 6 plus volume 7 copy. Copy chosen in place of damaged original volume 7; no union of overlapping copies.'},
        'limitations':['Local exports do not establish current DLL identity or physical accuracy.',
            'Unreadable rowid intervals are listed explicitly; no interpolation or in-place recovery.',
            'Missing local dates are not evidence that the site stopped collecting.'],
        'sources':[]}
    root=a.source_root
    selected=[('left',root/'左线'/'NewDevice'/f'1793507670403_DataBaseFile_{n}.db') for n in range(3,8)]
    selected += [('right',root/'右线'/'1793052366195_DataBaseFile_6.db'),
                 ('right',root/'右线'/'1793052366195_DataBaseFile_7 - 副本.db')]
    for line,p in selected:
        before=(p.stat().st_size,p.stat().st_mtime_ns)
        source_id=p.stem.replace(' - 副本','_copy')
        source={'line':line,'file':str(p),'source_id':source_id,'bytes':p.stat().st_size,'sha256':sha(p),'tables':[]}
        c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        tables=c.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        for t in tables:
            data=export_table(c,t,out/line/source_id,START,END)
            source['tables'].append(data)
            print(line,p.name,t[0],data['rows'],data['status'],flush=True)
        c.close()
        source['unchanged_during_export']=before==(p.stat().st_size,p.stat().st_mtime_ns)
        if not source['unchanged_during_export']:raise RuntimeError(f'Source changed during export: {p}')
        manifest['sources'].append(source)
        write_json(out/'manifest.in_progress.json',manifest)
    manifest['exported_source_rows']=sum(t['rows'] for s in manifest['sources'] for t in s['tables'])
    manifest['total_compressed_bytes']=sum(f['bytes'] for s in manifest['sources'] for t in s['tables'] for f in t['files'])
    manifest['tables_with_corruption']=[{'line':s['line'],'source_id':s['source_id'],'table':t['table'],'status':t['status'],'unreadable_ranges':len(t['unreadable_rowid_ranges'])} for s in manifest['sources'] for t in s['tables'] if t['status'] in ['partial_corrupt','unreadable_table']]
    write_json(out/'manifest.json',manifest)
    (out/'manifest.in_progress.json').unlink()
    print(json.dumps({k:manifest[k] for k in ['exported_source_rows','total_compressed_bytes','tables_with_corruption']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
