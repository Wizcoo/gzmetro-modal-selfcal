from pathlib import Path
import os,json,hashlib,struct
import numpy as np,pandas as pd
O=Path(os.environ.get('NP_OUTPUT',Path(__file__).resolve().parents[1]));O.mkdir(parents=True,exist_ok=True)
W=Path(os.environ.get('NP_WORK',O/'.work'));W.mkdir(parents=True,exist_ok=True)
R=Path(os.environ.get('NP_REPO',O.parents[1]))
OLD=Path(os.environ.get('NP_OLD_WORK',O.parent/'right_x_enhancement'/'.work'))
CACHE=Path(os.environ.get('NP_OLD_CACHE',O.parent/'right_x'/'.cache'))
DATA=Path(os.environ.get('NP_DATA','E:/Wiz/GZMetro-Cpp/data-sql'))
def epoch(t):return int(pd.Timestamp(t,tz='Asia/Shanghai').timestamp()*1000)
def iso(t):return pd.Timestamp(t,unit='ms',tz='UTC').tz_convert('Asia/Shanghai').isoformat(timespec='milliseconds')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(d,name):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);d.to_csv(p,index=False,encoding='utf-8',lineterminator='\n',float_format='%.12g');assert p.stat().st_size<1950000,(name,p.stat().st_size)
def write_parts(d,name):
 text=d.to_csv(index=False,lineterminator='\n',float_format='%.12g');size=len(text.encode('utf-8'))
 if size<1900000:write(d,name);return
 count=int(np.ceil(size/1800000));p=O/name
 if p.exists():
  assert O.resolve() in p.resolve().parents;p.unlink()
 for j in range(count):write(d.iloc[len(d)*j//count:len(d)*(j+1)//count],str(Path(name).with_name(Path(name).stem+f'_part{j+1:02d}.csv')))
def load_pr3(p):
 with p.open('rb') as f:
  def u():return struct.unpack('<I',f.read(4))[0]
  def s():return f.read(u()).decode()
  n=u();names=[s() for _ in range(n)];nm=u();methods=[s() for _ in range(nm)];nd=u();fields=[s() for _ in range(nd)];nf=u();offset=f.tell()
 inner=np.dtype([('x','<f8',(n,)),('loo','<f8',(n,)),('diag','<f8',(nd,))]);dt=np.dtype([('ts','<i8'),('rawx','<f8',(n,)),('rawy','<f8',(n,)),('y','<f8',(n,)),('methods',inner,(nm,))]);assert p.stat().st_size==offset+nf*dt.itemsize
 return names,methods,fields,np.memmap(p,dtype=dt,mode='r',offset=offset,shape=(nf,))
def robust_sd(v):
 v=np.asarray(v);v=v[np.isfinite(v)];return 1.4826*np.median(abs(v-np.median(v))) if len(v) else np.nan
def corr(a,b):
 q=np.isfinite(a)&np.isfinite(b)
 return float(np.corrcoef(a[q],b[q])[0,1]) if q.sum()>=20 and np.std(a[q])>1e-10 and np.std(b[q])>1e-10 else np.nan
def rolling(t,v,mins=5,minp=3):
 out=np.full(len(t),np.nan);cuts=np.r_[0,np.flatnonzero(np.diff(t)>90000)+1,len(t)]
 for a,b in zip(cuts[:-1],cuts[1:]):out[a:b]=pd.Series(v[a:b],index=pd.to_datetime(t[a:b],unit='ms',utc=True)).rolling(f'{mins}min',min_periods=minp).median().values
 return out
def metrics(t,v):
 ok=np.isfinite(v);t=np.asarray(t)[ok];v=np.asarray(v)[ok]
 if len(v)<20:return {'rows':len(v)}
 sm=rolling(t,v);dt=np.diff(t);adj=(dt>=30000)&(dt<=90000);r={'rows':len(v),'LF_Q95_Q05_mm':np.nanquantile(sm,.95)-np.nanquantile(sm,.05),'step_abs_P99_mm':np.quantile(abs(np.diff(v)[adj]),.99) if adj.any() else np.nan,'PV_mm':np.ptp(v),'first_last30_median_change_mm':np.median(v[t>=t[-1]-1800000])-np.median(v[t<t[0]+1800000])}
 ix=pd.Index(t);runs=np.cumsum(np.r_[False,np.diff(t)>90000])
 for m in [10,30,60]:
  j=ix.get_indexer(t-m*60000,method='nearest',tolerance=90000);good=j>=0;good[good]&=runs[good]==runs[j[good]];d=sm[good]-sm[j[good]];r[f'drift{m}min_abs_P99_mm']=np.nanquantile(abs(d),.99) if np.isfinite(d).any() else np.nan
 return r
