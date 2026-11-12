"""Batched form of the frozen scalar/group ADMM, same objective/parameters.

Zero padding moves each window into a common15x15 operator. All columns of
the same window length stop together, as in the original implementation.
Daytime can skip the stateless optimizer while retaining identical history.
"""
from l1trend import L1Trend
from common import *
import warnings

class L1TrendFast(L1Trend):
 def __init__(self,p):
  super().__init__(p);self.Dpad=np.zeros((16,13,15));self.Hpad=np.zeros((16,15,15))
  for n,(D,H) in self.cache.items():self.Dpad[n,-(n-2):,-n:]=D;self.Hpad[n,-n:,-n:]=H
 def step(self,t,x,gate,ready,ncorrected,h):
  gap=self.last and (t-self.last>90000 or t<=self.last);self.last=int(t)
  if gap:self.history.clear();self.count[:]=0
  finite=np.isfinite(x);self.count=np.where(finite,np.minimum(self.count+1,15),0);self.history.append(np.asarray(x).copy());g=float(np.clip(gate,0,1)) if ready and ncorrected>0 and (h>=23 or h<7+1/3) else 0.
  if g==0:return np.asarray(x).copy(),{'eligible':np.zeros(self.p,bool),'nonconverged_points':0,'primal_mm':0.,'gate':g}
  cols=np.flatnonzero(self.count>=3)
  if not len(cols):return np.asarray(x).copy(),{'eligible':finite&(self.count>=3),'nonconverged_points':0,'primal_mm':0.,'gate':g}
  lengths=self.count[cols];yy=np.zeros((len(cols),15));hist=np.vstack(self.history);yy[:,-len(hist):]=hist[:,cols].T;valid=np.arange(15)[None,:]>=15-lengths[:,None];yy[~valid]=0;raw=yy.copy();raw[~valid]=np.nan
  with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);sigma=mad(np.diff(raw,n=2,axis=1),axis=1)/np.sqrt(6)
  sigma=np.maximum(.01,np.where(np.isfinite(sigma),sigma,.1));lam=sigma*np.sqrt(12*np.log(lengths));D=self.Dpad[lengths];H=self.Hpad[lengths];Dt=np.transpose(D,(0,2,1));z=np.zeros((len(cols),13,1));u=z.copy();Y=yy[:,:,None];level=Y.copy();primal=np.full(len(cols),np.inf);dual=primal.copy();active=np.ones(len(cols),bool)
  for k in range(50):
   new=np.matmul(H,Y+self.rho*np.matmul(Dt,z-u));level[active]=new[active];dl=np.matmul(D,level);old=z.copy();v=dl+u;zz=np.sign(v)*np.maximum(0,abs(v)-lam[:,None,None]/self.rho);z[active]=zz[active];u[active]+=(dl-z)[active]
   if k%5==4:
    p=np.max(abs(dl-z),axis=(1,2));dd=np.max(abs(self.rho*np.matmul(Dt,z-old)),axis=(1,2));primal[active]=p[active];dual[active]=dd[active]
    for n in set(lengths[active]):
     group=lengths==n
     if np.max(np.maximum(primal[group],dual[group]))<1e-5:active[group]=False
    if not active.any():break
  out=np.asarray(x).copy();out[cols]=level[:,-1,0];self.last_residual=float(np.max(primal));self.nonconverged=int(np.sum(np.maximum(primal,dual)>1e-4));return x+g*(out-x),{'eligible':finite&(self.count>=3),'nonconverged_points':self.nonconverged,'primal_mm':self.last_residual,'gate':g}
