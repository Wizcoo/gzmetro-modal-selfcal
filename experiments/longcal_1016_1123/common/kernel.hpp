#pragma once
// Per-marker, per-axis edge calibration. No filesystem or framework dependencies.
#include "candidate.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

constexpr double missing = std::numeric_limits<double>::quiet_NaN();
constexpr int window = Candidate::history_days;
static_assert(window >= 2 && window <= 30);
constexpr int64_t minute_ms = 60000;
inline double median(double* data, int count) {
    std::sort(data, data+count);
    return (data[(count-1)/2]+data[count/2])*.5;
}

struct Night {
    int day=-1000;
    std::array<float,10> sum{};
    std::array<uint16_t,10> count{};
};
template<class T> auto reset_if_supported(T& t,int) -> decltype(t.reset(),void()) {t.reset();}
template<class T> void reset_if_supported(T&,long) {}

struct Channel {
    Candidate model{};
    std::array<Night,window+1> past{};
    std::array<double,30> block{}, trail{};
    std::array<int,30> block_min{}, trail_min{};
    std::array<double,12> centers{};
    int block_id=-1, used=0, day_id=-1, center_count=0;
    int last_anchor_min=-100000, prev_min=-100000, hold_end=-1;
    std::array<int,3> accepted{},stable_minutes{};
    double anchor=missing, prev=missing, applied=0;

    void close_block() {
        if (used<24) return;
        auto range=std::minmax_element(block.begin(),block.begin()+used);
        if (*range.second-*range.first>.6 || std::abs(block[0]-block[used-1])>.25) return;
        std::array<double,30> delta{};
        int n=0;
        for (int i=1;i<used;++i)
            if (block_min[i]==block_min[i-1]+1) delta[n++]=std::abs(block[i]-block[i-1]);
        if (!n || median(delta.data(),n)>.12) return;
        auto copy=block;
        double center=median(copy.data(),used);
        model.learn_day(block[used-1],center);
        const int64_t stamp=int64_t(block_min[used-1]-480)*minute_ms;
        const int split=(stamp>=1794009600000LL)+(stamp>=1794700800000LL);
        ++accepted[split]; stable_minutes[split]+=used;
        const int day=block_id/48;
        if (day!=day_id) {day_id=day; center_count=0;}
        if (center_count>=12) throw std::logic_error("too many day blocks");
        centers[center_count++]=center;
        auto days=centers;
        anchor=median(days.data(),center_count);
        last_anchor_min=block_min[used-1];
    }

    double step(int m,double value,double& ref,std::ofstream* samples,bool draw) {
        const int day=m/1440, tod=m%1440, slot=m/30;
        if (slot!=block_id) {close_block(); used=0; block_id=slot;}
        ref=m-last_anchor_min<=2880?anchor:missing;
        if (!std::isfinite(value)) {applied=0; prev=missing; reset_if_supported(model,0); return value;}
        const bool connected=std::isfinite(prev) && m-prev_min<=3;
        const double velocity=connected?value-prev:0;
        if (!connected) {applied=0; hold_end=-1;}
        const bool night=tod>=1320 || tod<480;
        if (!connected || !night || !std::isfinite(ref)) reset_if_supported(model,0);
        if (!night || !std::isfinite(ref)) applied=0;
        if (night && std::isfinite(ref)) {
            const int night_id=day-(tod<480);
            const int hour=((tod+120)%1440)/60;
            double sum=0,squares=0; int n=0;
            for (const auto& phase:past) {
                if (phase.day>=night_id-window && phase.day<night_id && phase.count[hour]>=12) {
                    const double avg=double(phase.sum[hour])/phase.count[hour];
                    sum+=avg; squares+=avg*avg; ++n;
                }
            }
            const double dev=value-ref, hist=n?sum/n:0;
            const double spread=n?std::sqrt(std::max(0.,squares/n-hist*hist)):0;
            const int old=(m+1)%30;
            const bool ramp=trail_min[old]==m-29 && std::abs(value-trail[old])>=.65;
            if (connected && (std::abs(velocity)>=.5 || ramp)) hold_end=m+45;
            if (n<2 || !connected) {applied=0; reset_if_supported(model,0);}
            else if (m>hold_end) {
                if (samples && draw) {
                    const double target=dev*hist>0?std::copysign(
                        std::min({std::abs(dev),std::abs(hist),.8})*
                        std::max(0.,1-spread/(std::abs(hist)+.1)),dev):0;
                    const double row[6]={dev,hist,spread,double(n),velocity,target};
                    samples->write(reinterpret_cast<const char*>(row),sizeof(row));
                }
                double aim=std::clamp(model.predict(dev,hist,spread,n,velocity),-.8,.8);
                if (!std::isfinite(aim)) throw std::runtime_error("nonfinite model correction");
                // Smooth entry/exit over 15 minutes. Never backfill an earlier frame.
                const int elapsed=(tod+120)%1440;
                aim*=std::clamp(std::min(elapsed,599-elapsed)/15.,0.,1.);
                applied+=std::clamp(aim-applied,-.025,.025);
            }
            auto& phase=past[night_id%(window+1)];
            if (phase.day!=night_id) {phase=Night{}; phase.day=night_id;}
            if (m!=prev_min) {phase.sum[hour]+=float(dev); ++phase.count[hour];}
        }
        if (tod>=600 && tod<960 && (used==0 || block_min[used-1]!=m)) {
            block[used]=value; block_min[used++]=m;
        }
        prev=value; prev_min=m;
        trail[m%30]=value; trail_min[m%30]=m;
        return value-applied;
    }
};
