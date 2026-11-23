#include "candidate.hpp"
#include <cassert>
#include <iostream>
#include <limits>
#include <type_traits>

int main() {
    static_assert(std::is_trivially_copyable<Candidate>::value);
    Candidate calm, variable, mirror;
    for (int t=0; t<120; ++t) {
        const double positive = calm.predict(0.48,0.4,0.04,20,0.);
        const double negative = mirror.predict(-0.48,-0.4,0.04,20,0.);
        assert(positive > 0. && positive == -negative);
        assert(variable.predict(0.48,0.4,1.,20,0.) < positive);
    }
    assert(calm.variance > 0 && calm.variance < 0.09f);
    Candidate snapshot = calm;
    for (int t=0; t<200; ++t) {
        const double v=0.1*std::sin(t/12.);
        assert(calm.predict(v,0.18,0.08,10,0.01) ==
               snapshot.predict(v,0.18,0.08,10,0.01));
    }
    const Candidate before_event = calm;
    assert(calm.predict(5.,0.18,0.08,10,1.) == before_event.bias);
    assert(calm.variance == before_event.variance);
    Candidate perturbed = calm;
    for (int t=0; t<100; ++t) {
        const double base = calm.predict(0.1,0.18,0.08,10,0.);
        const double after = perturbed.predict(0.4,0.18,0.08,10,0.);
        assert((0.3 - (after-base))/0.3 >= 0.92);
    }
    assert(calm.predict(0.,0.,0.,1,0.) == 0.);
    assert(calm.variance == Candidate::prior_variance);
    assert(perturbed.predict(std::numeric_limits<double>::quiet_NaN(),0.,0.,10,0.) == 0.);
    mirror.learn_day(0.2,0.1);
    assert(mirror.bias == 0. && mirror.variance == Candidate::prior_variance);
    for (int t=0; t<1000; ++t) {
        const auto b = mirror.predict(100.,90.,0.,30,0.);
        assert(b <= 0.41 && b >= 0.);
    }
    std::cout << "ex3 state tests passed; sizeof(Candidate)=" << sizeof(Candidate) << " B\n";
}
