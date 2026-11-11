# CSV 指标与读取说明

所有时间为北京时间（Asia/Shanghai，UTC+8），窗口 `[2026-11-05 00:00, 2026-11-07 15:00]`。不随机抽样，不插值；CSV 为未压缩 UTF-8。分片保持行序，单文件小于 1.95 MB。原始数字保留在仓库 JSONL；CSV 用约 9 位有效数字呈现诊断数据。

## 分段

`nominal_phase` 按默认钟表：baseline=[22,23)，ramp_in=[23,23:20)，full_correction=[23:20,次日07)，ramp_out=[07,07:20)，daytime=[07:20,22)。阶段是名义分段，实际 gate/modes_ready 缺失，不能等同于真正修正状态。

`phase_key=date|phase|night_date`。night_date 按模块夜号逻辑，中午之前归前一夜，因此同一日 daytime 可在中午拆成两个段；主表另有跨全部日期的 daytime/full 统计，不将它们合成一个连续无缺口序列。11/05 凌晨是 11/04 夜的尾段，也保留。

## 单位与有效性

坐标统计单位 mm，依据状态式共模 API 的毫米契约；本批表的业务写入实现不在手中，详见 pipeline_trace 的单位限制。环境 temp 单位按温度字段解释为 °C，缺少独立校准；其他姿态字段单位未核实，保持原值。`*_r` 是无量纲 Pearson 相关系数，非因果、非传递增益。

上游有效行要求 RoiCalState==1、raw/cal 有限、无冲突业务键；保留零观测，不凭数值为零判无效。相邻差分只用 30–90 秒间隔的真实相邻观测，跨缺口不算一步。下游缺少可验证有效性旗标，统计保留有限值并标出恒零字段/测点；不把恒零点当作精度真值。

## 指标

- `pv_mm`：该段 max−min。`robust_p99_p01_range_mm`：该段 Q99−Q01。均是波动范围，不是准确度误差。
- `baseline_first10min_mm`：该统计段首 10 分钟有效观测的中位数；不是物理真值，不是算法内部22–23点基线。
- `local_offset_abs_p95/p99_mm`：相对上述局部基线偏移绝对值的分位数。不能称为 P99 误差。
- `step_abs_p95/p99/max_mm`：有效相邻帧绝对变化量的分位数/最大值，不跨缺口。
- `trailing31min_residual_abs_p95/p99_mm`：原值减过去31分钟中位数，至少15个点；这是尾随去趋势残差，非测量真误差。
- `drift10/30/60min_abs_p95/p99_mm`：连续段内，过去5分钟中位数之差，比较当前与相隔10/30/60分钟的真实样本（时间容差90秒）；每次中位数至少3个点，缺口重启。表示低频变化，非相邻抖动。
- `sustained5min_offset_abs_max_mm`：过去5分钟中位数相对局部基线的最大绝对偏移；`last10min_minus_first10min_mm` 表示段首尾10分钟中位数差。若段跨多个连续段，注意 gaps 列，不声称真位移。
- correction=raw−cal；`nonzero_correction_fraction` 为绝对修正量>1e−6 mm 的有效观测比例。零修正不能唯一判定模式或 gate 失效。
- `pv_reduction_fraction=1−PV(cal)/PV(raw)`；step reduction 同理。负值表示修正后该波动指标增大。两者均不是最终 x0 精度提升。
- 设备级 `device_median_of_marker_metrics` 是逐 Marker 指标的中位数；`device_common_median` 是逐帧 YD 点相对局部基线后取中位数的轨迹，不能混同。
- 同设备相关性采用排除自身后的其他 YD 点中位数。PCA 仅用该段全部点均有效的完整帧，不补 NaN；列出完整帧数。PC1 比例仅描述协同变化。
- 环境相关采用完全相同时间戳，无近邻硬配。innerTemp 等恒零字段不提供相关系数；sz±180折返的线性相关不用于因果推断。
- 下游 x0/filtered/init 的差分分解见事件：`Δx0 ≈ ΔfilteredX0−ΔinitX`。调整初值的跳变与滤波变化分别报告。

## 文件布局

- `right_x_summary.csv`：设备级与 Marker 级，X/Y 对照，全窗口、白天、名义正式修正三类概览。
- `summaries/*_phase_metrics.partNN.csv`：六设备逐点、逐日期/阶段详细指标（包括修正量、低频、环境与共模相关）。
- `device_phase_metrics.csv`：设备共模轨迹与完整帧 PCA 指标。
- `summaries/downstream_phase_metrics.partNN.csv`：下游各点、逐阶段 x0/y0 指标。
- `continuous_overview/`：六设备全部真实帧的 X/Y 共模轨迹，不是原始逐点证据的替代品。
- `right_x_events.csv`、`right_x_windows/`：典型事件索引与未降采样连续证据；详见 events 方法及各事件注释。
- `marker_device_membership.csv`：真实 Marker 表成员关系，不能当串联所有权表。
- `upstream_downstream_associations.csv`：同名、完全同时间戳候选边，全部候选保留；含水平/差分相关，不能称为敏感度。
- `environment_quality.csv`、`field_identity_checks.csv`、`data_audit.json`：环境可用性、实存字段恒等式与数据组织审计。

JSONL 里的原始源 rowid 和 source_db 仅用于溯源。跨卷去掉完全一致的业务记录（忽略 uin/source_rowid）；若业务键冲突则保留且排除歧义关联。**MarkerData 的 12 个恒零参考点是观测事实，不能算作无误差标签。**
