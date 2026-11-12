from common import *
import ctypes as ct
import threading
_lib=None
_lock=threading.Lock()
_dll_path=os.add_dll_directory('C:/msys64/ucrt64/bin') if os.name=='nt' and Path('C:/msys64/ucrt64/bin').exists() else None
def library():
 global _lib
 with _lock:
  if _lib is None:
   lib=ct.CDLL(str(W/'xtrend_l1.dll'));ptr=ct.POINTER(ct.c_double);ip=ct.POINTER(ct.c_int);tp=ct.POINTER(ct.c_int64)
   lib.xs_create.argtypes=[ct.c_int];lib.xs_create.restype=ct.c_void_p;lib.xs_free.argtypes=[ct.c_void_p];lib.xs_step.argtypes=[ct.c_void_p,ct.c_int64,ptr,ct.c_double,ptr,ptr];lib.xs_dump.argtypes=[ct.c_void_p,ptr,ip,tp];lib.xs_restore.argtypes=[ct.c_void_p,ptr,ip,tp];lib.xs_certificate.argtypes=[ct.c_void_p,ct.c_int,ptr,ptr,ptr,ptr];_lib=lib
 return _lib
def ptr(a):return a.ctypes.data_as(ct.POINTER(ct.c_double))
class L1TrendCpp:
 def __init__(self,p):self.p=p;self.handle=library().xs_create(p);self.count=np.zeros(p,dtype=np.int32);self._last=0
 def __del__(self):
  if getattr(self,'handle',None):library().xs_free(self.handle);self.handle=None
 def step(self,t,x,gate,ready,ncorrected,h):
  g=float(np.clip(gate,0,1)) if ready and ncorrected>0 and (h>=23 or h<7+1/3) else 0.;x=np.ascontiguousarray(x,dtype=np.float64);out=np.empty(self.p);stats=np.empty(4);library().xs_step(self.handle,int(t),ptr(x),g,ptr(out),ptr(stats));self.count=np.where(np.isfinite(x),np.minimum(self.count+1,15),0).astype(np.int32)
  if self._last and (t-self._last>90000 or t<=self._last):self.count=np.isfinite(x).astype(np.int32)
  self._last=int(t);fallback=bool(stats[2]>0 or not np.isfinite(stats[0]));eligible=np.isfinite(x)&(self.count>=3)&(g>0)
  # Conservative device-frame fallback. No tested historical/injected frame
  # reached this path; numerical qualification must also hold for deployment.
  if fallback:out=x.copy();eligible[:]=False
  return out,{'eligible':eligible,'nonconverged_points':int(stats[2]),'numerical_passthrough':fallback,'primal_mm':float(np.sqrt(2*stats[0])),'duality_gap_mm2':stats[0],'max_iterations':stats[1],'gate':g}
 def dump(self):
  y=np.empty((self.p,15));counts=np.empty(self.p,dtype=np.int32);last=np.empty(self.p,dtype=np.int64);library().xs_dump(self.handle,ptr(y),counts.ctypes.data_as(ct.POINTER(ct.c_int)),last.ctypes.data_as(ct.POINTER(ct.c_int64)));return {'y':y.tolist(),'counts':counts.tolist(),'last':last.tolist(),'last_frame':self._last}
 def restore(self,state):
  y=np.asarray(state['y'],float);counts=np.asarray(state['counts'],np.int32);last=np.asarray(state['last'],np.int64);assert y.shape==(self.p,15) and counts.shape==(self.p,);library().xs_restore(self.handle,ptr(y),counts.ctypes.data_as(ct.POINTER(ct.c_int)),last.ctypes.data_as(ct.POINTER(ct.c_int64)));self.count=counts.copy();self._last=state['last_frame']
 def certificate(self,j):
  y=np.empty(15);l=y.copy();u=np.empty(13);s=np.empty(4);library().xs_certificate(self.handle,j,ptr(y),ptr(l),ptr(u),ptr(s));n=int(s[0]);return y[:n],l[:n],u[:max(0,n-2)],s
