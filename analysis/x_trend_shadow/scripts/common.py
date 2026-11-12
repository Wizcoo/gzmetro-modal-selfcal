from pathlib import Path
import os,json,hashlib,struct
import numpy as np,pandas as pd
O=Path(__file__).resolve().parents[1];R=O.parents[1];BASE=R.parent
W=Path(os.environ.get('XS_WORK',O/'.work'));W.mkdir(parents=True,exist_ok=True)
OLD=Path(os.environ.get('XS_RAW_CACHE',BASE/'x_preprocess_work_20261112/cache'))
LF=BASE/'low_frequency_research_20261112/analysis/crossline_low_frequency'
DATA=Path(os.environ.get('XS_DATA','E:/Wiz/GZMetro-Cpp/data-sql'))
METHODS=['B0_original','W3_original','A_thermal','B_event','C_reference','D_L1trend','D_W3_L1trend','E_residual_factor']
FOCUS=['780639346578','780639298317','780639376393','780638327479','780638349768','780630499846']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def epoch(s):return int(pd.Timestamp(s,tz='Asia/Shanghai').timestamp()*1000)
def iso(t):return pd.Timestamp(t,unit='ms',tz='UTC').tz_convert('Asia/Shanghai').isoformat(timespec='milliseconds')
def clocks(t):
 a=pd.to_datetime(t,unit='ms',utc=True).tz_convert('Asia/Shanghai');h=a.hour.to_numpy()+a.minute.to_numpy()/60+a.second.to_numpy()/3600
 return h,(a-pd.Timedelta(hours=12)).strftime('%Y-%m-%d').to_numpy()
def ref(n):return n.startswith(('YJ','ZJ'))
def node(n):return n.startswith(('YXJ','ZXJ'))
def kind(n):return 'reference' if ref(n) else 'node' if node(n) else 'ordinary'
def clean_json(x):
 if isinstance(x,dict):return {str(k):clean_json(v) for k,v in x.items()}
 if isinstance(x,(tuple,list,np.ndarray)):return [clean_json(v) for v in x]
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,np.integer):return int(x)
 if isinstance(x,np.bool_):return bool(x)
 return x
def save_json(x,name):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean_json(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def save(df,name):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(df).to_csv(p,index=False,encoding='utf-8',lineterminator='\n',float_format='%.12g')
def save_parts(df,name,budget=1850000):
 text=df.to_csv(index=False,lineterminator='\n',float_format='%.12g');count=max(1,int(np.ceil(len(text.encode())/budget)))
 p=O/name
 for old in [p]+list(p.parent.glob(p.stem+'_part*.csv')):
  if old.exists():
   assert O.resolve() in old.resolve().parents;old.unlink()
 for k in range(count):save(df.iloc[len(df)*k//count:len(df)*(k+1)//count],name if count==1 else str(Path(name).with_name(Path(name).stem+f'_part{k+1:02d}.csv')))
def packet_read(p):
 with Path(p).open('rb') as f:
  def u():return struct.unpack('<I',f.read(4))[0]
  names=[f.read(u()).decode() for _ in range(u())];n=len(names);nf=u();off=f.tell()
 dtype=np.dtype([('t','<i8'),('x','<f8',(n,)),('y','<f8',(n,)),('field','<f8',(n,)),('noise','<f8',(n,))]);assert Path(p).stat().st_size==off+nf*dtype.itemsize
 return names,np.memmap(p,mode='r',dtype=dtype,offset=off,shape=(nf,))
def native_read(p):
 with Path(p).open('rb') as f:
  def u():return struct.unpack('<I',f.read(4))[0]
  names=[f.read(u()).decode() for _ in range(u())];n=len(names);nf=u();off=f.tell()
 dtype=np.dtype([('t','<i8'),('base','<f8',(n,)),('w3','<f8',(n,)),('y','<f8',(n,)),('prew3','<f8',(n,))]);assert Path(p).stat().st_size==off+nf*dtype.itemsize
 return names,np.memmap(p,mode='r',dtype=dtype,offset=off,shape=(nf,))
def roster():return pd.read_csv(O/'input_identity.csv',dtype={'device_id':str}).to_dict('records')
def load_data(line,dev):return np.load(W/line/dev/'input.npz')
def mad(a,axis=None):
 m=np.nanmedian(a,axis=axis,keepdims=True);return 1.4826*np.nanmedian(abs(a-m),axis=axis)
def r2(y,p,min_n=60):
 ok=np.isfinite(y)&np.isfinite(p)
 if ok.sum()<min_n:return np.nan
 den=np.mean(y[ok]**2)
 return float(1-np.mean((y[ok]-p[ok])**2)/den) if den>1e-6 else np.nan
