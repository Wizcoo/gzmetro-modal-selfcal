# 左右线 X 影子稳定趋势研究

本目录实现并实际运行 A 温度动态状态、B 事件切换估计、C 独立参考传递、D 因果 L1 趋势、E 宽支持低秩残余五种机制。原监测 X/Y、历史模态核心和告警信息保留；所有新结果只作为独立稳定趋势。**不能把蓝线当作更准确的物理位移或报警输入。**

先读 [实测结论](findings.md)、[算法及失效条件](algorithms.md)、[全点图册](index.html)。[key_and_all_overview.csv](key_and_all_overview.csv) 单独列关键参考/节点，避免普通点平均掩盖问题。最小影子模块见 [XTrendL1.h](scripts/XTrendL1.h) 和 [接入说明](shadow_integration.md)。

## 对照、范围与单位

- 数据为 PR #4 已核验的完整原分辨率包：右线 6 台269点、左线6台255点，2026-11-05 至11-12上午；具体最后时刻见 `input_identity.csv`。无随机抽样。右线11/07下午约71–72分钟缺口，左线11/06至11/07约1615–1617分钟缺口；左线11/06夜缺失，坏尾未知完整性保留原边界。`marker_night_coverage.csv` 连无有效数据的点/夜也列出。
- B0：右线原 V51、左线原 V53，从同一首帧独立冷启动，原源文件和配置不改。两版 cpp 相同、头文件默认配置不同。左线历史现场版本可能不同，不能把固定 V53 冷启动称作整周现场精确复现。
- W3：独立完整历史实例，Raw X 先经过因果3样本中位数再送原核心；Y不经过预处理。无效点/时间缺口重置该点窗口，2样本取均值。W3不是直接滤实存calX。
- A/B/C/D/E：旁路读取 B0 的 X，**不反馈**到任何模态学习、解算、Y或报警。另列 W3→D 消融，白天外层回到B0。W3本身作为历史比较可以改变白天，所有新影子候选白天逐值等于B0。
- 红线数据库实存calX仅作现场观察基线，与独立B0分列，不据此宣称同条件现场A/B。图内只使用有效ROI的实存值。
- X/Y、修正、PV和幅度单位mm；温度°C；时间戳Unix毫秒，图及ISO日期为北京时间。mm依据原接口契约；实际像素落库变换、串联几何和物理真值不可得，不宣称±1pixel或最终X0精度。
- 完整逐夜结果含11/05–11/11；结论主要汇总11/09–11/11三个较后夜，模型只使用当时已完成历史。这些历史已多轮研究，**不是未见新夜的盲验收**。A/C先前夜拟合、再下一已完成夜检验、合格后合并历史拟合；不看当前夜选系数。
- 主评价 `night23_07` 为23:00至次日07:00；另列 `shared_core_active`，要求两个核心均ready、gate=1、实际修正点数>0。晨间07:00–07:20渐出单独检查。真正启用还要求原核心实际状态，不能只按时钟。

## 指标与证据文件

| 文件 | 定义/用途 |
|---|---|
| `metrics/` | 全部点、逐夜、两种scope、全部算法、Raw与实存calX。PV=max−min，P95_P05=Q95−Q05，均不是误差真值。比例先按同一点夜配对，再汇总中位数。 |
| `device_metrics_all.csv` / `device_metrics_focus.csv` | 每设备夜、所有Marker中位及最差点；focus为指定6台的小规模实测，不隐藏其他点。 |
| `key_and_all_overview.csv` / `worst_marker_cases.csv` | all、key(YJ/ZJ/YXJ/ZXJ)、node(YXJ/ZXJ)分别比较，列最坏退化。 |
| `step_P99_mm` | 相邻有效帧绝对变化P99，跨>90秒缺口不连接。 |
| `slow30/60min_change_P99_mm` | 对5分钟**因果均值描述量**作30/60分钟间隔绝对变化P99，不跨缺帧。该均值仅用于指标，不用于显示曲线。 |
| `first_last30_median_delta_mm` | 首/末30分钟中位值之差，持续偏移描述。 |
| `traces/`, `trace_catalog.csv` | 每设备每夜23:00–07:20全部原观测行：Raw、实存、B0、W3、A–E、原Y、gate、ready、状态、事件标志、源DB和rowid。缺失为NaN，不填造观测；拆分文件<2MB。 |
| `plots/`, `plot_catalog.csv` | 524点完整历史、最新整夜及严格消融；重点6台另有8h/60m/10m共18图。灰虚Raw、红实存、蓝D，无显示平滑、插值或重新归零。 |
| `safety/`, `safety_E/` | 所有目标/非目标点注入指标。A–D覆盖12台；E覆盖6台重点设备。观测域增量，不是串联几何投影后的物理运动。 |
| `injection_windows/`, `injection_windows_E/` | 代表性注入的连续全采样配对响应，支持检查延迟、失真和非目标点伪响应。 |
| `admission/`, `models/`, `factor_models/` | 每点独立历史预测资格、模型和E空间载荷；NaN/未合格明确回退。 |
| `thermal_reference_diagnostics.csv` | 当前/15/60分钟滞后温度、温度率、其他参考相关性及独立预测分数；关联不是因果真值。 |
| `night_day_transitions*.csv`, `boundary_checks.csv` | 相对于B0的新增修正量变化，避免把原监测跳变误记为切换伪差。 |
| `protocol*.json`, `L1_*json`, `validation.json` | 参数锁定、源哈希、数值证书、数据/代码/输出回核。`.work`不提交。 |

注入比较 injected−clean，保留B0自身会吸收/传播部分增量的事实；额外损失=候选配对响应与B0配对响应之差。温度+阶跃还用 thermal_step1−thermal_only 单独测量真实已知增量保留。延迟要求连续3帧位于相应稳态幅度±5%，未达到记NaN并统计，不用0掩盖失败。所有原Y逐位一致。告警接口测试使用不透明测试载荷，未取得真实现场告警引擎，不能称作现场告警功能验收。

## 复现

需要Python3.12、numpy/pandas、C++17 g++；画图另需matplotlib和中文字体。版本与编译命令见 `build_provenance.json`。原始DB、PR4派生包、可信本机缓存不重复上传。

先按 [PR4复现说明](../right_x_preprocess/README.md) 建立同哈希的validation原始包/PKL；准备原文清单对应的只读SQLite（温度）及旧右线EnvData缓存。可用环境变量指定缓存：

```powershell
$env:PYTHONUTF8='1'
$env:XS_RAW_CACHE='原PR4缓存目录' # validation_<line>_<device>.bin/.pkl
$env:XS_PR4_REPORT='PR4报告目录' # input_identity_validation.csv/new_source_manifest.json
$env:XS_DATA='E:/Wiz/GZMetro-Cpp/data-sql'
# 默认缓存位置为本研究目录.work；不指向现场状态目录。
python analysis/x_trend_shadow/scripts/prepare.py --exported-environment
# 上项使用已提交的因果温度对齐表，不打开数据库。
# 若需从原DB重新核对环境来源，运行prepare.py（无此开关），并提供上述只读源及旧EnvData缓存。
python analysis/x_trend_shadow/scripts/run_native.py --compile --inject
python analysis/x_trend_shadow/scripts/run_candidates.py
python analysis/x_trend_shadow/scripts/build_l1.py
python analysis/x_trend_shadow/scripts/check_l1_cpp.py
python analysis/x_trend_shadow/scripts/add_trend.py
python analysis/x_trend_shadow/scripts/run_factor.py
python analysis/x_trend_shadow/scripts/merge_factor.py
python analysis/x_trend_shadow/scripts/metrics.py
python analysis/x_trend_shadow/scripts/metrics.py --focus
python analysis/x_trend_shadow/scripts/safety.py
python analysis/x_trend_shadow/scripts/safety_factor.py --focus
python analysis/x_trend_shadow/scripts/summarize_results.py
python analysis/x_trend_shadow/scripts/diagnose.py
python analysis/x_trend_shadow/scripts/visualize.py
python analysis/x_trend_shadow/scripts/export_traces.py
python analysis/x_trend_shadow/scripts/boundary_decomposition.py
python analysis/x_trend_shadow/scripts/demo_and_check_adapter.py
python analysis/x_trend_shadow/scripts/validate_delivery.py --traces
python analysis/x_trend_shadow/scripts/report.py
python analysis/x_trend_shadow/scripts/safety_plots.py
```

`freeze.py`/`--freeze`是本次研究的时间记录；复现不重写为新的“提前冻结”证据。`pilot/`保留早期ABC、ADMM50数值试验；最终D使用有原对偶证书的D-L1-2，窗口和λ规则不因试验结果改变。运行耗时受主机/并发影响，不要求CPU时间或PE构建时间戳相同。

`validate_delivery.py`默认还核对本机原DB/包哈希，所以需要原始只读源；仅算法复现可使用已提交环境表。新数据不在Git，不能声称仅克隆仓库即可重放所有原始输入。`eligible_fraction`表示当前帧满足更新资格，`changed_fraction`表示输出确实不同于B0；A/C/E保持或渐出历史校正时两者可能不同。
