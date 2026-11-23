#include "ModalSelfCal.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <cstring>
#include <stdexcept>
#include <iterator>
namespace fs=std::filesystem;
void need(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
uint64_t u64(std::istream& f){unsigned char b[8];f.read((char*)b,8);need(bool(f),"truncated binary");uint64_t v=0;for(int i=0;i<8;i++)v|=uint64_t(b[i])<<(8*i);return v;}
std::string txt(std::istream& f){auto n=u64(f);need(n<1048576,"bad string");std::string s(n,'\0');f.read(s.data(),n);need(bool(f),"truncated string");return s;}
double num(std::istream& f){auto n=u64(f);double v;std::memcpy(&v,&n,8);return v;}
int main(int argc,char** argv){try{
 need(argc==8,"input.bin initial.state max_frame_dev points.csv frames.csv emit_start_ms final.state");
 std::ifstream in(fs::path(argv[1]),std::ios::binary);
 std::string magic="MSC_OFFLINE_INPUT_V1\n",s(magic.size(),'\0');in.read(s.data(),s.size());need(s==magic,"bad format");
 auto dev=txt(in);auto count=u64(in);std::vector<std::string> names;for(uint64_t j=0;j<count;j++)names.push_back(txt(in));auto nf=u64(in);
 ModalSelfCalConfig cfg;cfg.max_frame_dev=std::stod(argv[3]);
 ModalSelfCalState engine(cfg);std::string error;need(engine.Init(dev,names,&error,false),error);
 std::ifstream sf(fs::path(argv[2]),std::ios::binary);need(bool(sf),"state open failed");std::string state((std::istreambuf_iterator<char>(sf)),{});
 ModalSelfCalResumeInfo resume;need(engine.ImportState(state,&resume,&error),error);
 std::ofstream out{fs::path(argv[4])},frames{fs::path(argv[5])};need(bool(out)&&bool(frames),"output open failed");out<<std::setprecision(17);frames<<std::setprecision(17);
 out<<"timestamp,markerName,replayX,replayY,correctionX,correctionY\n";
 frames<<"timestamp,night_id,stateX,stateY,historyX,historyY,baselineX,baselineY,modesX,modesY,tonightX,tonightY,correctedX,correctedY,gateX,gateY,learnValidX,learnValidY\n";
 int64_t emit=std::stoll(argv[6]),last=0;uint64_t processed=0;
 for(uint64_t i=0;i<nf;i++){
  int64_t ts=u64(in);need(ts>last,"timestamps not increasing");last=ts;
  std::vector<double> x(count),y(count);for(auto& v:x)v=num(in);for(auto& v:y)v=num(in);
  if(ts<=resume.last_timestamp_ms)continue;
  ModalSelfCalResult r;need(engine.Process(ts,x,y,&r,&error,false),error);need(r.output_ready&&!r.duplicate,"no output");processed++;
  const auto& ix=r.info_x;const auto& iy=r.info_y;
  frames<<ts<<','<<ix.night_id<<','<<ix.state<<','<<iy.state<<','<<ix.n_history<<','<<iy.n_history<<','<<ix.baseline_frozen<<','<<iy.baseline_frozen<<','<<ix.modes_ready<<','<<iy.modes_ready<<','<<ix.modes_from_tonight<<','<<iy.modes_from_tonight<<','<<ix.n_corrected<<','<<iy.n_corrected<<','<<ix.gate<<','<<iy.gate<<','<<ix.n_frame_learn_valid<<','<<iy.n_frame_learn_valid<<'\n';
  if(ts>=emit)for(size_t j=0;j<count;j++)out<<ts<<','<<names[j]<<','<<r.x[j]<<','<<r.y[j]<<','<<r.correction_x[j]<<','<<r.correction_y[j]<<'\n';
 }
 need(in.peek()==std::char_traits<char>::eof(),"extra binary data");
 int64_t cutoff;need(engine.ExportState(&state,&cutoff,&error),error);
 std::ofstream final(fs::path(argv[7]),std::ios::binary);final.write(state.data(),state.size());need(bool(final)&&bool(out)&&bool(frames),"write failure");
 ModalSelfCalState check(cfg);need(check.Init(dev,names,&error,false),error);ModalSelfCalResumeInfo rr;need(check.ImportState(state,&rr,&error),error);need(rr.last_timestamp_ms==cutoff,"export/import cutoff mismatch");
 std::cout<<"PASS "<<dev<<" input_frames="<<nf<<" processed="<<processed<<" points="<<count<<" resume="<<resume.last_timestamp_ms<<" final="<<cutoff<<" final_import=OK\n";return 0;
 }catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}}
