"""Causal finite-memory second-order L1 trend, separate display channel.

Each valid point solves .5||y-l||² + lambda||D²l||_1 on past/current samples.
Only the last solution value is emitted. No future sample, retrospective
replacement, zero-phase step or forcing to a shared marker median.
"""
from common import *
from collections import deque
import warnings

class L1Trend:
 def __init__(self,p):
  self.p=p;self.window=15;self.rho=2.;self.history=deque(maxlen=15);self.count=np.zeros(p,int);self.last=0;self.cache={};self.last_residual=0.;self.nonconverged=0
  for n in range(3,16):
   D=np.diff(np.eye(n),n=2,axis=0);H=np.linalg.inv(np.eye(n)+self.rho*D.T@D);self.cache[n]=(D,H)
 def step(self,t,x,gate,ready,ncorrected,h):
  gap=self.last and (t-self.last>90000 or t<=self.last);self.last=int(t)
  if gap:self.history.clear();self.count[:]=0
  finite=np.isfinite(x);self.count=np.where(finite,np.minimum(self.count+1,15),0);self.history.append(np.asarray(x).copy());Y=np.vstack(self.history);out=np.asarray(x).copy();largest=0.;nonconverged=0
  for n in sorted(set(self.count)):
   if n<3:continue
   cols=np.flatnonzero(self.count==n);yy=Y[-n:,cols];D,H=self.cache[n]
   with warnings.catch_warnings():
    warnings.simplefilter('ignore',RuntimeWarning);sigma=mad(np.diff(yy,n=2,axis=0),axis=0)/np.sqrt(6)
   sigma=np.maximum(.01,np.where(np.isfinite(sigma),sigma,.1));lam=sigma*np.sqrt(12*np.log(n));z=np.zeros((n-2,len(cols)));u=z.copy();level=yy.copy();primal=dual=np.full(len(cols),np.inf)
   for k in range(50):
    level=H@(yy+self.rho*D.T@(z-u));dl=D@level;old=z.copy();v=dl+u;z=np.sign(v)*np.maximum(0,abs(v)-lam[None,:]/self.rho);u+=dl-z
    if k%5==4:
     primal=np.max(abs(dl-z),axis=0);dual=np.max(abs(self.rho*D.T@(z-old)),axis=0)
     if np.max(np.maximum(primal,dual))<1e-5:break
   out[cols]=level[-1];largest=max(largest,float(np.max(primal)));nonconverged+=int(np.sum(np.maximum(primal,dual)>1e-4))
  self.last_residual=largest;self.nonconverged=nonconverged;g=float(np.clip(gate,0,1)) if ready and ncorrected>0 and (h>=23 or h<7+1/3) else 0.;result=x+g*(out-x)
  if g==0:result=np.asarray(x).copy()
  return result,{'eligible':finite&(self.count>=3)&(g>0),'nonconverged_points':nonconverged,'primal_mm':largest,'gate':g}
