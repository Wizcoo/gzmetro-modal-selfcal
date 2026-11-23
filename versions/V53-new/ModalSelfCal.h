#pragma once
// ModalSelfCal V53-new: V53 API with dynamic marker rosters.
#include <cstdint>
#include <limits>
#include <memory>
#include <string>
#include <vector>

namespace gzmetro_msc {

struct ModalSelfCalConfig {
    // ---- 时钟（北京时间；夜内小时：次日 0~12 点记作 24~36，如 26 = 次日 02:00）----
    double tz_offset_h = 8.0;       // 时间戳 Unix 毫秒 → 本地时间的偏移（小时）
    double ref_start_h = 22.0;      // 基准窗起（含）
    double ref_end_h = 23.0;        // 基准窗止（不含）；同时是修正起点
    double learn_end_h = 26.0;      // 学习窗止（不含，次日 02:00）；学习窗 = [ref_start_h, learn_end_h)
    double apply_end_h = 31.0;      // 修正窗止（次日 07:00），之后 ramp_min 分钟内线性退出
    double ramp_min = 20.0;         // 进 / 出斜坡时长（分钟）
    double cadence_s = 60.0;        // 现场帧间隔（秒），只用于估算期望帧数

    // ---- 模态 ----
    int K = 3;                      // 模态阶数
    double guard = 0.5;             // 独占保护阈值：某点在任一模态中能量占比 > guard 即剔出学习集
    double spread_k = 3.0;          // 离散度筛选：标准差 > spread_k × 中位 的点不进学习集（≤0 关闭）
    int history_nights = 3;         // 合并最近几夜的统计求模态
    double min_valid_ratio = 0.8;   // 点在学习窗有效率 ≥ 该值才建模（否则该点原样透传）
    double min_learn_ratio = 0.6;   // 本夜学习窗帧数 ≥ 该比例 × 期望帧数 才收入历史
    int min_ref_frames = 10;        // 点在基准窗内有效帧 ≥ 该值才有基线（否则本夜该点透传）
    int min_valid = 5;              // 单帧参与最小二乘的最少学习点数（实际取 max(min_valid, K+2)）

    // ---- 实时单帧抗差与离群剔除（防止单点突变/跳变污染全局模态反解）----
    double max_frame_residual = 2.5; // 单帧拟合残差门限（mm）：|z_i - A_i v| > 该值时自动剔出求解并重算，<=0 关闭
    double max_frame_dev = 0.0;      // 单帧绝对偏差门限（mm）：|z_i| > 该值时初检直接剔除，<=0 关闭

    // 外接 / 基准点前缀：不参与学模态与求 v，只按回归载荷扣公共项
    std::vector<std::string> fit_only_prefixes = {"YJ", "ZJ"};

    bool enabled = true;            // false：逐帧原样透传，state = DISABLED
};

struct ModalSelfCalFrameInfo {
    int64_t ts_ms = 0;
    std::string state;              // PASSTHROUGH / BASELINE / RAMP / CORRECTING / WAIT_MODES / DEGRADED_FRAME
                                    // / SKIP_BAD_TS / DISABLED / BAD_INPUT
    int64_t night_id = 0;           // 夜号：本地日期的 Unix 天数（20:00–次日 12:00 归同一夜）
    double night_hour = 0.0;        // 夜内小时（见 Config 说明）
    double gate = 0.0;              // 修正门值 0~1
    bool baseline_frozen = false;   // 本夜基线是否已冻结（23:00 后）
    bool modes_ready = false;       // 本夜是否有可用模态
    bool modes_from_tonight = false;// 模态来自本夜（冷启动，02:00 起修正）
    int n_history = 0;              // 历史统计夜数（0~history_nights）
    int n_learn_points = 0;         // 学习点数（剔除 YJ / 离散 / 独占后）
    int n_frame_learn_valid = 0;    // 本帧参与最小二乘的有效学习点数
    int n_corrected = 0;            // 本帧被修正的点数
    double v[3] = {0.0, 0.0, 0.0};  // 本帧模态时间系数（前 3 阶，诊断用）
};

} // namespace gzmetro_msc
using gzmetro_msc::ModalSelfCalConfig;
using gzmetro_msc::ModalSelfCalFrameInfo;

struct ModalSelfCalResumeInfo {
    int64_t last_timestamp_ms = 0; // Resume with the next available real frame after this; gaps allowed.
    int history_x = 0, history_y = 0;
    bool baseline_x = false, baseline_y = false;
    bool modes_x = false, modes_y = false;
};
struct ModalSelfCalResult {
    bool output_ready = false, duplicate = false, replayed = false;
    std::vector<double> x,y,correction_x,correction_y;
    ModalSelfCalFrameInfo info_x,info_y;
};
// The V50 snapshot envelope is retained for V53 compatibility.
// Software owns loading/history/storage/retry. Engine owns MEMORY only.
// No filesystem, database, callbacks, raw-anchor or database consistency checks.
// Same V49 mathematical core and full internal state validation.
class ModalSelfCalState {
public:
    explicit ModalSelfCalState(const ModalSelfCalConfig& = ModalSelfCalConfig());
    ~ModalSelfCalState();
    ModalSelfCalState(const ModalSelfCalState&) = delete;
    ModalSelfCalState& operator=(const ModalSelfCalState&) = delete;

    bool Init(const std::string& device_id, const std::vector<std::string>& names,
              std::string* error = nullptr, bool allow_new_stream = false);
    // One runtime package type for deployment, restart and offline repair.
    // Checks device and math config, then remaps saved axis state by marker name.
    // No extra line/calibration fields or special bootstrap permission.
    bool ImportState(const std::string& bytes, ModalSelfCalResumeInfo* resume,
                     std::string* error = nullptr);
    // Missing observations are allowed; history replay is optional, not required.
    // Invalid arguments leave state unchanged. An internal exception after
    // advancing either axis invalidates the instance; Destroy/Init/Import the
    // last software-committed snapshot before retrying from durable raw data.
    bool Process(int64_t timestamp_ms, const std::vector<double>& raw_x,
                 const std::vector<double>& raw_y, ModalSelfCalResult*,
                 std::string* error = nullptr, bool history_replay = false);
    // Exact bytes incl. NUL. Repeated export without processing is identical.
    // Export does NOT mean software has durably saved anything.
    bool ExportState(std::string* bytes, int64_t* last_timestamp_ms,
                     std::string* error = nullptr) const;
    // MEMORY progress, not proof of database commit. Zero after empty Init.
    bool GetResumeTs(int64_t* last_timestamp_ms, std::string* error = nullptr) const;
    void Destroy(); // No implicit save. Software exports/saves first.
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
