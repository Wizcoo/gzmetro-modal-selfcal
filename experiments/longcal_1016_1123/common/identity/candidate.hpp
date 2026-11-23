#pragma once
struct Candidate {
    static constexpr int history_days=30;
    void learn_day(double,double) {}
    double predict(double,double,double,int,double) {return 0.;}
};
