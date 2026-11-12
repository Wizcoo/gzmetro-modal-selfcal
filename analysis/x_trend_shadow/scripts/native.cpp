#include "ModalSelfCal.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <vector>
using V=std::vector<double>;
template<class T>T read(std::istream&f){T a{};f.read((char*)&a,sizeof a);if(!f)throw std::runtime_error("truncated input");return a;}
template<class T>void write(std::ostream&f,const T&a){f.write((const char*)&a,sizeof a);}
std::string stringread(std::istream&f){auto n=read<uint32_t>(f);std::string s(n,' ');f.read(s.data(),n);return s;}
void stringwrite(std::ostream&f,const std::string&s){write<uint32_t>(f,s.size());f.write(s.data(),s.size());}
bool node(const std::string&s){return s.rfind("YXJ",0)==0||s.rfind("ZXJ",0)==0;}
bool isReference(const std::string&s){return s.rfind("YJ",0)==0||s.rfind("ZJ",0)==0;}
struct Filter{std::array<double,3>b{};int count=0;int64_t last=0;
 double update(double x,int64_t t){if(!std::isfinite(x)){count=0;last=0;return NAN;}if(last&&(t<last||t-last>180000))count=0;last=t;if(count==0){b[0]=x;count=1;return x;}if(count==1){b[1]=x;count=2;return .5*(b[0]+b[1]);}if(count==2){b[2]=x;count=3;}else{b[0]=b[1];b[1]=b[2];b[2]=x;}auto a=b;std::sort(a.begin(),a.end());return a[1];}
};
struct Frame{int64_t t;V x,y;};
struct Result{V base,w3,y,pre;ModalSelfCalFrameInfo info0,info1;double us0=0,us1=0;};
struct Engine{
 std::unique_ptr<ModalSelfCalState>a,b;std::vector<Filter> filters;std::string device;std::vector<std::string>names;
 Engine(std::string dev,std::vector<std::string>n):filters(n.size()),device(dev),names(n){init();}
 void init(){a=std::make_unique<ModalSelfCalState>();b=std::make_unique<ModalSelfCalState>();std::string e;if(!a->Init(device,names,&e,true)||!b->Init(device,names,&e,true))throw std::runtime_error(e);}
 std::array<std::string,2> dump(){std::array<std::string,2>s;std::string e;int64_t t;if(!a->ExportState(&s[0],&t,&e)||!b->ExportState(&s[1],&t,&e))throw std::runtime_error(e);return s;}
 void restore(const std::array<std::string,2>&s){init();std::string e;ModalSelfCalResumeInfo r;if(!a->ImportState(s[0],&r,&e)||!b->ImportState(s[1],&r,&e))throw std::runtime_error(e);}
 Result run(const Frame&f){Result z;ModalSelfCalResult x,y;std::string e;auto tick=std::chrono::steady_clock::now();if(!a->Process(f.t,f.x,f.y,&x,&e))throw std::runtime_error(e);z.us0=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-tick).count();z.pre.resize(names.size());for(size_t j=0;j<names.size();j++)z.pre[j]=filters[j].update(f.x[j],f.t);tick=std::chrono::steady_clock::now();if(!b->Process(f.t,z.pre,f.y,&y,&e))throw std::runtime_error(e);z.us1=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-tick).count();for(size_t j=0;j<names.size();j++){if(std::memcmp(&x.y[j],&y.y[j],8))throw std::runtime_error("Y changed");if(std::isfinite(f.x[j])!=std::isfinite(z.pre[j]))throw std::runtime_error("W3 mask changed");}z.base=x.x;z.w3=y.x;z.y=x.y;z.info0=x.info_x;z.info1=y.info_x;return z;}
};
struct Writer{
 std::ofstream f,c;
 Writer(std::string prefix,const std::vector<std::string>&names,uint32_t nf):f(prefix+".bin",std::ios::binary),c(prefix+"_frames.csv"){
  write<uint32_t>(f,names.size());for(auto&s:names)stringwrite(f,s);write<uint32_t>(f,nf);
  c<<"timestamp,base_gate,w3_gate,base_ready,w3_ready,base_state,w3_state,base_nhistory,w3_nhistory,base_nlearn,w3_nlearn,base_nvalid,w3_nvalid,base_ncorrected,w3_ncorrected,base_us,w3_core_us\n"<<std::setprecision(17);
 }
 void row(int64_t t,const Result&r){write(f,t);for(auto*v:{&r.base,&r.w3,&r.y,&r.pre})f.write((const char*)v->data(),v->size()*8);auto&a=r.info0;auto&b=r.info1;c<<t<<','<<a.gate<<','<<b.gate<<','<<a.modes_ready<<','<<b.modes_ready<<','<<a.state<<','<<b.state<<','<<a.n_history<<','<<b.n_history<<','<<a.n_learn_points<<','<<b.n_learn_points<<','<<a.n_frame_learn_valid<<','<<b.n_frame_learn_valid<<','<<a.n_corrected<<','<<b.n_corrected<<','<<r.us0<<','<<r.us1<<'\n';if(!f||!c)throw std::runtime_error("write failed");}
};
struct Snapshot{size_t index;int64_t onset;std::array<std::string,2>core;std::vector<Filter>filters;};
int main(int argc,char**argv){static char logbuf[1<<20];std::setvbuf(stderr,logbuf,_IOFBF,sizeof(logbuf));try{
 if(argc!=6)throw std::runtime_error("input_packet outfolder device onset_csv inject0or1");std::string dir=argv[2],dev=argv[3];std::ifstream in(argv[1],std::ios::binary);auto n=read<uint32_t>(in);std::vector<std::string>names;for(uint32_t i=0;i<n;i++)names.push_back(stringread(in));auto nf=read<uint32_t>(in);std::vector<Frame>frames;for(uint32_t j=0;j<nf;j++){Frame f;f.t=read<int64_t>(in);for(V*v:{&f.x,&f.y})for(uint32_t i=0;i<n;i++)v->push_back(read<double>(in));for(uint32_t i=0;i<2*n;i++)read<double>(in);frames.push_back(f);}
 std::vector<int64_t>onsets;std::stringstream ss(argv[4]);std::string token;while(std::getline(ss,token,','))onsets.push_back(std::stoll(token));
 Engine engine(dev,names);std::vector<Result>clean;std::vector<Snapshot>snaps;Writer output(dir+"/normal",names,nf);
 for(size_t j=0;j<frames.size();j++){
  for(auto t:onsets)if(j&&frames[j].t>=t&&frames[j-1].t<t)snaps.push_back({j,t,engine.dump(),engine.filters});
  clean.push_back(engine.run(frames[j]));output.row(frames[j].t,clean.back());
 }
 std::ofstream manifest(dir+"/injection_manifest.csv");manifest<<"scenario,onset_ms,marker,target,nuisance,frames,baseline_ready,baseline_gate\n";
 uint64_t checks=uint64_t(nf)*n;
 if(std::string(argv[5])=="1")for(auto&s:snaps){
  if(!clean[s.index].info0.modes_ready||clean[s.index].info0.gate<.999999||clean[s.index].info0.n_corrected<=0)throw std::runtime_error("injection baseline not correcting");
  int target=0,ordinary=0,reference=-1;for(size_t i=0;i<names.size();i++){if(node(names[i])){target=i;break;}}for(size_t i=0;i<names.size();i++){if(!isReference(names[i])&&!node(names[i])){ordinary=i;break;}}for(size_t i=0;i<names.size();i++)if(isReference(names[i])){reference=i;break;}
  std::vector<std::string>cases={"node_step1","node_step3","ordinary_step3","ramp1_1h","ramp3_3h","cohort20_step1","cohort20_step3","refs_nodes_step1","pulse1frame3","pulse2frame3","reference_step3","references_step1","missing10","thermal_only","thermal_step1","restart","crossnight_step1"};
  for(auto&scenario:cases){
   if((scenario=="reference_step3"||scenario=="references_step1")&&reference<0)continue;
   Engine e(dev,names);e.restore(s.core);e.filters=s.filters;size_t end=s.index;int64_t duration=scenario=="crossnight_step1"?31LL*3600000:4LL*3600000;while(end<frames.size()&&frames[end].t<s.onset+duration)end++;Writer out(dir+"/"+scenario+"_"+std::to_string(s.onset),names,end-s.index);
   V mask(n,0);for(uint32_t i=0;i<n;i++){
    if(scenario=="ordinary_step3")mask[i]=int(i)==ordinary;
    else if(scenario.rfind("cohort20",0)==0)mask[i]=int((37*i+11)%n)<std::max(1,int(std::round(.2*n)));
    else if(scenario=="refs_nodes_step1")mask[i]=isReference(names[i])||node(names[i]);
    else if(scenario=="reference_step3")mask[i]=int(i)==reference;
    else if(scenario=="references_step1")mask[i]=isReference(names[i]);
    else if(scenario!="thermal_only"&&scenario!="restart")mask[i]=int(i)==target;
    manifest<<scenario<<','<<s.onset<<','<<names[i]<<','<<mask[i]<<','<<(scenario.rfind("thermal_",0)==0)<<','<<end-s.index<<','<<clean[s.index].info0.modes_ready<<','<<clean[s.index].info0.gate<<'\n';
   }
   for(size_t j=s.index;j<end;j++){
    if(scenario=="restart"&&j==s.index+30)e.restore(e.dump());
    Frame f=frames[j];double h=(f.t-s.onset)/3600000.;size_t k=j-s.index;double amp=scenario.find('3')!=std::string::npos?3:1;
    for(uint32_t i=0;i<n;i++){
     double a=amp;if(scenario=="ramp1_1h")a=std::min(1.,h);if(scenario=="ramp3_3h")a=std::min(3.,h);
     if(scenario=="pulse1frame3")a=k==0?3:0;if(scenario=="pulse2frame3")a=k<2?3:0;if(scenario=="missing10")a=0;
     if(scenario=="missing10"&&mask[i]&&k<10)f.x[i]=NAN;
     else if(std::isfinite(f.x[i]))f.x[i]+=mask[i]*a;
     if(scenario.rfind("thermal_",0)==0&&std::isfinite(f.x[i]))f.x[i]+=.4*std::min(2.,2*h);
    }
    auto z=e.run(f);for(uint32_t i=0;i<n;i++){if(std::memcmp(&z.y[i],&clean[j].y[i],8))throw std::runtime_error("injection Y changed");if(scenario=="restart"&&(std::memcmp(&z.base[i],&clean[j].base[i],8)||std::memcmp(&z.w3[i],&clean[j].w3[i],8)))throw std::runtime_error("native restart differs");checks++;}out.row(f.t,z);
   }
  }
 }
 std::cout<<dev<<" native_B0_and_W3=PASS Y_bitwise="<<checks<<" snapshots="<<snaps.size()<<" unchanged_original_source=1\n";return 0;
 }catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<'\n';return 1;}}
