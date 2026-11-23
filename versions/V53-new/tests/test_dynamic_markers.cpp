#include "ModalSelfCal.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace {

using Roster = std::vector<int>;
const Roster old_points{0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
const Roster all_points{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11};
constexpr char device[] = "v53-dynamic-marker-test";
constexpr int added_night = 3;
constexpr int learn_end = 240;  // 02:00, minutes since 22:00.
constexpr double tolerance = 1e-8;

void Require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

#define CHECK(condition) Require((condition), std::string(#condition) + " at line " + std::to_string(__LINE__))

int64_t Timestamp(int night, int minute) {
    return (20000LL + night) * 86400000 + 14LL * 3600000 + minute * 60000LL;
}

ModalSelfCalConfig Config() {
    ModalSelfCalConfig config;
    config.cadence_s = 300;
    return config;
}

std::vector<std::string> Names(const Roster& roster) {
    std::vector<std::string> names;
    for (int point : roster) names.push_back("P" + std::to_string(point));
    return names;
}

struct Frame {
    std::vector<double> x, y;
};

Frame Raw(const Roster& roster, int night, int minute) {
    Frame frame;
    for (int point : roster) {
        const double angle = point * 0.5235987755982988;
        const double a = std::cos(angle);
        const double b = std::sin(angle);
        const double c = 0.6 + (point % 4) * 0.12;
        const double t = minute * 0.037;
        frame.x.push_back(3.0 + point + night * 0.125 +
                          a * std::sin(t) + b * std::cos(0.7 * t) + c * std::sin(0.4 * t));
        frame.y.push_back(-2.0 - point + night * 0.25 +
                          a * std::cos(0.9 * t) + b * std::sin(1.1 * t) + c * std::cos(0.3 * t));
    }
    return frame;
}

void Init(ModalSelfCalState& engine, const Roster& roster, bool fresh = false,
          const char* id = device) {
    std::string error;
    if (!engine.Init(id, Names(roster), &error, fresh)) throw std::runtime_error(error);
}

ModalSelfCalResult Process(ModalSelfCalState& engine, int night, int minute, const Frame& raw) {
    ModalSelfCalResult result;
    std::string error;
    if (!engine.Process(Timestamp(night, minute), raw.x, raw.y, &result, &error))
        throw std::runtime_error(error);
    CHECK(result.output_ready && !result.duplicate && !result.replayed);
    return result;
}

ModalSelfCalResult Step(ModalSelfCalState& engine, const Roster& roster, int night, int minute) {
    return Process(engine, night, minute, Raw(roster, night, minute));
}

std::string Export(ModalSelfCalState& engine, int night, int minute) {
    int64_t timestamp = 0;
    std::string snapshot, error;
    if (!engine.ExportState(&snapshot, &timestamp, &error)) throw std::runtime_error(error);
    CHECK(timestamp == Timestamp(night, minute));
    return snapshot;
}

#ifdef MSC_GENERATE_V53_FIXTURES

// Build with the original V53 translation unit and this macro to regenerate the fixtures.
void Write(const std::filesystem::path& path, const std::string& bytes) {
    std::ofstream file(path, std::ios::binary);
    file.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    Require(static_cast<bool>(file), "Could not write " + path.string());
}

void GenerateFixtures(const std::filesystem::path& directory) {
    std::filesystem::create_directories(directory);
    ModalSelfCalState legacy(Config());
    Init(legacy, old_points, true);
    for (int night = 0; night < 3; ++night) {
        for (int minute = 0; minute <= 270; minute += 5) {
            Step(legacy, old_points, night, minute);
            if (night == 0 && minute == 250)
                Write(directory / "cold_ramp_v53.state", Export(legacy, night, minute));
        }
    }
    Write(directory / "history_v53.state", Export(legacy, 2, 270));
}

#else

std::string Read(const std::filesystem::path& path) {
    std::ifstream file(path, std::ios::binary);
    Require(static_cast<bool>(file), "Could not open fixture " + path.string());
    return std::string(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
}

ModalSelfCalResumeInfo Import(ModalSelfCalState& engine, const std::string& snapshot) {
    ModalSelfCalResumeInfo resume;
    std::string error;
    if (!engine.ImportState(snapshot, &resume, &error)) throw std::runtime_error(error);
    return resume;
}

void Near(double actual, double expected) {
    Require(std::abs(actual - expected) <= tolerance, "Expected " + std::to_string(expected) +
            ", got " + std::to_string(actual));
}

void CheckPoint(const ModalSelfCalResult& result, const Frame& raw, const Frame& baseline,
                std::size_t i, double gate) {
    Near(result.x[i], raw.x[i] - gate * (raw.x[i] - baseline.x[i]));
    Near(result.y[i], raw.y[i] - gate * (raw.y[i] - baseline.y[i]));
}

Frame Baseline(const Roster& roster, int night) {
    Frame mean{std::vector<double>(roster.size()), std::vector<double>(roster.size())};
    for (int minute = 0; minute < 60; minute += 5) {
        const auto raw = Raw(roster, night, minute);
        for (std::size_t i = 0; i < roster.size(); ++i) {
            mean.x[i] += raw.x[i];
            mean.y[i] += raw.y[i];
        }
    }
    for (double& x : mean.x) x /= 12;
    for (double& y : mean.y) y /= 12;
    return mean;
}

void CheckUnchanged(const ModalSelfCalResult& a, const ModalSelfCalResult& b, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i) {
        CHECK(a.x[i] == b.x[i] && a.y[i] == b.y[i]);
        CHECK(a.correction_x[i] == b.correction_x[i] && a.correction_y[i] == b.correction_y[i]);
    }
    CHECK(a.info_x.state == b.info_x.state && a.info_y.state == b.info_y.state);
    CHECK(a.info_x.gate == b.info_x.gate && a.info_y.gate == b.info_y.gate);
    for (int k = 0; k < 3; ++k) {
        CHECK(a.info_x.v[k] == b.info_x.v[k] && a.info_y.v[k] == b.info_y.v[k]);
    }
}

void TestAdd(const std::string& snapshot) {
    ModalSelfCalState reference(Config()), expanded(Config());
    Init(reference, old_points);
    Init(expanded, all_points);
    Import(reference, snapshot);
    Import(expanded, snapshot);
    const auto baseline = Baseline(all_points, added_night);
    for (int minute = 0; minute <= 270; minute += 5) {
        auto expected = Step(reference, old_points, added_night, minute);
        const auto raw = Raw(all_points, added_night, minute);
        auto actual = Process(expanded, added_night, minute, raw);
        CheckUnchanged(actual, expected, old_points.size());
        if (minute < 60) CHECK(actual.info_x.state == "BASELINE");
        if (minute >= 65) {
            CHECK(actual.info_x.n_learn_points == 10 && actual.info_y.n_learn_points == 10);
            const int n_corrected = minute <= learn_end ? 10 : 12;
            CHECK(actual.info_x.n_corrected == n_corrected && actual.info_y.n_corrected == n_corrected);
        }
        const double gate = std::clamp((minute - learn_end) / 20.0, 0.0, 1.0);
        for (std::size_t i = 10; i < 12; ++i) {
            if (minute <= learn_end) CHECK(actual.x[i] == raw.x[i] && actual.y[i] == raw.y[i]);
            CheckPoint(actual, raw, baseline, i, gate);
        }
    }

    const int next_night = added_night + 1;
    for (int minute = 0; minute <= 60; minute += 5) Step(expanded, all_points, next_night, minute);
    const auto next_baseline = Baseline(all_points, next_night);
    const auto ramp_raw = Raw(all_points, next_night, 65);
    const auto ramp = Process(expanded, next_night, 65, ramp_raw);
    CHECK(ramp.info_x.n_corrected == 12 && ramp.info_y.n_corrected == 12);
    for (std::size_t i = 10; i < all_points.size(); ++i)
        CheckPoint(ramp, ramp_raw, next_baseline, i, 0.25);

    const auto actual = Step(expanded, all_points, next_night, 80);
    CHECK(actual.info_x.n_history == 3 && actual.info_y.n_history == 3);
    CHECK(actual.info_x.n_learn_points == 12 && actual.info_y.n_learn_points == 12);
    CHECK(actual.info_x.n_corrected == 12 && actual.info_y.n_corrected == 12);
    const auto next_raw = Raw(all_points, next_night, 80);
    for (std::size_t i = 0; i < all_points.size(); ++i)
        CheckPoint(actual, next_raw, next_baseline, i, 1.0);
}

void CheckWait(const ModalSelfCalResult& result, const Frame& raw) {
    CHECK(result.info_x.state == "WAIT_MODES" && result.info_y.state == "WAIT_MODES");
    CHECK(result.info_x.n_corrected == 0 && result.info_y.n_corrected == 0);
    CHECK(result.x == raw.x && result.y == raw.y);
}

void TestRemove(const std::string& snapshot) {
    const Roster retained{9, 0, 2, 3, 4, 6, 7, 8};
    ModalSelfCalState reduced(Config());
    Init(reduced, retained);
    Import(reduced, snapshot);
    for (int minute = 0; minute <= 60; minute += 5) Step(reduced, retained, added_night, minute);
    auto actual = Step(reduced, retained, added_night, 90);
    CHECK(actual.info_x.n_corrected == 8 && actual.info_y.n_corrected == 8);
    for (std::size_t i = 0; i < retained.size(); ++i)
        CheckPoint(actual, Raw(retained, added_night, 90), Baseline(retained, added_night), i, 1.0);

    const Roster insufficient{9, 0, 2, 3};
    const auto during_learning = Export(reduced, added_night, 90);
    reduced.Destroy();
    Init(reduced, insufficient);
    const auto resume = Import(reduced, during_learning);
    CHECK(resume.baseline_x && resume.baseline_y && !resume.modes_x && !resume.modes_y);
    auto raw = Raw(insufficient, added_night, 95);
    CheckWait(Process(reduced, added_night, 95, raw), raw);
    raw = Raw(insufficient, added_night, 265);
    CheckWait(Process(reduced, added_night, 265, raw), raw);

    const Roster replacement{9, 0, 2, 3, 10, 11};
    ModalSelfCalState recovering(Config());
    Init(recovering, replacement);
    Import(recovering, snapshot);
    for (int minute = 0; minute <= 265; minute += 5) {
        const auto input = Raw(replacement, added_night, minute);
        actual = Process(recovering, added_night, minute, input);
        if (minute > 60 && minute < learn_end) CheckWait(actual, input);
        if (minute == learn_end) {
            CHECK(actual.x == input.x && actual.y == input.y);
            CHECK(actual.info_x.modes_from_tonight && actual.info_y.modes_from_tonight);
        }
    }
    CHECK(actual.info_x.n_corrected == 6 && actual.info_y.n_corrected == 6);
    for (std::size_t i = 0; i < replacement.size(); ++i)
        CheckPoint(actual, Raw(replacement, added_night, 265), Baseline(replacement, added_night), i, 1.0);
}

void TestMissing(const std::string& snapshot) {
    ModalSelfCalState reference(Config()), missing(Config());
    Init(reference, old_points);
    Init(missing, old_points);
    Import(reference, snapshot);
    Import(missing, snapshot);
    constexpr std::size_t kMissing = 4;
    for (int minute = 0; minute <= 270; minute += 5) {
        auto expected = Step(reference, old_points, added_night, minute);
        auto raw = Raw(old_points, added_night, minute);
        raw.x[kMissing] = raw.y[kMissing] = std::numeric_limits<double>::quiet_NaN();
        auto actual = Process(missing, added_night, minute, raw);
        CHECK(std::isnan(actual.x[kMissing]) && std::isnan(actual.y[kMissing]));
        CHECK(std::isnan(actual.correction_x[kMissing]) && std::isnan(actual.correction_y[kMissing]));
        for (std::size_t i = 0; i < old_points.size(); ++i) {
            if (i == kMissing) continue;
            Near(actual.x[i], expected.x[i]);
            Near(actual.y[i], expected.y[i]);
        }
        if (minute >= 65) {
            CHECK(actual.info_x.n_frame_learn_valid == 9 && actual.info_y.n_frame_learn_valid == 9);
            CHECK(actual.info_x.n_corrected == 9 && actual.info_y.n_corrected == 9);
        }
    }
}

void TestRestart(const std::string& snapshot) {
    ModalSelfCalState uninterrupted(Config()), resumed(Config()), reordered(Config());
    Init(uninterrupted, all_points);
    Import(uninterrupted, snapshot);
    for (int minute = 0; minute <= 250; minute += 5)
        Step(uninterrupted, all_points, added_night, minute);
    const auto during_ramp = Export(uninterrupted, added_night, 250);
    const std::string gates = "\npoint_apply_from_h=23,23,23,23,23,23,23,23,23,23,26,26\n";
    const auto first_gate = during_ramp.find(gates);
    CHECK(first_gate != std::string::npos && during_ramp.find(gates, first_gate + 1) != std::string::npos);
    Init(resumed, all_points);
    const auto resume = Import(resumed, during_ramp);
    CHECK(resume.last_timestamp_ms == Timestamp(added_night, 250) && resume.modes_x && resume.modes_y);
    CHECK(Export(resumed, added_night, 250) == during_ramp);

    auto reverse = all_points;
    std::reverse(reverse.begin(), reverse.end());
    Init(reordered, reverse);
    Import(reordered, during_ramp);
    for (int minute : {251, 255, 260, 265, 300, 540, 550, 565}) {
        auto expected = Step(uninterrupted, all_points, added_night, minute);
        auto actual = Step(resumed, all_points, added_night, minute);
        CheckUnchanged(actual, expected, all_points.size());
        CHECK(actual.info_x.n_corrected == expected.info_x.n_corrected);
        CHECK(actual.info_y.n_corrected == expected.info_y.n_corrected);
        auto reversed = Step(reordered, reverse, added_night, minute);
        for (std::size_t i = 0; i < reverse.size(); ++i) {
            Near(reversed.x[i], expected.x[reverse[i]]);
            Near(reversed.y[i], expected.y[reverse[i]]);
        }
    }
    CHECK(Export(resumed, added_night, 565) == Export(uninterrupted, added_night, 565));
}

void TestLegacy(const std::string& snapshot, const std::string& cold) {
    CHECK(snapshot.find("point_apply_from_h=") == std::string::npos);
    CHECK(cold.find("point_apply_from_h=") == std::string::npos);
    ModalSelfCalState engine(Config());
    Init(engine, old_points);
    auto wrong_checksum = snapshot;
    wrong_checksum.back() ^= 1;
    ModalSelfCalResumeInfo resume;
    std::string error;
    CHECK(!engine.ImportState(wrong_checksum, &resume, &error));
    CHECK(error.find("checksum") != std::string::npos);

    ModalSelfCalState other_device(Config());
    Init(other_device, old_points, false, "other-device");
    CHECK(!other_device.ImportState(snapshot, &resume, &error));
    CHECK(error.find("device") != std::string::npos);
    auto other_config = Config();
    other_config.max_frame_dev = 8.0;
    ModalSelfCalState other_parameters(other_config);
    Init(other_parameters, old_points);
    CHECK(!other_parameters.ImportState(snapshot, &resume, &error));
    CHECK(error.find("math parameters") != std::string::npos);

    resume = Import(engine, snapshot);
    CHECK(resume.history_x == 3 && resume.history_y == 3);
    CHECK(resume.last_timestamp_ms == Timestamp(2, 270) && resume.modes_x && resume.modes_y);
    auto actual = Step(engine, old_points, 2, 275);
    for (std::size_t i = 0; i < old_points.size(); ++i)
        CheckPoint(actual, Raw(old_points, 2, 275), Baseline(old_points, 2), i, 1.0);

    engine.Destroy();
    Init(engine, old_points);
    resume = Import(engine, cold);
    CHECK(resume.last_timestamp_ms == Timestamp(0, 250) && resume.history_x == 1 && resume.history_y == 1);
    actual = Step(engine, old_points, 0, 255);
    CHECK(actual.info_x.modes_from_tonight && actual.info_y.modes_from_tonight);
    Near(actual.info_x.gate, 0.75);
    Near(actual.info_y.gate, 0.75);
    for (std::size_t i = 0; i < old_points.size(); ++i)
        CheckPoint(actual, Raw(old_points, 0, 255), Baseline(old_points, 0), i, 0.75);
}

void TestAttachmentLimits(const std::string& snapshot) {
    ModalSelfCalState expanded(Config());
    Init(expanded, all_points);
    Import(expanded, snapshot);
    for (int minute = 0; minute < learn_end; minute += 5) {
        auto raw = Raw(all_points, added_night, minute);
        const double nan = std::numeric_limits<double>::quiet_NaN();
        if (minute < 10) raw.x[10] = raw.y[10] = nan;
        if (minute < 15) raw.x[11] = nan;
        if (minute >= 60 && minute < 125) raw.y[11] = nan;
        Process(expanded, added_night, minute, raw);
    }
    const auto raw = Raw(all_points, added_night, 265);
    auto actual = Process(expanded, added_night, 265, raw);
    const auto baseline = Baseline(all_points, added_night);
    // First close is 02:25; the eligible point starts its own ramp at that frame.
    CHECK(actual.info_x.n_corrected == 10 && actual.info_y.n_corrected == 10);
    CHECK(actual.x[10] == raw.x[10] && actual.y[10] == raw.y[10]);
    const auto subsequent = Raw(all_points, added_night, 275);
    const auto halfway = Process(expanded, added_night, 275, subsequent);
    const auto full = Process(expanded, added_night, 290, subsequent);
    CHECK(halfway.info_x.n_corrected == 11 && halfway.info_y.n_corrected == 11);
    CheckPoint(halfway, subsequent, baseline, 0, 1.0);
    CHECK(std::abs(full.correction_x[10]) > 0.01 && std::abs(full.correction_y[10]) > 0.01);
    Near(halfway.correction_x[10], 0.5 * full.correction_x[10]);
    Near(halfway.correction_y[10], 0.5 * full.correction_y[10]);
    CHECK(halfway.x[11] == subsequent.x[11] && halfway.y[11] == subsequent.y[11]);
    // The attached point's correction is centered on only its valid reference samples.
    double sum_x = 0.0, sum_y = 0.0;
    for (int ref_minute = 10; ref_minute < 60; ref_minute += 5) {
        const auto ref = Raw(all_points, added_night, ref_minute);
        const auto sample = Process(expanded, added_night, 300 + ref_minute, ref);
        sum_x += sample.correction_x[10];
        sum_y += sample.correction_y[10];
    }
    Near(sum_x, 0.0);
    Near(sum_y, 0.0);

    expanded.Destroy();
    Init(expanded, all_points);
    Import(expanded, snapshot);
    // Constant learning points yield a singular tonight covariance, even with historical modes.
    const auto flat = Raw(all_points, added_night, 0);
    for (int minute = 0; minute < learn_end; minute += 5) {
        auto frame = Raw(all_points, added_night, minute);
        std::copy_n(flat.x.begin(), old_points.size(), frame.x.begin());
        std::copy_n(flat.y.begin(), old_points.size(), frame.y.begin());
        Process(expanded, added_night, minute, frame);
    }
    Step(expanded, all_points, added_night, learn_end);
    actual = Process(expanded, added_night, 265, raw);
    CHECK(actual.info_x.n_corrected == 10 && actual.info_y.n_corrected == 10);
    for (std::size_t i = 10; i < all_points.size(); ++i)
        CHECK(actual.x[i] == raw.x[i] && actual.y[i] == raw.y[i]);

    expanded.Destroy();
    Init(expanded, all_points);
    Import(expanded, snapshot);
    for (int minute = 0; minute < learn_end; minute += 5)
        Step(expanded, all_points, added_night, minute);
    // When the first close falls in the exit ramp, attached points still enter from zero.
    actual = Process(expanded, added_night, 545, raw);
    CHECK(actual.info_x.n_corrected == 10 && actual.info_y.n_corrected == 10);
    CheckPoint(actual, raw, baseline, 10, 0.0);
    actual = Process(expanded, added_night, 550, raw);
    CHECK(actual.info_x.n_corrected == 12 && actual.info_y.n_corrected == 12);
    CheckPoint(actual, raw, baseline, 0, 0.5);
    CheckPoint(actual, raw, baseline, 10, 0.25);
}

#endif

}  // namespace

int main(int argc, char** argv) {
    try {
#ifdef MSC_GENERATE_V53_FIXTURES
        Require(argc == 2, "Expected a fixture output directory");
        GenerateFixtures(argv[1]);
        std::cout << "V53 fixtures generated\n";
#else
        Require(argc == 3, "Expected a test case and a fixture directory");
        const std::string test = argv[1];
        const std::filesystem::path fixtures = argv[2];
        const auto snapshot = Read(fixtures / "history_v53.state");
        if (test == "add") TestAdd(snapshot);
        else if (test == "remove") TestRemove(snapshot);
        else if (test == "missing") TestMissing(snapshot);
        else if (test == "restart") TestRestart(snapshot);
        else if (test == "legacy") TestLegacy(snapshot, Read(fixtures / "cold_ramp_v53.state"));
        else if (test == "attachment_limits") TestAttachmentLimits(snapshot);
        else throw std::runtime_error("Unknown test case " + test);
        std::cout << "PASS " << test << '\n';
#endif
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
