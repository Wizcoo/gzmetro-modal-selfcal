from common import *
import subprocess,shutil,platform

def main():
 lock=json.loads((O/'implementation_freeze.json').read_text())
 for name,h in lock['algorithm_SHA256'].items():assert sha(O/'scripts'/name)==h
 for suffix in ['cpp','h']:assert sha(R/'versions/V51'/f'ModalSelfCal.{suffix}')==lock[f'original_V51_{suffix}_SHA256']
 compiler=os.environ.get('NP_CXX') or shutil.which('g++') or 'C:/msys64/ucrt64/bin/g++.exe'
 command=[compiler,'-std=c++17','-O2','-pthread','-I'+str(R/'versions/V51'),str(O/'scripts/driver.cpp'),'-o',str(W/'preprocess.exe')]
 subprocess.run(command,check=True)
 result={'compiler':subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],'command':command,'Python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'executable_SHA256':sha(W/'preprocess.exe'),'original_sources_included_without_patch':True}
 (O/'build_provenance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
