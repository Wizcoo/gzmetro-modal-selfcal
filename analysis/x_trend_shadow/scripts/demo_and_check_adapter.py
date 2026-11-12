from shadow_cli import run
from common import *
import csv

def read(p):return list(csv.DictReader(Path(p).open(encoding='utf-8')))
def main():
 q=next(q for q in roster() if q['device_id']=='780638327479');folder=W/q['line']/q['device_id'];d=np.load(folder/'normal.npz');src=load_data(q['line'],q['device_id']);names=src['names'].tolist();t=d['t'];base=d['base'];y=d['y'];state=pd.read_csv(folder/'normal_frames.csv');idx=np.flatnonzero((t>=epoch('2026-11-12 03:00'))&(t<epoch('2026-11-12 04:00')));rows=[]
 for ii in idx:
  for j,n in enumerate(names):rows.append(dict(timestamp=str(t[ii]),markerName=n,calX=format(base[ii,j],'.17g'),calY=format(y[ii,j],'.17g'),base_gate=str(state.base_gate.iloc[ii]),base_ready=str(state.base_ready.iloc[ii]),base_ncorrected=str(state.base_ncorrected.iloc[ii]),alarmPayload='TEST_OPAQUE_原通道告警字段_'+str(ii%3),rawX=format(src['x'][ii,j],'.17g')))
 # The alarm payload is an adapter test token, not a recovered site alarm.
 fields=list(rows[0]);prefix=O/'demo';prefix.mkdir(exist_ok=True)
 for name,records in [('original.csv',rows),('part1.csv',rows[:30*len(names)]),('part2.csv',rows[30*len(names):])]:
  with (prefix/name).open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader();w.writerows(records)
 (prefix/'points.json').write_text(json.dumps(names,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
 # Disposable results in .work avoid overwriting reviewable demo files.
 out=W/'adapter_test';out.mkdir(exist_ok=True)
 for f in out.glob('*.csv'):f.unlink()
 for f in out.glob('*.json'):f.unlink()
 full=run(prefix/'original.csv',out/'full.csv',names,state_out=out/'full_state.json');run(prefix/'part1.csv',out/'part1_out.csv',names,state_out=out/'mid.json');run(prefix/'part2.csv',out/'part2_out.csv',names,state_in=out/'mid.json',state_out=out/'end.json');a=read(out/'full.csv');b=read(out/'part1_out.csv')+read(out/'part2_out.csv');assert a==b,'adapter restart changes output';assert len(a)==len(rows)
 for original,new in zip(rows,a):assert all(new[k]==v for k,v in original.items()) and new['stableTrendForAlarm']=='0'
 import shutil
 shutil.copyfile(out/'full.csv',prefix/'shadow_output.csv');save_json({'passed':True,'original_fields_checked':len(rows)*len(fields),'original_rows':len(rows),'Y_strings_and_alarm_payload_unchanged':True,'full_vs_JSON_restart_rows_exact':len(a),'test_alarm_payload_not_actual_site_alert':True,'source_CSV_unmodified':True,'method':'D_L1trend'},'adapter_validation.json');print('PASS',full)

if __name__=='__main__':main()
