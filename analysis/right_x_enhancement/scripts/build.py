from common import *
import argparse,subprocess,shutil,platform

def main():
    p=argparse.ArgumentParser();p.add_argument('--cxx',default=shutil.which('g++'));a=p.parse_args();assert a.cxx,'Specify --cxx path/to/g++'
    args=[a.cxx,'-std=c++17','-O2','-pthread','-I',str(R/'versions/V51'),'-I',str(W),'-I',str(Path(__file__).parent),str(Path(__file__).parent/'driver.cpp'),str(R/'versions/V51/ModalSelfCal.cpp'),'-o',str(W/'research.exe')]
    subprocess.run(args,check=True)
    info={'compiler':subprocess.check_output([a.cxx,'--version'],text=True).splitlines()[0],'flags':['-std=c++17','-O2','-pthread'],'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'executable_sha256':sha(W/'research.exe'),'original_cpp_sha256':sha(R/'versions/V51/ModalSelfCal.cpp'),'original_header_sha256':sha(R/'versions/V51/ModalSelfCal.h'),'research_hook_sha256':sha(Path(__file__).parent/'research_hook.h'),'driver_sha256':sha(Path(__file__).parent/'driver.cpp')}
    (O/'build_provenance.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8',newline='\n')
if __name__=='__main__':main()
