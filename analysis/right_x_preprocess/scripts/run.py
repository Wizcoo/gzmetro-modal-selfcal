from common import *
import argparse,subprocess,concurrent.futures,time

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['old','validation'],required=True);a=p.parse_args();source=pd.read_csv(O/f'input_identity_{a.stage}.csv',dtype={'device_id':str});out=W/a.stage;out.mkdir(exist_ok=True)
 def job(row):
  line,dev=row['line'],row['device_id'];tick=time.monotonic()
  with (out/f'{line}_{dev}.log').open('w',encoding='utf-8') as log:r=subprocess.run([str(W/'preprocess.exe'),str(W/f'{a.stage}_{line}_{dev}.bin'),str(out),line,dev,a.stage],stdout=subprocess.PIPE,stderr=log,text=True)
  if r.returncode:raise RuntimeError(line+' '+dev+' '+(out/f'{line}_{dev}.log').read_text(encoding='utf-8')[-1800:])
  return {'stage':a.stage,'line':line,'device_id':dev,'exit_code':r.returncode,'elapsed_s':time.monotonic()-tick,'stdout':r.stdout.strip()}
 rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  for r in ex.map(job,source.to_dict('records')):rows.append(r);print(r,flush=True)
 write(pd.DataFrame(rows),f'run_audit_{a.stage}.csv')
if __name__=='__main__':main()
