#include "ModalSelfCal.h"
#include <iostream>
#include <stdexcept>

static void require(bool ok, const std::string& error) {
    if (!ok) throw std::runtime_error(error);
}
int main() {
    try {
        const std::vector<std::string> names={"P1","P2","P3","P4","P5","P6"};
        const std::vector<double> x={1,2,3,4,5,6}, y={6,5,4,3,2,1};
        std::string err, bytes, again;
        int64_t last=0;
        ModalSelfCalState a;
        require(a.Init("smoke-device",names,&err,true),err);
        ModalSelfCalResult r;
        const int64_t ts=1794362400000LL;
        require(a.Process(ts,x,y,&r,&err),err);
        require(r.output_ready && r.x==x && r.y==y,"daytime passthrough failed");
        require(a.ExportState(&bytes,&last,&err),err);
        require(last==ts,"export timestamp differs");
        ModalSelfCalState b;
        require(b.Init("smoke-device",names,&err),err);
        ModalSelfCalResumeInfo resume;
        require(b.ImportState(bytes,&resume,&err),err);
        require(resume.last_timestamp_ms==ts,"resume timestamp differs");
        require(b.ExportState(&again,&last,&err),err);
        require(again==bytes,"roundtrip changed state bytes");
        require(b.Process(ts+60000,x,y,&r,&err),err);
        require(r.output_ready && r.x==x && r.y==y,"resumed output differs");
        std::cout << "PASS state roundtrip and resume\n";
        return 0;
    } catch(const std::exception& e) {std::cerr << e.what() << '\n'; return 1;}
}
