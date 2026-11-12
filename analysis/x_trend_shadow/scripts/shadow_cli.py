"""Read a copy of original monitoring CSV, append display-only trend fields.

No database, network, native modal engine or alarm engine is opened here.
Every existing CSV field is copied verbatim as a string. The original calX,
calY and opaque alarm payload retain their names and values.
"""
from common import *
from l1_cpp import L1TrendCpp
from shadow import ShadowTrend
from state_io import export_l1,restore_l1,export_shadow,restore_shadow,model_arrays
import csv,argparse

def number(v):
 try:return float(v)
 except (TypeError,ValueError):return np.nan

def run(input_path,output_path,names,method='D_L1trend',models=None,state_in=None,state_out=None):
 input_path=Path(input_path);output_path=Path(output_path);assert input_path.resolve()!=output_path.resolve(),'source CSV must remain unchanged';assert not output_path.exists(),'refuse to overwrite a previous output';names=list(names);assert len(set(names))==len(names);lookup={n:i for i,n in enumerate(names)};models=models or {};kernel=L1TrendCpp(len(names)) if method=='D_L1trend' else ShadowTrend(names,models)
 if state_in:
  state=json.loads(Path(state_in).read_text(encoding='utf-8'));assert state['schema']=='XStableDisplay1' and state['names']==names and state['method']==method;kernel=restore_l1(state['payload']) if method=='D_L1trend' else restore_shadow(state['payload'],models)
 extra=['stableTrendX','stableTrendDeltaX','stableTrendEligible','stableTrendEvent','stableTrendNumericFallback','stableTrendForAlarm','stableTrendVersion'];rows_done=0;frames_done=0
 output_path.parent.mkdir(parents=True,exist_ok=True)
 with input_path.open('r',encoding='utf-8-sig',newline='') as source,output_path.open('w',encoding='utf-8',newline='') as target:
  reader=csv.DictReader(source);fields=reader.fieldnames;assert fields and all(f in fields for f in ['timestamp','markerName','calX','base_gate','base_ready','base_ncorrected']);assert not set(fields).intersection(extra),'input already contains generated trend fields';writer=csv.DictWriter(target,fieldnames=fields+extra,lineterminator='\n');writer.writeheader();batch=[];last=None
  def emit(batch):
   nonlocal rows_done,frames_done
   if not batch:return
   ts=int(batch[0]['timestamp']);xx=np.full(len(names),np.nan);yy=xx.copy();seen=set()
   for r in batch:
    assert int(r['timestamp'])==ts and r['markerName'] in lookup;assert r['markerName'] not in seen,'duplicate observation';seen.add(r['markerName']);i=lookup[r['markerName']];xx[i]=number(r['calX']);yy[i]=number(r.get('calY'))
   first=batch[0];assert all(all(row[key]==first[key] for key in ['base_gate','base_ready','base_ncorrected']) for row in batch),'inconsistent per-device frame status';gate=number(first['base_gate']);ready=number(first['base_ready'])==1;nc=number(first['base_ncorrected']);h,night=clocks(np.array([ts],dtype=np.int64));before=[r.copy() for r in batch]
   if method=='D_L1trend':trend,q=kernel.step(ts,xx,gate,ready,nc,h[0]);eligible=q['eligible'];events=np.zeros(len(names),bool)
   else:
    r=kernel.step(ts,xx,yy,number(first.get('temp')),gate,ready,nc,h[0],night[0],alarms=batch);index=['A_thermal','B_event','C_reference'].index(method);trend=r['trend_x'][:,index];eligible=r['eligible'][:,index];events=r['event'];assert r['alarms'] is batch
   for r,original in zip(batch,before):
    i=lookup[r['markerName']];out=r.copy();out.update(stableTrendX=format(trend[i],'.17g'),stableTrendDeltaX=format(trend[i]-xx[i],'.17g'),stableTrendEligible=int(eligible[i]),stableTrendEvent='' if method=='D_L1trend' else int(events[i]),stableTrendNumericFallback=int(q['numerical_passthrough']) if method=='D_L1trend' else '',stableTrendForAlarm=0,stableTrendVersion='XS-D-L1-2' if method=='D_L1trend' else 'XS-ABC-1');assert r==original;writer.writerow(out);rows_done+=1
   frames_done+=1
  for row in reader:
   ts=int(row['timestamp'])
   if last is not None and ts!=last:
    assert ts>last,'input must be chronological';emit(batch);batch=[]
   batch.append(row);last=ts
  emit(batch)
 if state_out:
  p=Path(state_out);assert not p.exists(),'state output must be a new file';p.write_text(json.dumps({'schema':'XStableDisplay1','names':names,'method':method,'payload':export_l1(kernel) if method=='D_L1trend' else export_shadow(kernel)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 return {'rows':rows_done,'frames':frames_done,'original_fields_preserved':True,'alarm_field_not_interpreted_or_changed':True,'trend_for_alarm':False,'method':method}

def main():
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');p.add_argument('--points',required=True,help='JSON array of the original point order');p.add_argument('--method',choices=['D_L1trend','A_thermal','B_event','C_reference'],default='D_L1trend');p.add_argument('--models');p.add_argument('--state-in');p.add_argument('--state-out');a=p.parse_args();names=json.loads(Path(a.points).read_text(encoding='utf-8'));models={}
 if a.models:
  f=json.loads(Path(a.models).read_text(encoding='utf-8'));assert names==f['names']
  for n,m in f['models'].items():models[n]={k:model_arrays(v) if k in ['A','C'] else v for k,v in m.items()}
 if a.method in ['A_thermal','C_reference']:assert models,'predictive candidates require their frozen earlier-night models'
 print(run(a.input,a.output,names,a.method,models,a.state_in,a.state_out))

if __name__=='__main__':main()
