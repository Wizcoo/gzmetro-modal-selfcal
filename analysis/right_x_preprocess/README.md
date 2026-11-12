# X 前置保形降噪 + 原 V51：阅读与复现

先读 [findings.md](findings.md)，再读 [噪声可辨识性](noise_identifiability.md) 和 [算法推导、状态及失效](preprocessing_algorithms.md)。本目录只含研究脚本与允许分享的派生证据，不改生产源码、配置、状态包，不含部署入口、凭据、新增原库或完整JSONL重复副本。

## 固定实验与数据身份

分支基于 PR3 的 `4ce0ac6c8a99674ffebc0f0f8af699c575da54aa`。B0为原 Raw→V51；B1为N1；B2为αβ；B2ll为轻量因果局部线性对照；B3为保护公共子空间的残差处理。所有分支完整独立运行学习、历史合并及修正，原V51配置完全一致。B4未通过预定独立收益条件，见 `joint_decision.json`。

右线旧数据为原PR1/2/3去重观测，11/05 00:00–11/07 15:00（实际到14:59）。新增右线8/9/10卷接在旧输入后，至11/12 09:59:45.160；左线NewDevice的3–7卷从11/05开始，至11/12 09:41:26.376。右线269点、左线255点，各六设备；不跨设备合并同名YXJ。新版左右线**都用原V51实验核心**，实存calX只是独立观察列，不与冷启动作同条件A/B。

`protocol_frozen.json`、`freeze_record.json`、`implementation_freeze.json`锁定协议、噪声等级和C++算法，分别在11/12 11:36与11:55北京时间、读取新增信号之前完成。原协议字节SHA保留，另有语义SHA支持最终LF规范化；C++在实现锁定后未改。

新数据库部分尾页损坏。只读 immutable、无WAL，先批量读，再逐行补回失败批次中可读记录；可能时作rowid点寻址，不修复原库。右线11/07下午实际缺口约71–72分钟；左线11/06–07约1615–1617分钟，11/06夜完全缺失。损坏尾部不可读总量未知，不编造记录。各点ROI无效/缺测与公共时间缺口分别列在 `observation_quality.csv`、`time_coverage.csv`、`time_gaps.csv`；来源SHA/错误见 `new_source_manifest.json`。去重按实际payload，冲突业务键整体排除，本批为0；重叠卷不重复计数。

发布包不重复放旧阶段的逐点指标：它们已包含在validation完整流的11/05–07前缀，五组pre/cal此前缀逐值核验一致。`key_AB_ratios_old.csv`单独保留开发集对照。脚本重建产生的old重复中间表及内部report_facts不提交，审查目录以artifact_catalog.csv为准。

## 单位、范围和指标字典（适用于全部CSV）

- 全部文本UTF-8、未压缩；原毫秒时间戳与北京时间ISO+08:00并列，连续证据不随机抽样、不插值、不填补缺口。大表按确定的顺序拆part，单文件<2 MB。
- X/Y、raw/pre/cal、修正量、RMSE、范围、步差、漂移均为 **mm（V51输入契约，实际落库变换未取得）**；噪声σ也是mm。ratio/retained_fraction/相关/能量为无量纲；耗时`us`为微秒；时间`seconds/minutes/frames`按列后缀；模态夹角为degrees。center/scale仅保留原域，**未确认其是毫米、世界坐标或实际换算系数**。
- `date=11/07,phase=night`指11/07 23:20至11/08 07:00，左闭右开；day为同日07:20–22:00。11/12 day仅覆盖已有上午。`native_window`保留整窗，包括未形成模式的帧；`same_B0_active`只取B0 gate>0且n_corrected>0的同一时间集合。冷启动首夜02点前等待模式不能混成正式修正效果。完整回放仍包含所有基线、渐入、渐出和白天帧。
- `LF_Q95_Q05_mm`为连续段上5分钟**尾随**中位数的Q95−Q05，最少3点，超过90秒断段。`step_abs_P99_mm`仅用间隔30–90秒的相邻有效步。10/30/60分钟漂移为上述低频轨迹的时间差绝对值P99，最近匹配容差90秒且不跨缺口。PV是原序列max−min；首末30分钟中位差是有符号持续偏移代理。它们都不是物理“P99误差”。
- 修正量分别 `raw-pre` 与 `pre-cal`，相加等于raw-cal。V51实际公式为 `cal=pre-gate*(ΣA_k v_k-cbar)`。每组A不同，v轴可能旋转；不能跨基底直接比较单个v数值的物理意义。
- 已知噪声测试为三档固定σ独立Gaussian，seed及点序写入`input_identity_*`；每组从头重建自身含噪历史。比较`cal(x+ε)-cal(x)`的RMSE，再除B0对应量。完整点统计跨夜按样本数合并平方量后开方；`noise_night_overview`保留逐夜分布，防止合并掩盖失败。这不是物理精度。
- 波形注入均为**观测域**，没有经过真实串联几何投影。旧回放03点分叉为11/06与11/07，新增为11/08与11/12；每组复制自己的完整预处理和V51内存，从03–07点续跑。噪声实验不是这种快照续跑，而是完整全历史重建。
- 阶跃1/3mm、节点1mm/1小时与3mm/3小时斜坡、每隔一个点的多点变化、第一原模态方向（关键点最大载荷归一）、单/重复脉冲、单/多参考异常、缺失10帧及反向连续跳变均列出。333715无YJ/YXJ，不计作零误差通过；其普通点及Y/有效性/全点传播仍完整运行。
- 稳定段为06:30–07:00；保留率=同方法注入减未注入的稳定段中位数/已知输入中位数。斜率在斜坡持续期按真实时间拟合；`ramp_equivalent_lag_seconds`仅为截距/斜率折算，不是独立物理时延。峰值偏差、正负超调及完整波形RMSE另列。
- `delay95_frames`从计划注入起算，要求连续5帧处于已知量95–105%。`first_valid_delay_frames`与`delay95_after_first_valid_frames`分离首段缺失，`delay95_delta_vs_B0_frames`作相同输入的原V51对照。时间秒列使用实际时间。中途缺失仍影响连续5帧要求；B0也可能有非零等待，**不能全部归咎滤波延迟**。最终幅度未到达、无持续非零阶跃或斜坡不适用时留空，不是0帧通过。
- `extra_nontarget_key`先逐帧计算候选配对响应减B0配对响应，再对未注入的关键点取最大绝对值；`injection_non_target`是全点配对最大量，包含原有传播。脉冲不能用末段0/0保留率；其峰值、波形及非目标量都保留。
- 0.9–1.1幅度、5帧、0.1mm额外传播、10%波动退化是本研究筛选线，**不是已经取得的现场容差**。

## 文件入口

| 文件 | 对应证据与范围 |
| --- | --- |
| `comparison_overview.csv`, `heldout_key_AB.csv`, `key_AB_ratios_*` | 全部关键通道逐夜和汇总；right新增11/07–11/11、left11/05及11/07–11/11；old为11/05与11/06 |
| `full_metrics/`, `key_chain_metrics_*` | 每设备、全部Marker、昼夜、raw/现场观察及五组pre/cal；范围按stage/date列，部分窗如实计数 |
| `old_noise_components`, `old_spatial_common`, `old_frequency_components` | 仅旧右线开发集；频带、公共关联和随机样证据；各行含分段或起止时间 |
| `noise_sensitivity_*`, `noise_night_overview` | 三档已知噪声全历史重建；完整逐点及逐夜分布，含普通点对照 |
| `waveforms/`, `signal_safety_overview`, `extra_nontarget_key*`, `injection_non_target_*` | 全部已知形态及参考/失效测试，所有关键点、所有候选，区分pre与cal层 |
| `mode_stability_*`, `mode_trace_windows*`, `coverage_runtime_*`, `runtime_overview` | 独立模态/学习变化、事件逐帧v/逐阶贡献及实际资格、退化与计算代价 |
| `event_index.csv`, `windows/`, `figures/` | 五个最差代表性完整夜，外加阶跃/斜坡/脉冲/多点传播/缺失四小时时序；五张图，含Raw/pre/cal三层 |
| `N1_changed_observations.csv` | 正常完整回放实际触发的全部N1记录；旧集为0，新增仅一个普通点 |
| `input_identity_*`, `new_source_manifest`, `time_*`, `observation_quality` | 数据身份、去重、损坏/缺口/有效性；完整源库不上传 |
| `validation.json`, `mode_metric_validation.json`, `artifact_catalog.csv` | 数据/代码/Y/公式/独立指标核验与审查目录SHA |

## 复现（仓库根目录，派生缓存均在研究目录.work）

需要Python3.12、numpy/pandas、C++17 g++；绘图需要matplotlib及中文字体。数值版本及编译参数见`build_provenance.json`。图表另用本机已有matplotlib环境；结果通过固定二进制/CSV交换。

```powershell
$env:NP_REPO=(Get-Location).Path
$env:NP_OUTPUT=Join-Path $env:NP_REPO 'analysis/right_x_preprocess'
$env:NP_WORK=Join-Path $env:NP_OUTPUT '.work'
$env:NP_DATA='E:/Wiz/GZMetro-Cpp/data-sql'
$env:NP_OLD_CACHE=Join-Path $env:NP_REPO 'analysis/right_x/.cache'
$env:NP_OLD_WORK=Join-Path $env:NP_REPO 'analysis/right_x_enhancement/.work'
$env:PYTHONUTF8='1'
$env:NP_CXX='C:/msys64/ucrt64/bin/g++.exe'
python analysis/right_x/scripts/load_data.py
python analysis/right_x_preprocess/scripts/build.py
python analysis/right_x_preprocess/scripts/prepare_inputs.py --stage old
python analysis/right_x_preprocess/scripts/run.py --stage old
python analysis/right_x_preprocess/scripts/summarize.py --stage old
# old_noise与PR3精确基线核对需前轮缓存；可按PR3 README重建final。
python analysis/right_x_preprocess/scripts/old_noise.py
python analysis/right_x_preprocess/scripts/prepare_inputs.py --stage validation
python analysis/right_x_preprocess/scripts/run.py --stage validation
python analysis/right_x_preprocess/scripts/summarize.py --stage validation
python analysis/right_x_preprocess/scripts/diagnostics.py
python analysis/right_x_preprocess/scripts/review.py
python analysis/right_x_preprocess/scripts/signal_audit.py
python analysis/right_x_preprocess/scripts/report_facts.py
python analysis/right_x_preprocess/scripts/figures_and_windows.py
python analysis/right_x_preprocess/scripts/mode_and_metric_audit.py
python analysis/right_x_preprocess/scripts/quality.py
python analysis/right_x_preprocess/scripts/runtime_full.py
python analysis/right_x_preprocess/scripts/audit.py
python analysis/right_x_preprocess/scripts/evidence_audit.py
python analysis/right_x_preprocess/scripts/package.py
```

新数据不在Git中，需具备同身份只读SQLite，源码/协议/算法SHA由脚本强制检查。数值重算应复现；CPU、编译PE时间戳和环境路径不要求字节相同。报告与冻结记录不是运行脚本后自动升级的上线许可。没有匹配现场状态，故现场实存calX也不要求等于B0；没有串联接口/几何和独立位移真值，本轮不提供候选X0或物理精度宣称。
