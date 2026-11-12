from common import *
import argparse,subprocess,concurrent.futures,time,shutil,platform

def main():
 p=argparse.ArgumentParser();p.add_argument('--focus',action='store_true');p.add_argument('--inject',action='store_true');p.add_argument('--compile',action='store_true');p.add_argument('--missing-only',action='store_true');a=p.parse_args();os.environ['PATH']='C:/msys64/ucrt64/bin;'+os.environ.get('PATH','');build=[]
 if a.compile:
  for line,ver in [('right','V51'),('left','V53')]:
   src=R/'versions'/ver;folder=W/line;folder.mkdir(exist_ok=True);compiler='C:/msys64/ucrt64/bin/g++.exe';cmd=[compiler,'-std=c++17','-O2','-pthread','-I'+str(src),str(O/'scripts/native.cpp'),str(src/'ModalSelfCal.cpp'),'-o',str(folder/'native.exe')];r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,r.stderr;build.append({'line':line,'version':ver,'cpp_SHA256':sha(src/'ModalSelfCal.cpp'),'h_SHA256':sha(src/'ModalSelfCal.h'),'driver_SHA256':sha(O/'scripts/native.cpp'),'command':cmd,'compiler':subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],'Python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__})
  save_json(build,'build_provenance.json')
 def job(q):
  line,dev=q['line'],q['device_id'];folder=W/line/dev;before=sha(folder/'normal.bin') if (folder/'normal.bin').exists() else None;tick=time.monotonic();packet=OLD/f'validation_{line}_{dev}.bin';assert sha(packet)==q['raw_packet_SHA256'];cmd=[str(W/line/'native.exe'),str(packet),str(folder),dev,','.join(str(epoch(v)) for v in ['2026-11-10 03:00','2026-11-12 03:00']),str(int(a.inject))]
  with (folder/'native.log').open('w',encoding='utf-8') as log:r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=log,text=True)
  assert r.returncode==0,(line,dev,(folder/'native.log').read_text(encoding='utf-8')[-1500:]);names,d=native_read(folder/'normal.bin');source=load_data(line,dev);assert names==source['names'].tolist() and np.array_equal(d['t'],source['t']);after=sha(folder/'normal.bin');assert before is None or before==after,'original baseline changed';np.savez_compressed(folder/'normal.npz',t=d['t'],base=d['base'],w3=d['w3'],y=d['y'],prew3=d['prew3']);out={'line':line,'device_id':dev,'elapsed_seconds':time.monotonic()-tick,'injections':a.inject,'baseline_SHA256':after,'same_as_prior_pilot':before is None or before==after,'stdout':r.stdout.strip(),'status':'PASS'};print(out,flush=True);return out
 todo=[q for q in roster() if (not a.focus or q['device_id'] in FOCUS) and (not a.missing_only or not (W/q['line']/q['device_id']/'normal.npz').exists())];rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for r in pool.map(job,todo):rows.append(r)
 save(rows,'native_run_'+('missing' if a.missing_only else 'focus' if a.focus else 'all')+('_injections' if a.inject else '')+'.csv')

if __name__=='__main__':main()
