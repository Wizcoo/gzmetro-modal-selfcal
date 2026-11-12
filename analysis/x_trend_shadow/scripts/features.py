from common import *

class Features:
 """Strictly causal RC temperature state, baseline and reference state."""
 def __init__(self,p):
  self.p=p;self.last=0;self.night=None;self.fast=np.nan;self.slow=np.nan;self.level=np.full(p,np.nan);self.reset_night()
 def reset_night(self):
  self.count=np.zeros(self.p);self.total=np.zeros(self.p);self.ftotal=np.zeros(3);self.fcount=0
 def step(self,t,x,T,h,night):
  dt=(t-self.last)/60000 if self.last else 1.;gap=not self.last or dt<=0 or dt>1.5;self.last=int(t)
  if night!=self.night:self.night=night;self.reset_night()
  if np.isfinite(T):
   if gap or not np.isfinite(self.fast):self.fast=self.slow=float(T)
   else:self.fast+=(1-np.exp(-dt/12))*(T-self.fast);self.slow+=(1-np.exp(-dt/60))*(T-self.slow)
   f=np.array([self.slow,max(0,self.fast-self.slow),min(0,self.fast-self.slow)])
  else:self.fast=self.slow=np.nan;f=np.full(3,np.nan)
  finite=np.isfinite(x);warm=gap|~np.isfinite(self.level);self.level[warm&finite]=x[warm&finite];a=1-np.exp(-min(max(dt,.01),1.5)/10);self.level[finite&~warm]+=a*(x[finite&~warm]-self.level[finite&~warm]);self.level[~finite]=np.nan
  if 22<=h<23:
   self.count+=finite;self.total+=np.where(finite,x,0)
   if np.all(np.isfinite(f)):self.ftotal+=f;self.fcount+=1
  b=np.divide(self.total,self.count,out=np.full(self.p,np.nan),where=self.count>=10)
  ready=h>=23 or h<7.333333334
  if not ready:b[:]=np.nan
  tf=f-self.ftotal/self.fcount if ready and self.fcount>=10 else np.full(3,np.nan)
  return {'thermal':tf,'residual':x-b,'slow_residual':self.level-b,'baseline':b,'dt':min(max(dt,.01),1.5),'gap':gap}

def all_features(t,x,T):
 h,night=clocks(t);s=Features(x.shape[1]);F=np.full((len(t),3),np.nan);z=np.full_like(x,np.nan);zs=z.copy();b=z.copy()
 for i in range(len(t)):
  q=s.step(t[i],x[i],T[i],h[i],night[i]);F[i]=q['thermal'];z[i]=q['residual'];zs[i]=q['slow_residual'];b[i]=q['baseline']
 return F,z,zs,b

def fit_ridge(X,Y,minimum=90):
 if Y.ndim==1:Y=Y[:,None]
 B=np.full((X.shape[1],Y.shape[1]),np.nan);scale=np.full(Y.shape[1],np.nan)
 for j in range(Y.shape[1]):
  ok=np.all(np.isfinite(X),axis=1)&np.isfinite(Y[:,j])
  if ok.sum()<minimum:continue
  xx=X[ok];yy=Y[ok,j];s=np.maximum(np.std(xx,axis=0),.02);xx=xx/s
  # Small fixed ridge; no parameter search against PV or validation night.
  beta=np.linalg.solve(xx.T@xx+.02*len(xx)*np.eye(xx.shape[1]),xx.T@yy)/s
  for k in range(2):
   e=yy-X[ok]@beta;sig=max(.03,float(mad(e)));w=np.minimum(1.,2.5*sig/np.maximum(abs(e),1e-12));g=(xx*w[:,None]).T@xx+.02*len(xx)*np.eye(xx.shape[1]);beta=np.linalg.solve(g,xx.T@(w*yy))/s
  B[:,j]=beta;scale[j]=max(.03,float(mad(yy-X[ok]@beta)))
 return B,scale

def fit_reference(RR,Y,refs):
 p=Y.shape[1];B=np.zeros((len(refs),p));B[:]=np.nan;sigma=np.full(p,np.nan)
 for j in range(p):
  keep=[k for k,r in enumerate(refs) if r!=j]
  if len(keep)<2:continue
  c,s=fit_ridge(RR[:,keep],Y[:,j]);B[:,j]=0;B[keep,j]=c[:,0];sigma[j]=s[0]
 return B,sigma

def bank(t,x,T,status,names):
 F,z,zs,b=all_features(t,x,T);h,nights=clocks(t);active=status.base_ready.eq(1).to_numpy()&status.base_gate.ge(.99999).to_numpy()&status.base_ncorrected.gt(0).to_numpy()&((h>=23+1/3)|(h<7));refs=[i for i,n in enumerate(names) if ref(n)];previous=[];models={};audit=[]
 for night in sorted(set(nights)):
  current=(nights==night)&active
  model={'A':None,'C':None,'training_nights':previous[-2:].copy()}
  if len(previous)>=2:
   n0,n1=previous[-2:];train=(nights==n0)&active;valid=(nights==n1)&active;pooled=(train|valid)
   ca,sa=fit_ridge(F[train],zs[train]);pred=F[valid]@ca;score=np.array([r2(zs[valid,j],pred[:,j]) for j in range(x.shape[1])]);fa,scale=fit_ridge(F[pooled],zs[pooled]);admit=np.isfinite(score)&(score>=.1)&np.all(np.isfinite(fa),axis=0)
   model['A']={'B':fa,'admit':admit,'sigma':scale,'feature_limit':np.maximum(.1,np.nanquantile(abs(F[pooled]),.99,axis=0)*1.5),'refs':refs,'validation_r2':score}
   for j,n in enumerate(names):audit.append(dict(night=night,method='A_thermal',marker=n,kind=kind(n),training_night=n0,validation_night=n1,past_R2=score[j],admitted=bool(admit[j]),references=len(refs),reason='past_predictability' if admit[j] else 'not_predictive_or_missing'))
   if len(refs)>=2:
    cc,sc=fit_reference(zs[train][:,refs],zs[train],refs);pp=zs[valid][:,refs]@np.nan_to_num(cc,nan=0);scorec=np.array([r2(zs[valid,j],pp[:,j]) if np.all(np.isfinite(cc[:,j])) else np.nan for j in range(x.shape[1])]);fc,sc=fit_reference(zs[pooled][:,refs],zs[pooled],refs)
    # Conditional reference prediction, each reference strictly held out.
    qscore=np.array([scorec[j] for j in refs]);good_ref=np.isfinite(qscore)&(qscore>=0);refok=good_ref.sum()>=2;admitc=(scorec>=.1)&np.all(np.isfinite(fc),axis=0)&refok
    cr=zs[pooled][:,refs];ok=np.isfinite(cr).all(axis=1);energy=np.nan
    if ok.sum()>=90:
     singular=np.linalg.svd(cr[ok],compute_uv=False);energy=singular[0]**2/np.sum(singular**2)
    admitc&=np.isfinite(energy)&(energy>=.6)
    model['C']={'B':fc,'admit':admitc,'sigma':sc,'refs':refs,'reference_quality':good_ref,'rank1_energy':energy,'validation_r2':scorec}
    for j,n in enumerate(names):audit.append(dict(night=night,method='C_reference',marker=n,kind=kind(n),training_night=n0,validation_night=n1,past_R2=scorec[j],admitted=bool(admitc[j]),references=len(refs)-int(j in refs),rank1_energy=energy,reason='independent_reference_transfer' if admitc[j] else 'no_independent_transfer_or_reference_quality'))
   else:
    for n in names:audit.append(dict(night=night,method='C_reference',marker=n,kind=kind(n),training_night=n0,validation_night=n1,past_R2=np.nan,admitted=False,references=len(refs),reason='fewer_than_two_local_references'))
  else:
   for method in ['A_thermal','C_reference']:
    for n in names:audit.append(dict(night=night,method=method,marker=n,kind=kind(n),admitted=False,references=len(refs),reason='fewer_than_two_completed_nights'))
  models[night]=model
  if current.sum()>=180:previous.append(night)
 return models,pd.DataFrame(audit),{'F':F,'residual':z,'slow_residual':zs,'baseline':b}
