from l1trend import L1Trend
from l1trend_fast import L1TrendFast
from common import *
import time

def main():
 q=next(q for q in roster() if q['device_id']=='780639346578');d=np.load(W/q['line']/q['device_id']/'normal.npz');t=d['t'];x=d['base'];j=np.searchsorted(t,epoch('2026-11-10 03:00'));v=x[j-15:j+45].copy();tt=t[j-15:j+45].copy()
 # Deliberately exercise every reset/window length and mixed missing columns.
 for c in range(min(14,v.shape[1])):v[20+c,c]=np.nan
 v[45,0]+=1;v[50:53,1]+=3;old=L1Trend(v.shape[1]);new=L1TrendFast(v.shape[1]);maxdiff=0;oldtime=newtime=0;nonconv_old=nonconv_new=0
 for k,ts in enumerate(tt):
  gate=0 if k<10 else 1.;s=time.perf_counter();a,qa=old.step(ts,v[k],gate,True,100,3);oldtime+=time.perf_counter()-s;s=time.perf_counter();b,qb=new.step(ts,v[k],gate,True,100,3);newtime+=time.perf_counter()-s;assert np.array_equal(np.isfinite(a),np.isfinite(b));dif=np.nanmax(abs(a-b));maxdiff=max(maxdiff,float(dif));assert dif<1e-8,(k,dif)
  if gate:nonconv_old+=qa['nonconverged_points'];nonconv_new+=qb['nonconverged_points'];assert qa['nonconverged_points']==qb['nonconverged_points']
 save_json({'passed':True,'frames':len(v),'points':v.shape[1],'mixed_validity_step_pulse_and_day_bypass':True,'maximum_output_difference_mm':maxdiff,'reference_seconds':oldtime,'batch_seconds':newtime,'nonconverged_point_frames_old':nonconv_old,'nonconverged_point_frames_batch':nonconv_new,'old_code_SHA256':sha(O/'scripts/l1trend.py'),'batch_code_SHA256':sha(O/'scripts/l1trend_fast.py'),'objective_parameters_unchanged':True},'numeric_refactor_validation.json');print('PASS',maxdiff,'seconds',oldtime,newtime)

if __name__=='__main__':main()
