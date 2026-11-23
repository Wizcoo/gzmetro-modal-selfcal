// Measure the unmodified V53 plus the incremental calibration in a single process.
#include "ModalSelfCal.h"
#include "kernel.hpp"
#include "win_memory.hpp"

int main(int argc,char** argv) try {
    if(argc!=5) throw std::runtime_error("benchmark device names.txt input.bin baseline|candidate");
    std::ifstream roster(argv[2]), input(argv[3],std::ios::binary);
    if(!roster || !input) throw std::runtime_error("missing replay segment");
    std::vector<std::string> names;
    for(std::string name;std::getline(roster,name);) names.push_back(name);
    const bool apply=std::string(argv[4])=="candidate";
    const auto pre=process_peak();
    ModalSelfCalState v53; std::string error;
    if(!v53.Init(argv[1],names,&error,true)) throw std::runtime_error(error);
    const size_t p=names.size();
    std::vector<Channel> channels(apply?2*p:0);
    std::vector<double> x(p),y(p);
    ModalSelfCalResult result;
    double sum_us=0,checksum=0;
    size_t frames=0;
    std::array<size_t,5001> buckets{};
    int64_t ts;
    while(input.read(reinterpret_cast<char*>(&ts),sizeof(ts))) {
        for(auto* v:{&x,&y})
            if(!input.read(reinterpret_cast<char*>(v->data()),p*sizeof(double))) throw std::runtime_error("short frame");
        auto begin=std::chrono::steady_clock::now();
        if(!v53.Process(ts,x,y,&result,&error) || !result.output_ready || result.duplicate)
            throw std::runtime_error(error);
        if(apply) for(int axis=0;axis<2;++axis) {
            auto& values=axis?result.y:result.x;
            for(size_t j=0;j<p;++j) {
                double ignored;
                values[j]=channels[axis*p+j].step(int(ts/60000+480),values[j],ignored,nullptr,false);
            }
        }
        double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-begin).count();
        sum_us+=us; ++buckets[std::min(5000,int(us))]; ++frames;
        for(auto* v:{&result.x,&result.y}) for(double value:*v) if(std::isfinite(value)) checksum+=value;
    }
    if(!frames) throw std::runtime_error("empty input");
    size_t total=0,k=0;
    while(k<5000 && total+buckets[k]<std::ceil(frames*.95)) total+=buckets[k++];
    std::cout<<"{\"frames\":"<<frames<<",\"points\":"<<p<<",\"mean_ms\":"<<sum_us/frames/1000.
             <<",\"p95_ms_upper\":"<<(k+1)/1000.<<",\"peak_bytes\":"<<process_peak()
             <<",\"pre_init_peak_bytes\":"<<pre<<",\"kernel_state_bytes\":"<<sizeof(Channel)*channels.size()
             <<",\"checksum\":"<<checksum<<"}\n";
    return 0;
} catch(const std::exception& e) {std::cerr<<e.what()<<"\n";return 1;}
