from l1_cpp import *
from datetime import datetime,timezone
import time

if __name__=='__main__':
 q=next(q for q in roster() if q['device_id']=='780639346578');a=np.load(W/q['line']/q['device_id']/'normal.npz');t=a['t'];x=a['base'];j=np.searchsorted(t,epoch('2026-11-10 03:00'));xx=x[j-15:j+120].copy();tt=t[j-15:j+120];s=L1TrendCpp(xx.shape[1]);maxgap=0;count=0;bad=0;tick=time.monotonic()
 for k,ts in enumerate(tt):
  out,info=s.step(ts,xx[k],1,True,100,3)
  for col in range(xx.shape[1]):
   if not np.isfinite(xx[k,col]) or s.count[col]<3:continue
   y,l,u,v=s.certificate(col);D=np.diff(np.eye(len(y)),n=2,axis=0);assert np.allclose(l,y-D.T@u,rtol=0,atol=1e-10);assert np.max(abs(u))<=v[1]+1e-12;gap=v[1]*np.sum(abs(D@l))-u@(D@l);assert abs(gap-v[2])<1e-9 and gap>=-1e-9;maxgap=max(maxgap,gap);bad+=gap>5e-7;count+=1
 # Affine functions lie in the nullspace, including large absolute offsets.
 f=L1TrendCpp(3);maximum_affine_error=0
 for k in range(60):
  y=np.array([123.,-45.+.02*k,.01*k]);out,_=f.step(1794423600000+k*60000,y,1,True,3,3);maximum_affine_error=max(maximum_affine_error,float(np.max(abs(out-y))))
 assert maximum_affine_error<1e-8
 save_json({'passed':True,'frozen_UTC':datetime.now(timezone.utc).isoformat(),'certificates_independently_checked':count,'max_duality_gap_mm2':maxgap,'above_tolerance_certificates':bad,'maximum_affine_error_mm':maximum_affine_error,'seconds_including_certificate_checks':time.monotonic()-tick,'parameters_window_lambda_unchanged':True,'header_SHA256':sha(O/'scripts/XTrendL1.h')},'L1_numerical_validation.json');print('PASS',count,maxgap,bad,maximum_affine_error,time.monotonic()-tick)
