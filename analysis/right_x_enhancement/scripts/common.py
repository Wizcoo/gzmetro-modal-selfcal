from pathlib import Path
import os,json,hashlib,struct
import numpy as np,pandas as pd
O=Path(os.environ.get('RX_OUTPUT',Path(__file__).resolve().parents[1]));O.mkdir(parents=True,exist_ok=True)
W=Path(os.environ.get('RX_WORK',O/'.work'));W.mkdir(parents=True,exist_ok=True)
R=Path(os.environ.get('RX_REPO',O.parents[1]))
C=Path(os.environ.get('RX_CACHE',O.parent/'right_x'/'.cache'))
DEVS=[p.stem.split('_')[1] for p in sorted(C.glob('Marker_780*.pkl'))]
assert len(DEVS)==6,('Load the six-device PR1 cache or set RX_CACHE',str(C))
def epoch(s):return int(pd.Timestamp(s,tz='Asia/Shanghai').timestamp()*1000)
def iso(t):return pd.Timestamp(t,unit='ms',tz='UTC').tz_convert('Asia/Shanghai').isoformat(timespec='milliseconds')
def write(d,name):
    p=O/name;p.parent.mkdir(parents=True,exist_ok=True);d.to_csv(p,index=False,encoding='utf-8',lineterminator='\n',float_format='%.12g')
    assert p.stat().st_size<1950000,('split file',name,p.stat().st_size)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def smooth(t,v):
    out=np.full(len(t),np.nan);cuts=np.r_[0,np.flatnonzero(np.diff(t)>90000)+1,len(t)]
    for a,b in zip(cuts[:-1],cuts[1:]):out[a:b]=pd.Series(v[a:b],index=pd.to_datetime(t[a:b],unit='ms',utc=True)).rolling('5min',min_periods=3).median().values
    return out
def metrics(t,v):
    good=np.isfinite(v);t=np.asarray(t)[good];v=np.asarray(v)[good];s=smooth(t,v);adj=(np.diff(t)>=30000)&(np.diff(t)<=90000)
    r={'rows':len(t),'LF_Q95_Q05_mm':np.nanquantile(s,.95)-np.nanquantile(s,.05),'step_abs_P99_mm':np.quantile(abs(np.diff(v)[adj]),.99) if adj.any() else np.nan,'PV_mm':np.ptp(v),'persistent_offset_first_last_30min_mm':np.nanmedian(v[t>=t[-1]-1800000])-np.nanmedian(v[t<t[0]+1800000])}
    reference=np.median(v[t<t[0]+1800000]);offset=s-reference;longest=0.;start=None;last=None
    for ti,vi in zip(t,offset):
        if np.isfinite(vi) and abs(vi)>1:
            if start is None or ti-last>90000:start=ti
            longest=max(longest,(ti-start)/60000);last=ti
        else:start=None;last=None
    r['max_abs_5min_offset_from_first30min_mm']=np.nanmax(abs(offset));r['longest_5min_offset_over1mm_duration_min']=longest
    ix=pd.Index(t);run=np.cumsum(np.r_[False,np.diff(t)>90000])
    for m in [10,30,60]:
        j=ix.get_indexer(t-m*60000,method='nearest',tolerance=90000);ok=j>=0;ok[ok]&=run[ok]==run[j[ok]];d=s[ok]-s[j[ok]];r[f'drift{m}min_abs_P99_mm']=np.nanquantile(abs(d),.99) if np.isfinite(d).any() else np.nan
    return r
