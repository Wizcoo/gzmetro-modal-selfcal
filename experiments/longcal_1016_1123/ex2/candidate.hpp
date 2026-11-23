#pragma once

#include <algorithm>
#include <cmath>

// One instance belongs to one device, marker and axis. Units are mm.
struct Candidate {
    static constexpr int history_days = 30;
    static constexpr float prior_scale = 0.04f;
    float endpoint_bias = 0.0f;
    float endpoint_scale = prior_scale;

    // Called once, after a complete daytime block passes the shared quality tests.
    void learn_day(double last, double anchor) {
        if (!std::isfinite(last) || !std::isfinite(anchor)) return;
        const double error = std::clamp(last - anchor, -0.30, 0.30);
        constexpr double eta = 0.10;
        constexpr double lambda = 0.20;
        endpoint_bias += static_cast<float>(eta * (error - (1.0 + lambda) * endpoint_bias));
        endpoint_scale += static_cast<float>(eta * (std::abs(error) - endpoint_scale
                                      - lambda * (endpoint_scale - prior_scale)));
    }

    double predict(double dev, double hist, double spread, int n, double velocity) const {
        if (n < 2 || !std::isfinite(dev) || !std::isfinite(hist) ||
            !std::isfinite(spread) || spread < 0.0 || !std::isfinite(velocity)) return 0.0;
        const double reliability = (n / (n + 4.0)) / (1.0 + spread / 0.35);
        const double repeat = std::clamp(hist + endpoint_bias, -1.50, 1.50);
        const double supported = std::clamp(dev, std::min(0.0, repeat), std::max(0.0, repeat));
        const double noise_band = 3.0 * endpoint_scale;
        const double local = std::clamp(dev, -noise_band, noise_band);
        return reliability * (0.07 * supported + 0.02 * local);
    }
};

static_assert(sizeof(Candidate) == 8, "ex2 state size changed");
