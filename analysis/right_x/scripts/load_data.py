import gzip,json,hashlib
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent.parent
START=int(pd.Timestamp('2026-11-05',tz='Asia/Shanghai').timestamp()*1000)
END=int(pd.Timestamp('2026-11-07 15:00',tz='Asia/Shanghai').timestamp()*1000)

def load():
    cache=WORK/'.cache';cache.mkdir(exist_ok=True)
    m=json.loads((ROOT/'data'/'manifest.json').read_text(encoding='utf-8'))
    audit=[];frames={}
    for s in m['sources']:
        if s['line']!='right':continue
        for t in s['tables']:
            name=t['table'];parts=[]
            for f in t['files']:
                p=ROOT/f['path']
                assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
                df=pd.read_json(p,lines=True,compression='gzip',convert_dates=False,dtype=False)
                df['source_db']=s['source_id'];parts.append(df)
            if parts:frames.setdefault(name,[]).append(pd.concat(parts,ignore_index=True))
    for name,parts in frames.items():
        df=pd.concat(parts,ignore_index=True)
        tc='timestamp' if 'timestamp' in df else 'ts'
        df=df[df[tc].ge(START)&df[tc].le(END)].copy()
        # Source rowid/uin are local storage keys, not observation identities.
        if name.startswith('Marker_'):key=['timestamp','markerName','markerIndex','markerPos']
        elif name=='MarkerData':key=['timestamp','markerName','markerIndex','markerPos']
        elif name=='SubDeviceDisData':key=['timestamp','deviceId']
        elif name.startswith('SinglePoint_'):key=['ts','deviceId','cameraPos','pointName','pId']
        else:key=['ts','deviceId','cameraPos','imgId']
        key=[k for k in key if k in df]
        before=len(df)
        payload=[k for k in df if k not in ('source_db','_source_rowid','uin')]
        dup=df.duplicated(key,keep=False)
        conflicts=0
        if dup.any():
            for _,g in df.loc[dup].groupby(key,dropna=False,observed=True):
                if len(g[payload].drop_duplicates())>1:conflicts+=1
        df=df.drop_duplicates(payload,keep='first')
        # Preserve conflicting duplicate business keys; downstream code excludes
        # these keys from joins rather than selecting a convenient observation.
        ambiguous=df.duplicated(key,keep=False)
        df['ambiguous_business_key']=ambiguous
        df=df.sort_values(tc,kind='stable').reset_index(drop=True)
        df.to_pickle(cache/f'{name}.pkl')
        audit.append({'table':name,'loaded_rows':before,'exact_duplicates_removed':before-len(df),'conflicting_keys':conflicts,'ambiguous_rows':int(ambiguous.sum()),'retained_rows':len(df),'key':key,'min_timestamp_ms':int(df[tc].min()),'max_timestamp_ms':int(df[tc].max()),'columns':list(df)})
        print(name,len(df),'duplicates_removed',before-len(df),'ambiguous',int(ambiguous.sum()),flush=True)
    (WORK/'load_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':load()
