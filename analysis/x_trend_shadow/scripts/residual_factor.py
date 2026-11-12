"""E: causal broad low-rank increments + sparse sustained local component.

This is an independent post-monitor trend candidate, not a new V51 mode.
Ordinary markers estimate a shared increment; YJ/ZJ/YXJ/ZXJ never drive it.
Basis fitting uses only completed observations and freezes by01:30, with
initial no-history bootstrap allowed. Local persistent residuals are excluded
from the shared solve while retaining their historical target response.
"""
from features import Features
from common import *
from collections import deque
import warnings

class ResidualFactor:
 def __init__(self,names):
  self.names=list(names);self.p=len(names);self.ordinary=np.array([i for i,n in enumerate(names) if not ref(n) and not node(n)]);self.features=Features(self.p);self.history=deque(maxlen=90);self.delta_history=deque(maxlen=31);self.A=None;self.night=None;self.counter=0;self.prev=np.full(self.p,np.nan);self.was_active=False;self.c=np.zeros(self.p);self.filtered=np.zeros(self.p);self.sparse=np.zeros(self.p,bool);self.local=np.zeros(self.p);self.model_id=0;self.participation=[];self.sigma=np.full(self.p,.05)
 def fit(self):
  if len(self.history)<60:return False
  Y=np.vstack(self.history);finite=np.isfinite(Y);cols=self.ordinary[(finite[:,self.ordinary].sum(axis=0)>=.7*len(Y))&~self.sparse[self.ordinary]]
  if len(cols)<max(8,int(np.ceil(.6*len(self.ordinary)))):return False
  with warnings.catch_warnings():
   warnings.simplefilter('ignore',RuntimeWarning);center=np.nanmedian(Y,axis=0);scale=np.maximum(.05,mad(Y,axis=0))
  Z=np.clip((Y-center)/scale,-4,4);zz=np.nan_to_num(Z[:,cols],nan=0.);C=zz.T@zz/max(1,len(Y)-1);ev,U=np.linalg.eigh(C);positive=ev[ev>1e-8];floor=np.median(positive) if len(positive) else 0.;chosen=[];participation=[]
  for k in np.argsort(ev)[::-1]:
   part=1/np.sum(U[:,k]**4)
   if ev[k]>max(.05,1.5*floor) and part>=.35*len(cols):chosen.append(k);participation.append(part/len(cols))
   if len(chosen)==2:break
  if not chosen:return False
  scores=zz@U[:,chosen];A=np.full((self.p,len(chosen)),np.nan)
  for j in range(self.p):
   ok=np.isfinite(Z[:,j])
   if ok.sum()<.7*len(Y):continue
   G=scores[ok].T@scores[ok]+.02*len(Y)*np.eye(len(chosen));beta=np.linalg.solve(G,scores[ok].T@Z[ok,j]);A[j]=beta*scale[j]
  if not np.isfinite(A[cols]).all():return False
  self.A=A;self.participation=participation;self.model_id+=1;return True
 def step(self,t,x,gate,ready,ncorrected,h,night):
  q=self.features.step(t,x,np.nan,h,night);finite=np.isfinite(x);full=bool(ready and ncorrected>0 and gate>=.99999 and (h>=23 or h<7));g=float(np.clip(gate,0,1)) if ready and ncorrected>0 and (h>=23 or h<7+1/3) else 0.;dt=q['dt']
  if night!=self.night:
   self.night=night;self.c[:]=0;self.filtered[:]=0;self.local[:]=0;self.sparse[:]=False;self.history.clear();self.delta_history.clear();self.counter=0;self.prev=np.full(self.p,np.nan);self.was_active=False
  if q['gap']:
   self.prev=np.full(self.p,np.nan);self.filtered[:]=0;self.local[:]=0;self.was_active=False;self.delta_history.clear()
  # No current frame enters the covariance used for this frame's solve.
  learning_open=h>=23 or h<1.5
  if full and self.counter%30==0 and (learning_open or self.A is None):self.fit()
  delta=x-self.prev;eligible=np.zeros(self.p,bool);shared=False;rank=0 if self.A is None else self.A.shape[1];support=0.;new_sparse=np.zeros(self.p,bool)
  if full and self.was_active and self.A is not None:
   if len(self.delta_history)>=7:
    with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);sig=mad(np.vstack(self.delta_history),axis=0)/np.sqrt(2)
    self.sigma=np.maximum(.02,np.where(np.isfinite(sig),sig,.05))
   ids=self.ordinary[np.isfinite(delta[self.ordinary])&np.all(np.isfinite(self.A[self.ordinary]),axis=1)&~self.sparse[self.ordinary]]
   if len(ids)>=max(8,int(np.ceil(.6*len(self.ordinary)))):
    A=self.A[ids]/self.sigma[ids,None];b=delta[ids]/self.sigma[ids];weights=np.ones(len(ids));coef=np.zeros(rank);solved=True
    for iteration in range(4):
     G=(A*weights[:,None]).T@A+1e-8*np.eye(rank)
     if np.linalg.cond(G)>1e8:solved=False;break
     coef=np.linalg.solve(G,A.T@(weights*b));e=b-A@coef;weights=np.minimum(1.,2.5/np.maximum(abs(e),1e-12))
    support=float(np.sum(weights>=.5)/max(1,len(self.ordinary)))
    if solved and support>=.6:
     predicted=self.A@coef;innovation=delta-predicted;self.local=np.exp(-dt/200)*self.local+np.nan_to_num(innovation,nan=0.);new_sparse=np.isfinite(innovation)&(abs(self.local)>np.maximum(.35,4*self.sigma));self.sparse|=new_sparse;shared=True;eligible=finite&np.all(np.isfinite(self.A),axis=1)
     # These are shared predicted increments in observation coordinates.
     # Integrating here prevents basis rotation from creating level jumps.
     alpha=1-np.exp(-dt/15);self.filtered[eligible]+=alpha*(predicted[eligible]-self.filtered[eligible]);change=np.clip(self.filtered,-.1*dt,.1*dt);self.c[eligible]=np.clip(self.c[eligible]+change[eligible],-1.5,1.5)
  if full:
   self.history.append(q['slow_residual'].copy());self.counter+=1
   if self.was_active:self.delta_history.append(delta.copy())
  self.prev=np.asarray(x).copy();self.was_active=full
  out=x-g*self.c
  if g==0:out=np.asarray(x).copy()
  return out,{'eligible':eligible&shared&(g>0),'sparse':self.sparse.copy(),'new_sparse':new_sparse,'rank':rank,'broad_support_fraction':support,'model_id':self.model_id,'participation':self.participation.copy(),'gate':g,'correction':self.c.copy()}
