#pragma once
#include "weights.hpp"

#include <algorithm>
#include <array>
#include <cmath>

struct Candidate {
    static constexpr int history_days = 30;

    double predict(double dev, double hist, double spread, int n, double velocity) const {
        if (n < 2 || !std::isfinite(dev) || !std::isfinite(hist) ||
            !std::isfinite(spread) || !std::isfinite(velocity) || spread < 0.0 ||
            dev == 0.0 || hist == 0.0 || std::signbit(dev) != std::signbit(hist)) {
            return 0.0;
        }
        const double direction = std::copysign(1.0, dev);
        const std::array<double, 2> current = {
            std::min(std::abs(dev), 2.0) / 0.8,
            std::clamp(direction * velocity, -1.0, 1.0) / 0.3
        };
        const std::array<double, 3> history = {
            std::min(std::abs(hist), 2.0) / 0.8,
            std::min(spread, 2.0) / 0.8,
            std::min(n, 30) / 30.0
        };
        double logit = dual_stream_weights::p[36];
        for (int j = 0; j < 4; ++j) {
            double local = dual_stream_weights::p[8+j];
            double recurring = dual_stream_weights::p[24+j];
            for (int i = 0; i < 2; ++i) {
                local += current[i] * dual_stream_weights::p[i*4+j];
            }
            for (int i = 0; i < 3; ++i) {
                recurring += history[i] * dual_stream_weights::p[12+i*4+j];
            }
            logit += dual_stream_weights::p[28+j] * std::max(0.0, local);
            logit += dual_stream_weights::p[32+j] * std::max(0.0, recurring);
        }
        const double support = std::min({std::abs(dev), std::abs(hist), 0.8});
        const double gain = 1.0 / (1.0 + std::exp(-std::clamp(logit, -30.0, 30.0)));
        return direction * support * gain;
    }

    void learn_day(double, double) const {}
};
