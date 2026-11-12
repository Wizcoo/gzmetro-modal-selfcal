"""Separate trend channel. Does not call, mutate or feed back into the monitor.

Models are fitted only to earlier nights. All state updates use current/past
observations. Original X/Y and alarm payload are returned unchanged.
"""
from features import *
from collections import deque
import warnings

class ShadowTrend:
 def __init__(self,names,models):
  self.names=list(names);self.p=len(names);self.models=models;self.features=Features(self.p);self.history=deque(maxlen=13);self.last=0;self.prev=np.full(self.p,np.nan);self.night=None;self.refs=[j for j,n in enumerate(names) if ref(n)];self.model_override=None;self.reset()
 def reset(self):
  p=self.p;self.level=np.full(p,np.nan);self.velocity=np.zeros(p);self.P00=np.ones(p);self.P01=np.zeros(p);self.P11=np.ones(p)*.01;self.motion=np.zeros(p);self.recovery=np.zeros(p);self.cplus=np.zeros(p);self.cminus=np.zeros(p);self.aextra=np.zeros(p);self.cextra=np.zeros(p);self.again=np.ones(p);self.ap=np.ones(p)*.1;self.reference_event=False;self.reference_stale=0.
 def step(self,t,monitor_x,monitor_y,temperature,gate,ready,ncorrected,h,night,alarms=None):
  x=np.asarray(monitor_x);finite=np.isfinite(x);q=self.features.step(t,x,temperature,h,night);dt=q['dt']
  if self.night!=night:
   self.night=night;self.reset();self.history.clear();self.prev=np.full(self.p,np.nan)
  if q['gap']:
   self.history.clear();self.level[:]=np.nan;self.velocity[:]=0;self.motion[:]=0;self.recovery[:]=0;self.cplus[:]=self.cminus[:]=0
  delta=x-self.prev
  with warnings.catch_warnings():
   warnings.simplefilter('ignore',RuntimeWarning)
   hist=np.vstack(self.history) if len(self.history) else np.empty((0,self.p));ds=np.diff(hist,axis=0);sigma=np.maximum(.01,mad(ds,axis=0)/np.sqrt(2)) if len(hist)>=7 else np.full(self.p,.1)
  sigma=np.where(np.isfinite(sigma),sigma,.1);warm=np.isfinite(hist).sum(axis=0)>=7 if len(hist) else np.zeros(self.p,bool)
  jump=finite&np.isfinite(self.prev)&(abs(delta)>np.maximum(.20,4*sigma));large=finite&np.isfinite(delta)&(abs(delta)>np.maximum(.15,3*sigma));cohort=large.sum()>=max(3,int(np.ceil(.2*finite.sum()))) and abs(np.nansum(np.sign(delta[large])))>=.7*large.sum()
  self.cplus=np.maximum(0,self.cplus+np.nan_to_num(delta)-.15*sigma);self.cminus=np.minimum(0,self.cminus+np.nan_to_num(delta)+.15*sigma);persistent=(self.cplus>np.maximum(.18,4*sigma))|(self.cminus<-np.maximum(.18,4*sigma));event=(jump|persistent)&warm
  if cohort:event|=finite&warm
  self.motion=np.maximum(0,self.motion-dt);was_motion=self.motion>0;self.motion[event]=15;self.cplus[event]=self.cminus[event]=0;self.recovery=np.maximum(0,self.recovery-dt);self.recovery[was_motion&(self.motion<=0)]=10
  mode=np.where(self.motion>0,1,np.where(self.recovery>0,2,0)).astype(np.int8)
  init=finite&(~np.isfinite(self.level)|~warm);self.level[init]=x[init];self.velocity[init]=0;self.P00[init]=sigma[init]**2;self.P01[init]=0;self.P11[init]=sigma[init]**2/36
  decay=np.exp(-dt/30);prediction=self.level+self.velocity*dt;Rr=sigma**2;p00=self.P00+2*dt*self.P01+dt*dt*self.P11+Rr/400;p01=decay*(self.P01+dt*self.P11);p11=decay**2*self.P11+Rr*dt/1296;gain=p00/(p00+Rr);kg=p01/(p00+Rr);gain=np.maximum(gain,.8*self.recovery/10);innovation=x-prediction;new=prediction+gain*innovation;velocity=decay*self.velocity+kg*innovation
  moving=(mode==1)&finite;new[moving]=x[moving];velocity[moving]=0;new[init]=x[init];self.level[finite]=new[finite];self.velocity[finite]=velocity[finite];self.P00=(1-gain)*p00;self.P01=(1-gain)*p01;self.P11=p11-kg*p01
  self.level[~finite]=np.nan;self.velocity[~finite]=0;self.cplus[~finite]=self.cminus[~finite]=0
  refs=self.refs
  # A reference jump latches predictive adaptation until the next night.
  # Existing correction is held/decayed, never suddenly removed by a gate.
  if len(refs)>=2 and np.sum(np.isfinite(delta[refs])&(abs(delta[refs])>np.maximum(.4,4*sigma[refs])))>=2:self.reference_event=True
  model=self.model_override or self.models.get(night,{'A':None,'C':None});A=model.get('A');C=model.get('C');eligibleA=np.zeros(self.p,bool);eligibleC=eligibleA.copy();desiredA=self.aextra.copy();desiredC=self.cextra.copy()
  if A is not None and np.all(np.isfinite(q['thermal'])) and np.all(abs(q['thermal'])<=A['feature_limit']):
   pred=q['thermal']@A['B'];eligibleA=A['admit'].copy()&finite
   if not self.reference_event:
    for j in range(self.p):
     rr=[r for r in refs if r!=j and A['admit'][r] and np.isfinite(pred[r]) and abs(pred[r])>.05 and np.isfinite(q['residual'][r])]
     if len(rr)>=2:
      ratios=q['residual'][rr]/pred[rr];obs=float(np.median(ratios));spread=float(mad(ratios));self.ap[j]+=.001*dt
      if 0<=obs<=2 and spread<=.5 and abs(obs-self.again[j])<1:
       k=min(.03*dt,self.ap[j]/(self.ap[j]+max(.05,spread**2)));self.again[j]+=k*(obs-self.again[j]);self.ap[j]*=1-k
   desiredA=np.where(eligibleA,np.clip(pred*self.again,-1.5,1.5),0)
  else:desiredA[:]=0
  ref_quality=False
  if C is not None and len(refs)>=2 and not self.reference_event:
   rr=q['slow_residual'][refs];instant=q['residual'][refs]
   if np.all(np.isfinite(rr)):
    conditional=rr@np.nan_to_num(C['B'][:,refs],nan=0);sig=np.maximum(.05,C['sigma'][refs]);bad=abs(rr-conditional)>3.5*sig;raw_jump=np.isfinite(delta[refs])&(abs(delta[refs])>np.maximum(.4,4*sigma[refs]));ref_quality=(~bad&~raw_jump).sum()>=2 and not bad.any() and not raw_jump.any()
    if ref_quality:
     pred=rr@np.nan_to_num(C['B'],nan=0);eligibleC=C['admit'].copy()&finite;desiredC=np.where(eligibleC,np.clip(pred,-1.5,1.5),0)
  if ref_quality:self.reference_stale=0
  else:
   self.reference_stale+=dt
   # Brief faults retain the last correction. Long faults decay gradually.
   desiredC=self.cextra.copy() if self.reference_stale<=10 else np.zeros(self.p)
  if self.reference_event:
   desiredC=self.cextra.copy();desiredA=self.aextra.copy()
  for current,desired,tau in [(self.aextra,desiredA,4),(self.cextra,desiredC,12)]:
   change=(1-np.exp(-dt/tau))*(desired-current);change=np.clip(change,-.1*dt,.1*dt);current+=change;current[~finite]=0
  night_allowed=(h>=23 or h<7+1/3);g=float(np.clip(gate,0,1)) if ready and ncorrected>0 and night_allowed else 0.
  extra=np.stack([self.aextra,x-self.level,self.cextra],axis=1)*g;extra[~finite]=np.nan;trend=x[:,None]-extra;trend[~finite]=np.nan
  if g==0:trend[:]=x[:,None]
  eligible=np.stack([eligibleA,warm&finite,eligibleC],axis=1)&(g>0);self.history.append(x.copy());self.prev=x.copy();self.last=int(t)
  return {'monitor_x':monitor_x,'monitor_y':monitor_y,'alarms':alarms,'trend_x':trend,'difference_mm':-extra,'event':event,'event_mode':mode,'eligible':eligible,'gate':g,'reference_event_latched':self.reference_event,'reference_quality':ref_quality,'thermal_gain':self.again.copy()}
