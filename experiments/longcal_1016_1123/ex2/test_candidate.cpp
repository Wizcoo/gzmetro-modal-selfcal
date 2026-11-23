#include "candidate.hpp"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <type_traits>

int main() {
    static_assert(std::numeric_limits<float>::is_iec559, "float checkpoint format requires IEEE binary32");
    static_assert(std::is_trivially_copyable_v<Candidate>);
    Candidate adapter;
    const double nan = std::numeric_limits<double>::quiet_NaN();
    assert(adapter.predict(0.4, 0.8, 0.3, 1, 0.0) == 0.0);
    assert(adapter.predict(nan, 0.8, 0.3, 4, 0.0) == 0.0);
    assert(adapter.predict(0.4, 0.8, -0.3, 4, 0.0) == 0.0);
    adapter.learn_day(nan, 0.0);
    assert(adapter.endpoint_scale == Candidate::prior_scale && adapter.endpoint_bias == 0.0f);
    const double initial = adapter.predict(0.5, 0.2, 0.2, 10, 0.0);
    for (int i = 0; i < 150; ++i) adapter.learn_day(3.2, 3.0);
    assert(std::abs(adapter.endpoint_bias - 0.2 / 1.2) < 1e-6);
    assert(std::abs(adapter.endpoint_scale - (0.2 + 0.2 * 0.04) / 1.2) < 1e-6);
    assert(adapter.predict(0.5, 0.2, 0.2, 10, 0.0) > initial);
    // Exact state handoff on same ABI. Shared anchor/ring state is owned by the caller.
    std::array<std::uint8_t, sizeof(Candidate)> checkpoint;
    std::memcpy(checkpoint.data(), &adapter, sizeof(adapter));
    Candidate restarted;
    std::memcpy(&restarted, checkpoint.data(), sizeof(restarted));
    for (int i = -100; i < 100; ++i) {
        const double dev = i * 0.03;
        const double amp = 0.25;
        const double before = adapter.predict(dev, 0.20, 0.03, 25, 0.0);
        const double after = adapter.predict(dev + amp, 0.20, 0.03, 25, 0.0);
        assert(before == restarted.predict(dev, 0.20, 0.03, 25, 0.0));
        assert(amp - after + before >= 0.91 * amp - 1e-12);
        assert(std::abs(before) <= 0.09 * std::abs(dev) + 1e-12);
        adapter.learn_day(dev, 0.1);
        restarted.learn_day(dev, 0.1);
    }
    assert(std::memcmp(&adapter, &restarted, sizeof(adapter)) == 0);
    std::cout << "PASS: causal update, regularized optimum, fallback, fixed-state step response, "
                 "same-ABI continuation; candidate bytes=" << sizeof(adapter) << '\n';
}
