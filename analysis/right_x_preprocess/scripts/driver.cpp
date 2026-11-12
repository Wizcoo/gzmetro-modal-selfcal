#include "preprocess.h"
#include "ModalSelfCal.cpp" // Exact original source; no patch, no alternate math/config.
#include <fstream>
#include <iostream>
#include <chrono>
#include <cstring>
using V=pre::V;
template<class T>T rd(std::istream&f){T v{};f.read((char*)&v,sizeof(v));if(!f)throw std::runtime_error("truncated input");return v;}
template<class T>void wr(std::ostream&f,T v){f.write((char*)&v,sizeof(v));}
std::string rs(std::istream&f){auto n=rd<uint32_t>(f);std::string s(n,' ');f.read(s.data(),n);return s;}
void ws(std::ostream&f,const std::string&s){wr<uint32_t>(f,s.size());f.write(s.data(),s.size());}
double micros(std::chrono::steady_clock::time_point t){return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t).count();}
struct Frame{int64_t t;V x,y,field,noise;};
const std::vector<std::string> methods={"B0_raw","B1_N1","B2_N2_ab","B2ll_N2_linear","B3_N3"};
const std::vector<std::string> fields={"gate","modes_ready","from_tonight","n_history","n_learn","n_frame_valid","n_corrected","state_code","v1","v2","v3","pre_changed","pre_eligible","pre_reset","common_qualified","projection_failed","projection_leakage","max_pre_delta_mm","pre_us","core_us","Y_mismatch_count","learning_fit_RMS_mm","max_nontarget_pre_response_mm","max_nontarget_cal_response_mm"};
bool key(const std::string&n){return n.rfind("YJ",0)==0||n.rfind("YXJ",0)==0||n.rfind("ZJ",0)==0||n.rfind("ZXJ",0)==0;}
bool node(const std::string&n){return n.rfind("YXJ",0)==0||n.rfind("ZXJ",0)==0;}
bool isref(const std::string&n){return n.rfind("YJ",0)==0||n.rfind("ZJ",0)==0;}
std::vector<std::string> split(const std::string&s){std::vector<std::string> v;std::stringstream f(s);std::string t;while(std::getline(f,t,','))v.push_back(t);return v;}
pre::Model modelOf(ModalSelfCalState&s){std::string blob,err;int64_t t;if(!s.ExportState(&blob,&t,&err))throw std::runtime_error(err);auto decoded=Decode(blob);std::map<std::string,std::string> m;std::stringstream f(decoded.x);std::string line;while(std::getline(f,line)){auto p=line.find('=');if(p!=std::string::npos&&!m.count(line.substr(0,p)))m[line.substr(0,p)]=line.substr(p+1);}pre::Model o;o.night=std::stoll(m.at("night_id"));o.ready=m.at("modes_has")=="1";for(auto t:split(m.at("A")))o.A.push_back(std::stod(t));for(auto t:split(m.at("b")))o.b.push_back(std::stod(t));for(auto t:split(m.at("cbar")))o.cbar.push_back(std::stod(t));for(auto t:split(m.at("learn"))){o.learn.push_back(std::stod(t)!=0);o.learned+=o.learn.back();}for(auto t:split(m.at("use")))o.use.push_back(std::stod(t)!=0);return o;}
struct Stream {std::unique_ptr<ModalSelfCalState> core;pre::Processor processor;pre::Model model;Stream(const std::string&m,const std::string&dev,const std::vector<std::string>&names):processor(m,names.size()){core=std::make_unique<ModalSelfCalState>();std::string e;if(!core->Init(dev,names,&e,true))throw std::runtime_error(e);}};
struct Result{V y;std::vector<V> pre,cal,diag;};
struct Engine {
 std::string dev;std::vector<std::string> names;std::vector<std::unique_ptr<Stream>> streams;pre::RawHistory raw;
 Engine(const std::string&v,const std::vector<std::string>&n):dev(v),names(n),raw(n.size()){for(auto&m:methods)streams.emplace_back(new Stream(m,v,n));}
 Result run(const Frame&f,std::ofstream*birth=nullptr){Result out;std::string err;ModalSelfCalResult shadow;auto tick=std::chrono::steady_clock::now();if(!streams[0]->core->Process(f.t,f.x,f.y,&shadow,&err))throw std::runtime_error(err);double rawus=micros(tick);auto feature=raw.feature(f.t,f.x);
  for(size_t mi=0;mi<streams.size();mi++){
   auto&s=*streams[mi];ModalSelfCalResult r;V px=f.x;double pus=0,cus=rawus;
   if(mi==0)r=shadow;
   else {int valid=0;for(size_t i=0;i<f.x.size();i++)if(streams[0]->model.ready&&streams[0]->model.learn[i]&&std::isfinite(f.x[i]))valid++;bool commonok=streams[0]->model.ready&&shadow.info_x.modes_ready&&shadow.info_x.gate>0&&valid==streams[0]->model.learned&&shadow.info_x.n_frame_learn_valid==valid;tick=std::chrono::steady_clock::now();px=s.processor.run(f.t,f.x,shadow.x,streams[0]->model,commonok,feature);pus=micros(tick);tick=std::chrono::steady_clock::now();if(!s.core->Process(f.t,px,f.y,&r,&err))throw std::runtime_error(err);cus=micros(tick);}
   int ym=0;for(size_t i=0;i<f.y.size();i++){if(std::memcmp(&r.y[i],&shadow.y[i],8))ym++;if(std::isfinite(px[i])!=std::isfinite(f.x[i]))throw std::runtime_error("validity changed");}if(ym)throw std::runtime_error("Y differs original");
   bool born=r.info_x.modes_ready&&s.model.night!=r.info_x.night_id;if(born){s.model=modelOf(*s.core);if(birth)for(size_t i=0;i<names.size();i++)(*birth)<<methods[mi]<<','<<r.info_x.night_id<<','<<names[i]<<','<<int(s.model.learn[i])<<','<<int(s.model.use[i])<<','<<s.model.A[3*i]<<','<<s.model.A[3*i+1]<<','<<s.model.A[3*i+2]<<','<<s.model.b[i]<<','<<s.model.cbar[i]<<','<<r.info_x.n_history<<'\n';}
   auto&info=r.info_x;auto&pd=s.processor.diag;double rms=0,n=0;if(info.n_corrected>0&&s.model.ready)for(size_t i=0;i<names.size();i++)if(s.model.learn[i]&&std::isfinite(px[i])){double z=px[i]-s.model.b[i];for(int a=0;a<3;a++)z-=s.model.A[3*i+a]*info.v[a];rms+=z*z;n++;}
   int sc=info.state=="BASELINE"?1:info.state=="WAIT_MODES"?2:info.state=="RAMP"?3:info.state=="CORRECTING"?4:info.state=="DEGRADED_FRAME"?5:0;
   V dg={info.gate,double(info.modes_ready),double(info.modes_from_tonight),double(info.n_history),double(info.n_learn_points),double(info.n_frame_learn_valid),double(info.n_corrected),double(sc),info.v[0],info.v[1],info.v[2],double(pd.changed),double(pd.eligible),double(pd.reset),double(pd.reference_model),double(pd.projection_failed),pd.projection_leakage,pd.max_delta,pus,cus,double(ym),n?std::sqrt(rms/n):NAN,0,0};if(dg.size()!=fields.size())throw std::runtime_error("diag shape");out.pre.push_back(px);out.cal.push_back(r.x);out.diag.push_back(dg);
  }
  raw.update(f.t,f.x,feature);out.y=shadow.y;return out;
 }
};
struct Writer{std::ofstream f;std::vector<int> ids;Writer(const std::string&path,const std::vector<std::string>&names,uint32_t nf,bool compact):f(path,std::ios::binary){for(size_t i=0;i<names.size();i++)if(!compact||key(names[i]))ids.push_back(i);wr<uint32_t>(f,ids.size());for(int i:ids)ws(f,names[i]);wr<uint32_t>(f,methods.size());for(auto&m:methods)ws(f,m);wr<uint32_t>(f,fields.size());for(auto&s:fields)ws(f,s);wr<uint32_t>(f,nf);}
 void row(const Frame&x,const Result&r){wr<int64_t>(f,x.t);for(const V*v:{&x.x,&x.y,&x.field,&r.y})for(int i:ids)wr<double>(f,(*v)[i]);for(size_t m=0;m<methods.size();m++){for(int i:ids)wr<double>(f,r.pre[m][i]);for(int i:ids)wr<double>(f,r.cal[m][i]);f.write((char*)r.diag[m].data(),r.diag[m].size()*8);}}
};
struct Snapshot{size_t index;int64_t onset;std::vector<std::string> core;std::vector<pre::Processor> pre;std::vector<pre::Model> models;pre::RawHistory raw;};
std::vector<std::string> scenarios(const std::vector<std::string>&names){std::vector<std::string> s;for(auto&n:names)if(node(n))for(auto a:{"1","3"})s.push_back(n+"_step"+a);for(auto t:{"nodes_ramp1_1h","nodes_ramp3_3h","multiple_step1","multiple_step3","mode_step1","mode_step3","pulse1","pulse3","repeated_pulse3","reference3","common_reference1","missing_nodes","missing_learners","consecutive_jumps","small_node_step"})s.push_back(t);return s;}
int main(int argc,char**argv){static char logbuf[1<<20];std::setvbuf(stderr,logbuf,_IOFBF,sizeof(logbuf));try{
 if(argc!=6)throw std::runtime_error("packet output_dir line device old_or_validation");std::string packet=argv[1],dir=argv[2],line=argv[3],dev=argv[4],stage=argv[5];std::ifstream f(packet,std::ios::binary);auto np=rd<uint32_t>(f);std::vector<std::string> names;for(uint32_t i=0;i<np;i++)names.push_back(rs(f));auto nf=rd<uint32_t>(f);std::vector<Frame> frames;for(uint32_t i=0;i<nf;i++){Frame x;x.t=rd<int64_t>(f);for(V*v:{&x.x,&x.y,&x.field,&x.noise})for(uint32_t j=0;j<np;j++)v->push_back(rd<double>(f));frames.push_back(x);}
 std::vector<Result> clean;std::vector<Snapshot> snapshots;
 std::ofstream noiseout(dir+"/noise_"+line+"_"+dev+".csv");noiseout<<"line,device,method,noise_sigma_mm,night_id,marker,frames,raw_noise_RMSE_mm,pre_noise_sensitivity_RMSE_mm,cal_noise_sensitivity_RMSE_mm\n"<<std::setprecision(17);
 for(int level=0;level<4;level++){
  double sigma=level==0?0:level==1?.034778565088664073:level==2?.06955713017732815:.1391142603546563;Engine engine(dev,names);Writer out(dir+"/"+(level?"noise"+std::to_string(level):"clean")+"_"+line+"_"+dev+".bin",names,nf,level!=0);std::ofstream birth;
  if(!level){birth.open(dir+"/birth_"+line+"_"+dev+".csv");birth<<"method,night_id,marker,learn,use,A1,A2,A3,baseline_mm,cbar_mm,n_history\n"<<std::setprecision(17);}
  std::map<int64_t,std::vector<std::array<double,4>>> errors;
  for(size_t j=0;j<frames.size();j++){
   Frame x=frames[j];if(level)for(size_t i=0;i<x.x.size();i++)if(std::isfinite(x.x[i]))x.x[i]+=sigma*x.noise[i];
   if(!level){std::vector<int64_t> onsets=stage=="old"?std::vector<int64_t>{1793905200000LL,1793991600000LL}:std::vector<int64_t>{1794078000000LL,1794423600000LL};for(int64_t onset:onsets)if(x.t>=onset&&(j==0||frames[j-1].t<onset)){
    Snapshot s;s.index=j;s.onset=onset;s.raw=engine.raw;std::string e;int64_t ts;for(auto&st:engine.streams){std::string b;if(!st->core->ExportState(&b,&ts,&e))throw std::runtime_error(e);s.core.push_back(b);s.pre.push_back(st->processor);s.models.push_back(st->model);}snapshots.push_back(s);
   }}
   Result r=engine.run(x,!level?&birth:nullptr);if(level)for(size_t i=0;i<r.y.size();i++)if(std::memcmp(&r.y[i],&clean[j].y[i],8))throw std::runtime_error("Y noise differs clean");out.row(x,r);
   if(!level)clean.push_back(std::move(r));else{int64_t night;double hour;gzmetro_msc::MscLocalParts(x.t,8,&night,&hour);if(hour>=23+1./3&&hour<31){auto&acc=errors[night];if(acc.empty())acc.resize(np*methods.size());for(size_t m=0;m<methods.size();m++)for(size_t i=0;i<np;i++)if(std::isfinite(x.x[i])&&std::isfinite(r.cal[m][i])&&std::isfinite(clean[j].cal[m][i])){auto&a=acc[m*np+i];a[0]++;a[1]+=std::pow(x.x[i]-frames[j].x[i],2);a[2]+=std::pow(r.pre[m][i]-clean[j].pre[m][i],2);a[3]+=std::pow(r.cal[m][i]-clean[j].cal[m][i],2);}}}
  }
  if(level)for(auto&kv:errors)for(size_t m=0;m<methods.size();m++)for(size_t i=0;i<np;i++){auto&a=kv.second[m*np+i];if(a[0])noiseout<<line<<','<<dev<<','<<methods[m]<<','<<sigma<<','<<kv.first<<','<<names[i]<<','<<a[0]<<','<<std::sqrt(a[1]/a[0])<<','<<std::sqrt(a[2]/a[0])<<','<<std::sqrt(a[3]/a[0])<<'\n';}
 }
 for(auto&snap:snapshots)for(auto&scenario:scenarios(names)){
  Engine engine(dev,names);engine.raw=snap.raw;std::string err;for(size_t m=0;m<methods.size();m++){ModalSelfCalResumeInfo ri;if(!engine.streams[m]->core->ImportState(snap.core[m],&ri,&err))throw std::runtime_error(err);engine.streams[m]->processor=snap.pre[m];engine.streams[m]->model=snap.models[m];}
  size_t end=snap.index;while(end<frames.size()&&frames[end].t<snap.onset+14400000)end++;Writer out(dir+"/"+scenario+"_"+std::to_string(snap.onset)+"_"+line+"_"+dev+".bin",names,end-snap.index,true);
  int refid=-1,nodeid=-1;std::vector<int> refs,nodes;for(size_t i=0;i<names.size();i++){if(isref(names[i]))refs.push_back(i);if(node(names[i]))nodes.push_back(i);}if(!refs.empty())refid=refs[0];if(!nodes.empty())nodeid=nodes[0];double maxload=0;for(size_t i=0;i<names.size();i++)if(key(names[i])&&snap.models[0].ready&&snap.models[0].use[i])maxload=std::max(maxload,std::abs(snap.models[0].A[3*i]));if(maxload==0&&snap.models[0].ready)for(size_t i=0;i<names.size();i++)if(snap.models[0].learn[i])maxload=std::max(maxload,std::abs(snap.models[0].A[3*i]));
  for(size_t j=snap.index;j<end;j++){
   Frame x=frames[j];V truth(np,0);double h=(x.t-snap.onset)/3600000.;int frame=j-snap.index;double amp=scenario.back()=='3'?3:1;
   for(size_t i=0;i<np;i++){
    double delta=0;if(scenario==names[i]+"_step1"||scenario==names[i]+"_step3")delta=amp;
    if(scenario.rfind("nodes_ramp",0)==0&&node(names[i]))delta=scenario=="nodes_ramp1_1h"?std::min(1.,h):std::min(3.,h);
    if(scenario.rfind("multiple_step",0)==0&&i%2==0)delta=amp;
    if(scenario.rfind("mode_step",0)==0&&snap.models[0].ready&&snap.models[0].use[i]&&maxload>0)delta=amp*snap.models[0].A[3*i]/maxload;
    if((scenario=="pulse1"||scenario=="pulse3")&&int(i)==(nodeid>=0?nodeid:0)&&frame==0)delta=amp;
    if(scenario=="repeated_pulse3"&&int(i)==(nodeid>=0?nodeid:0)&&frame%10==0&&frame<50)delta=3;
    if(scenario=="reference3"&&int(i)==refid)delta=3;
    if(scenario=="common_reference1"&&isref(names[i]))delta=1;
    if(scenario=="small_node_step"&&int(i)==nodeid)delta=.034778565088664073;
    if(scenario=="consecutive_jumps"&&int(i)==nodeid&&frame<40){int phase=(frame/5)%4;delta=phase==0?1:phase==2?-1:0;}
    if(std::isfinite(x.x[i])){x.x[i]+=delta;truth[i]=delta;}
    if(scenario=="missing_nodes"&&node(names[i])&&frame<10)x.x[i]=NAN;
    if(scenario=="missing_learners"&&snap.models[0].ready&&snap.models[0].learn[i]&&frame<10)x.x[i]=NAN;
   }
   Result r=engine.run(x);for(size_t i=0;i<r.y.size();i++)if(std::memcmp(&r.y[i],&clean[j].y[i],8))throw std::runtime_error("Y injection differs clean");for(size_t m=0;m<methods.size();m++){double pm=0,cm=0;for(size_t i=0;i<np;i++)if(truth[i]==0&&std::isfinite(x.x[i])){pm=std::max(pm,std::abs(r.pre[m][i]-clean[j].pre[m][i]));cm=std::max(cm,std::abs(r.cal[m][i]-clean[j].cal[m][i]));}r.diag[m][22]=pm;r.diag[m][23]=cm;}out.row(x,r);
  }
 }
 std::cout<<line<<' '<<dev<<" frames="<<nf<<" streams=5 noise_levels=3 snapshots="<<snapshots.size()<<" Y_bitwise=PASS validity=PASS\n";return 0;
}catch(const std::exception&e){std::cerr<<"ERROR "<<e.what()<<'\n';return 1;}}
