#include "ModalSelfCal.h"
#include <fstream>
#include <iostream>
#include <vector>
#include <string>
#include <iomanip>
#include <stdexcept>
#include <cmath>
#include <memory>
template<class T>T rd(std::istream& f){T v{};f.read(reinterpret_cast<char*>(&v),sizeof(v));if(!f)throw std::runtime_error("truncated input");return v;}
std::string str(std::istream& f){auto n=rd<uint32_t>(f);if(n>10000)throw std::runtime_error("bad string");std::string s(n,'\0');f.read(&s[0],n);return s;}
bool yj(const std::string& s){return s.rfind("YJ",0)==0;}
bool yxj(const std::string& s){return s.rfind("YXJ",0)==0;}
int main(int argc,char**argv){try{
 if(argc!=6)throw std::runtime_error("input output device mode scenario");
 std::ifstream f(argv[1],std::ios::binary);std::ofstream out(argv[2]);if(!f||!out)throw std::runtime_error("file open");
 auto n=rd<uint32_t>(f);std::vector<std::string> names;for(uint32_t i=0;i<n;++i)names.push_back(str(f));auto frames=rd<uint32_t>(f);
 ModalSelfCalConfig basecfg;ModalSelfCalState base(basecfg);std::string err; if(!base.Init(argv[3],names,&err,true))throw std::runtime_error(err);
 ModalSelfCalConfig cfg;std::string mode=argv[4],scenario=argv[5];
 if(mode=="include_YJ")cfg.fit_only_prefixes={"ZJ"};
 else if(mode=="exclude_YXJ")cfg.fit_only_prefixes={"YJ","ZJ","YXJ"};
 else if(mode!="V51_cold")throw std::runtime_error("mode");
 std::unique_ptr<ModalSelfCalState> alt;if(mode!="V51_cold"){alt.reset(new ModalSelfCalState(cfg));if(!alt->Init(argv[3],names,&err,true))throw std::runtime_error(err);}
 out<<"timestamp,markerName,rawX_mm,rawY_mm,replayX_mm,replayY_mm,gateX,modes_readyX,stateX\n"<<std::setprecision(17);
 const int64_t onset=1793991600000LL; // 2026-11-07 03:00 Beijing, independently checked by Python.
 size_t output_rows=0;
 for(uint32_t frame=0;frame<frames;++frame){auto ts=rd<int64_t>(f);std::vector<double>x(n),y(n);for(double&v:x)v=rd<double>(f);for(double&v:y)v=rd<double>(f);
  double step=ts>=onset?1.0:0.0,ramp=std::max(0.0,std::min(1.0,(ts-onset)/3600000.0));
  for(size_t i=0;i<n;++i){
   if(names[i]=="YXJ5"&&std::isfinite(x[i])){if(scenario=="target_step")x[i]+=step;if(scenario=="target_ramp")x[i]+=ramp;}
   if(names[i]=="YXJ6"&&std::isfinite(x[i])&&scenario=="multiview_target_step")x[i]+=step;
   if(names[i]=="YJ7"&&std::isfinite(x[i])&&scenario=="one_reference_step")x[i]+=step;
   if((yj(names[i])||yxj(names[i]))&&std::isfinite(x[i])&&scenario=="coherent_reference_and_target_step")x[i]+=step;
   if(names[i]=="YXJ5"&&std::isfinite(y[i])&&scenario=="target_Y_settlement")y[i]-=step;
  }
  ModalSelfCalResult b,a;if(!base.Process(ts,x,y,&b,&err))throw std::runtime_error(err);const ModalSelfCalResult* r=&b;
  if(alt){if(!alt->Process(ts,x,y,&a,&err))throw std::runtime_error(err);r=&a;}
  for(size_t i=0;i<n;++i)if(yj(names[i])||yxj(names[i])){out<<ts<<','<<names[i]<<','<<x[i]<<','<<y[i]<<','<<r->x[i]<<','<<b.y[i]<<','<<r->info_x.gate<<','<<r->info_x.modes_ready<<','<<r->info_x.state<<'\n';++output_rows;}
 }
 std::cout<<argv[3]<<' '<<mode<<' '<<scenario<<" frames="<<frames<<" rows="<<output_rows<<'\n';return 0;
}catch(const std::exception&e){std::cout<<"ERROR "<<e.what()<<'\n';return 1;}}
