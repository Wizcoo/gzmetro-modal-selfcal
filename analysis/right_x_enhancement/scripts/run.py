from common import *
import argparse,subprocess,concurrent.futures,time

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['ea','all'],default='ea');p.add_argument('--tag');p.add_argument('--executable',default='research.exe');p.add_argument('--inject',action='store_true');a=p.parse_args()
    modes='identity,E_Huber,E_full,A' if a.stage=='ea' else 'identity,E_Huber,E_full,A,B0,B1,B2,D_EMA,D_Kalman'
    tag=a.tag or a.stage;out=W/tag;out.mkdir(exist_ok=True)
    def job(dev):
        tick=time.monotonic()
        with (out/f'{dev}.log').open('w',encoding='utf-8') as log:
            r=subprocess.run([str(W/a.executable),str(W/dev),str(out),dev,modes,'inject' if a.inject else 'normal'],stdout=subprocess.PIPE,stderr=log,text=True)
        if r.returncode:raise RuntimeError(dev+' '+(out/f'{dev}.log').read_text(encoding='utf-8')[-1500:])
        return {'device_id':dev,'stage':a.stage,'modes':modes,'injections':a.inject,'exit_code':r.returncode,'elapsed_s':time.monotonic()-tick,'stdout':r.stdout.strip()}
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for r in ex.map(job,DEVS):rows.append(r);print(r,flush=True)
    write(pd.DataFrame(rows),f'run_audit_{tag}.csv')
if __name__=='__main__':main()
