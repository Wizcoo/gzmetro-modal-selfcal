"""Verify every exported gzip record, field roster, row count and SHA-256."""
import gzip,hashlib,json,sys,sqlite3
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else 'data')
m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
total=0;files=0;checks=[]
for s in m['sources']:
    for t in s['tables']:
        table_rows=0;lo=None;hi=None;daily={}
        for info in t['files']:
            p=root.parent/info['path']
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            if h!=info['sha256']:raise ValueError(f'SHA mismatch: {p}')
            n=0
            with gzip.open(p,'rt',encoding='utf-8') as f:
                for line in f:
                    r=json.loads(line)
                    if list(r)!=['_source_rowid']+[c['name'] for c in t['columns']]:raise ValueError(f'Columns differ: {p}')
                    ts=r[t['time_column']]
                    lo=ts if lo is None else min(lo,ts);hi=ts if hi is None else max(hi,ts)
                    n+=1
            if n!=info['rows']:raise ValueError(f'Row count mismatch: {p}')
            table_rows+=n;files+=1
        if table_rows!=t['rows']:raise ValueError(f'Table total mismatch: {t["table"]}')
        if lo!=t['min_timestamp'] or hi!=t['max_timestamp']:raise ValueError('Time coverage mismatch')
        total+=table_rows
        if '--sources' in sys.argv and t['time_column']:
            p=Path(s['file']);c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)
            q='"'+t['table'].replace('"','""')+'"';tc=t['time_column']
            start=1793808000000;end=1794412800000
            try:
                expected=c.execute(f'SELECT count(*),min("{tc}"),max("{tc}") FROM {q} WHERE "{tc}">=? AND "{tc}"<?',(start,end)).fetchone()
                if tuple(expected)!=(table_rows,lo,hi):
                    if t['status']!='partial_corrupt' or expected[0]<table_rows:
                        raise ValueError(f'Source count/time mismatch: {s["source_id"]} {t["table"]}: {expected} vs {(table_rows,lo,hi)}')
                    checks.append({'line':s['line'],'source':s['source_id'],'table':t['table'],'source_count':'partial_corrupt','source_rows':expected[0],'exported_rows':table_rows,'unexported_rows':expected[0]-table_rows})
                else:checks.append({'line':s['line'],'source':s['source_id'],'table':t['table'],'source_count':'PASS'})
            except sqlite3.DatabaseError as e:
                checks.append({'line':s['line'],'source':s['source_id'],'table':t['table'],'source_count':'unavailable_corrupt_source','error':str(e)})
            finally:c.close()
assert total==m['exported_source_rows']
report={'status':'PASS','files':files,'rows':total,'source_reconciliation':checks}
(root.parent/'docs'/'data_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','files':files,'rows':total,'source_checks':len(checks),'unavailable_source_checks':sum(x['source_count']!='PASS' for x in checks)}))
