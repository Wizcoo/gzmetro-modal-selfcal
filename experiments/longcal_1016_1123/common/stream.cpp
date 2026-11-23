#include "kernel.hpp"
#include "win_memory.hpp"

template<typename T> void read(std::istream& in,T* ptr,size_t n) {
    if(!in.read(reinterpret_cast<char*>(ptr),n*sizeof(T))) throw std::runtime_error("short input");
}
template<typename T> void write(std::ostream& out,const T* ptr,size_t n) {
    if(!out.write(reinterpret_cast<const char*>(ptr),n*sizeof(T))) throw std::runtime_error("write failed");
}
int main(int argc,char** argv) try {
    if(argc!=4 && argc!=5) throw std::runtime_error("stream.exe frames.bin outputs.bin samples.bin|- [events.bin]");
    std::ifstream in(argv[1],std::ios::binary);
    std::ofstream out(argv[2],std::ios::binary),samples;
    const bool sample=std::string(argv[3])!="-";
    if(sample) samples.open(argv[3],std::ios::binary);
    uint32_t p,f; read(in,&p,1); read(in,&f,1);
    if(!p || p>4096 || !f) throw std::runtime_error("invalid frame dimensions");
    const size_t pre_init_peak=process_peak();
    std::vector<Channel> channels(2*p);
    std::vector<double> values(2*p), reference(2*p);
    // Optional paired event experiment. Start each injected stream from the exact
    // pre-event normal state. Discard its history when the event ends.
    std::ifstream events;
    std::vector<Channel> shadow;
    std::vector<double> injected(2*p);
    int64_t next_event=-1;
    uint32_t event_id=0,active_event=0;
    auto advance_event=[&]() {
        if (events.peek()==std::char_traits<char>::eof()) {next_event=-1; return;}
        read(events,&next_event,1); read(events,&event_id,1); read(events,injected.data(),injected.size());
    };
    if(argc==5) {events.open(argv[4],std::ios::binary); if(!events) throw std::runtime_error("missing events"); advance_event();}
    int64_t last=0; double sum_us=0;
    std::array<unsigned,2001> bins{};
    for(unsigned i=0;i<f;++i) {
        int64_t ts; read(in,&ts,1); read(in,values.data(),values.size());
        if(ts<=last) throw std::runtime_error("nonmonotonic timestamps");
        last=ts;
        const int m=int(ts/minute_ms+480);
        const bool event=next_event==ts;
        if(event && event_id!=active_event) {shadow=channels; active_event=event_id;}
        auto start=std::chrono::steady_clock::now();
        for(unsigned j=0;j<values.size();++j) {
            // 2026-11-07 08:00 Shanghai. Sampling is disabled for validation and test.
            const bool draw=(uint64_t(i)*1009+j*31)%113==0 && ts<1794009600000LL;
            values[j]=channels[j].step(m,values[j],reference[j],sample?&samples:nullptr,draw);
        }
        double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();
        sum_us+=us; ++bins[std::min(2000,int(us))];
        if(event) {
            for(unsigned j=0;j<values.size();++j) {
                double ignored;
                values[j]=shadow[j].step(m,injected[j],ignored,nullptr,false);
            }
            advance_event();
        }
        write(out,values.data(),values.size()); write(out,reference.data(),reference.size());
    }
    if(next_event!=-1) throw std::runtime_error("unmatched injection timestamp");
    unsigned total=0,k=0;
    while(k<2000 && total+bins[k]<std::ceil(f*.95)) total+=bins[k++];
    const size_t peak=process_peak();
    std::array<int,3> accepted{},stable{};
    for(auto& ch:channels) {
        // A final partial block is eligible for reporting only after its time window closes.
        for(int j=0;j<3;++j) {accepted[j]+=ch.accepted[j];stable[j]+=ch.stable_minutes[j];}
    }
    std::cout<<"{\"frames\":"<<f<<",\"points\":"<<p<<",\"mean_ms\":"<<sum_us/f/1000
             <<",\"p95_ms_upper\":"<<(k+1)/1000.<<",\"peak_bytes\":"<<peak
             <<",\"pre_init_peak_bytes\":"<<pre_init_peak<<",\"added_peak_bytes\":"<<peak-pre_init_peak
             <<",\"test_stable_blocks\":"<<accepted[2]<<",\"test_stable_minutes\":"<<stable[2]
             <<",\"candidate_state_bytes_per_axis\":"<<sizeof(Candidate)
             <<",\"kernel_state_bytes\":"<<sizeof(Channel)*channels.size()+sizeof(double)*4*p<<"}\n";
    return 0;
} catch(const std::exception& e) {std::cerr<<e.what()<<"\n"; return 1;}
