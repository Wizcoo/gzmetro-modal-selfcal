#include "ModalSelfCal.h"
#include <windows.h>
#include <psapi.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>

using Clock=std::chrono::steady_clock;
static size_t peak() {
    PROCESS_MEMORY_COUNTERS counters{};
    if(!GetProcessMemoryInfo(GetCurrentProcess(),&counters,sizeof(counters)))
        throw std::runtime_error("working set unavailable");
    return counters.PeakWorkingSetSize;
}
template<class T> void read(std::ifstream& in,T* ptr,size_t n) {
    if(!in.read(reinterpret_cast<char*>(ptr),sizeof(T)*n)) throw std::runtime_error("short input");
}
int main(int argc,char** argv) try {
    if(argc!=5) throw std::runtime_error("usage: replay device roster.txt input.bin output.bin");
    std::vector<std::string> names;
    std::ifstream roster(argv[2]);
    for(std::string line;std::getline(roster,line);) names.push_back(line);
    if(names.empty()) throw std::runtime_error("empty roster");
    const size_t process_start=peak();
    ModalSelfCalConfig cfg;
    if(cfg.history_nights!=3 || cfg.max_frame_dev!=0) throw std::runtime_error("wrong V53 defaults");
    ModalSelfCalState engine(cfg);
    std::string error;
    if(!engine.Init(argv[1],names,&error,true)) throw std::runtime_error(error);
    std::ifstream in(argv[3],std::ios::binary);
    std::ofstream out(argv[4],std::ios::binary);
    const size_t points=names.size();
    std::vector<double> x(points),y(points);
    ModalSelfCalResult result;
    int64_t frames=0;
    double us=0, max_us=0;
    std::map<std::string,int> states_x,states_y;
    while(in.peek()!=std::char_traits<char>::eof()) {
        int64_t ts;
        read(in,&ts,1); read(in,x.data(),points); read(in,y.data(),points);
        const auto start=Clock::now();
        if(!engine.Process(ts,x,y,&result,&error) || !result.output_ready || result.duplicate)
            throw std::runtime_error(error+" invalid result");
        const double elapsed=std::chrono::duration<double,std::micro>(Clock::now()-start).count();
        us+=elapsed; max_us=std::max(max_us,elapsed); ++frames;
        ++states_x[result.info_x.state]; ++states_y[result.info_y.state];
        out.write(reinterpret_cast<const char*>(result.x.data()),points*sizeof(double));
        out.write(reinterpret_cast<const char*>(result.y.data()),points*sizeof(double));
    }
    out.close();
    if(!out || !frames) throw std::runtime_error("empty input or output error");
    const size_t process_peak=peak();
    std::string state;
    int64_t last_ts=0;
    if(!engine.ExportState(&state,&last_ts,&error)) throw std::runtime_error(error);
    std::cout<<frames<<" "<<process_start<<" "<<process_peak<<" "<<us<<" "<<max_us<<" "<<state.size()<<"\n";
    for(auto& item:states_x) std::cout<<"x "<<item.first<<" "<<item.second<<"\n";
    for(auto& item:states_y) std::cout<<"y "<<item.first<<" "<<item.second<<"\n";
    return 0;
} catch(const std::exception& e) {
    std::cerr<<e.what()<<"\n"; return 2;
}
