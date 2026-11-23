#pragma once
#include <algorithm>
#include <cmath>

// Scalar random-walk filter. One instance per marker and output axis.
struct Candidate {
    static constexpr int history_days = 30;
    static constexpr float prior_variance = 0.09f;
    float bias = 0.f;
    float variance = prior_variance;

    void reset() {
        bias = 0.f;
        variance = prior_variance;
    }

    void learn_day(double last, double anchor) {
        if (std::isfinite(last) && std::isfinite(anchor)) reset();
    }

    double predict(double dev, double hist, double spread, int n, double velocity) {
        if (n < 2 || !std::isfinite(dev) || !std::isfinite(hist) ||
            !std::isfinite(spread) || spread < 0. || !std::isfinite(velocity)) {
            reset();
            return 0.;
        }
        if (std::abs(velocity) >= 0.5) return bias;

        // Historical phase forecast plus a weak, clipped contemporary innovation.
        const double phase = std::clamp(hist, -1., 1.);
        const double innovation = std::clamp(dev - phase, -0.75, 0.75);
        const double confidence = n / (n + 3.) / (1. + spread / 0.5);
        const double observed = confidence * (0.35 * phase + 0.08 * innovation);
        const double predicted_variance = variance + 0.0025;
        const double observation_variance = 0.09 + std::min(spread, 4.) * std::min(spread, 4.);
        const double gain = predicted_variance / (predicted_variance + observation_variance);
        bias = static_cast<float>(bias + gain * (observed - bias));
        variance = static_cast<float>((1. - gain) * predicted_variance);
        return bias;
    }
};
static_assert(sizeof(Candidate) == 8, "ex3 per-channel state must remain 8 bytes");
