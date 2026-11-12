"""JSON research-state roundtrip; no production state files are read/written."""
from shadow import ShadowTrend
from l1trend import L1Trend
from common import *
from collections import deque

ARRAYS=['level','velocity','P00','P01','P11','motion','recovery','cplus','cminus','aextra','cextra','again','ap','prev']

def fingerprint(models):return hashlib.sha256(json.dumps(clean_json(models),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def export_shadow(s):
 record={'schema':'XTrendShadowState1','names':s.names,'model_fingerprint':fingerprint(s.models),'last':s.last,'night':s.night,'reference_event':s.reference_event,'reference_stale':s.reference_stale,'arrays':{n:getattr(s,n) for n in ARRAYS},'history':list(s.history),'features':s.features.__dict__,'override':s.model_override}
 return json.dumps(clean_json(record),ensure_ascii=False,separators=(',',':'),allow_nan=False)

def model_arrays(m):
 if m is None:return None
 result={}
 for k,v in m.items():
  if k in ['B','sigma','feature_limit','validation_r2']:result[k]=np.asarray(v,dtype=float)
  elif k in ['admit','reference_quality']:result[k]=np.asarray(v,dtype=bool)
  else:result[k]=v
 return result

def restore_shadow(text,models):
 q=json.loads(text);assert q['schema']=='XTrendShadowState1' and fingerprint(models)==q['model_fingerprint'];s=ShadowTrend(q['names'],models)
 for n in ARRAYS:setattr(s,n,np.asarray(q['arrays'][n],dtype=float))
 for n in ['last','night','reference_event','reference_stale']:setattr(s,n,q[n])
 s.history=deque([np.asarray(v,dtype=float) for v in q['history']],maxlen=13)
 for n,v in q['features'].items():
  if n in ['level','count','total','ftotal']:v=np.asarray(v,dtype=float)
  elif n in ['fast','slow'] and v is None:v=np.nan
  setattr(s.features,n,v)
 s.model_override={k:(model_arrays(v) if k in ['A','C'] else v) for k,v in q['override'].items()} if q['override'] is not None else None
 return s

def export_l1(s):
 if hasattr(s,'dump'):return json.dumps(clean_json({'schema':'XL1CPPState2','p':s.p,'state':s.dump()}),separators=(',',':'),allow_nan=False)
 return json.dumps(clean_json({'schema':'XL1State1','p':s.p,'last':s.last,'count':s.count,'history':list(s.history)}),separators=(',',':'),allow_nan=False)
def restore_l1(text):
 q=json.loads(text)
 if q['schema']=='XL1CPPState2':
  from l1_cpp import L1TrendCpp
  s=L1TrendCpp(q['p']);s.restore(q['state']);return s
 assert q['schema']=='XL1State1';s=L1Trend(q['p']);s.last=q['last'];s.count=np.asarray(q['count'],dtype=int);s.history=deque([np.asarray(v,dtype=float) for v in q['history']],maxlen=15);return s
