# 右线 X 模态增强研究

阅读顺序：[候选推导](algorithm_candidates.md) → [证据排序及结论](ranking.md) → ablation_results.csv / injection_results.csv。父版本为 PR #2 `799d71d011aa16396913675de716d47eb80dfc1f`。这是两夜已探索数据上的开发与历史验证，不是新夜验收。

## 数据和指标

窗口：北京时间2026-11-05 00:00至11-07 15:00，实际末条14:59；六设备全部原始点进入同样的原始V51历史。RoiCalState==1及有限值才作为有效观测，其他为NaN；没有随机抽样、插值、重复计数或把白天当真值。

269个点全部参与回放；重点逐项报告14路YJ和6路YXJ。333715没有本地YJ/YXJ，仍完整回放并检查其系数/有效性/Y；不能为它编造参考点。五个YXJ名称的两个YXJ6观察通道分开。

ablation_results每行是设备×点×夜×方法×评价窗口：

- `nominal_core_including_cold_wait`：23:20–07:00全部有效目标观测，包括第一夜等待模态。
- `same_original_active_frames`：相同窗口内，仅原始V51真正有修正输出的帧，所有候选使用同样集合。第一夜约02:01起；第二夜按实际状态，不把名义夜窗冒充运行状态。LOPO还另报原始V51在其相同行的对照，不能与不同行数结果直接比较。
- `LF_Q95_Q05_mm`：5分钟尾随中位数的Q95−Q05，至少3个实际样本，>90秒缺口重启。
- `drift10/30/60min_abs_P99_mm`：上述5分钟信号的相应时间差绝对值P99；过去真实时刻最近匹配容差90秒，须在同连续段。不是P99误差。
- `step_abs_P99_mm`：30–90秒真实相邻有效帧差绝对值P99。
- `persistent_offset_first_last_30min_mm`：末30分钟与首30分钟中位数之差。
- `max_abs_5min_offset_from_first30min_mm`、`longest_5min_offset_over1mm_duration_min`：相对该评价窗首30分钟中位数的最大5分钟偏移，以及超过1 mm的最长真实连续时长。1 mm是描述阈值，不是物理精度标准。
- raw/cal/候选/修正量按共模API的毫米契约；数据库业务写入映射未独立核验。v为已归一化模态基中的系数，Ai无量纲；都不是最终云位移。相关/保留率/权重无量纲。centerX/Y仍为未核实原生配置单位。

`V51_field_observed`是现场实存calX，独立观察基线，**不得用于计算冷启动候选的同条件收益**。同条件基线仅`V51`；identity只作逐位执行控制。

## 注入与时延

两夜各自03点前从已运行状态分叉，原V51、每候选及其额外context一起复制；所有注入在02点学习结束后，无重新拟合。每个目标名字分别有1/3 mm阶跃，另有1 mm/1h、3 mm/3h斜坡、同名YXJ6双观察、单/多YJ异常、参考与目标同型变化、高杠杆学习点异常/尖峰、已知模态形状变化、10分钟参考/学习点失效恢复及YXJ5 Y向−1 mm。共28类，含该设备不存在目标时的零注入控制。

全部是**观测坐标域已知输入**，缺少真实标定/串联几何，不能称为已投影的世界位移。阶跃和斜坡稳定段为06:30–07:00。保留率=(注入输出−同方法未注入输出)/已知输入；0为抵消，负值反向，>1放大。脉冲另外报告峰值，不能用稳定段0/0算保留率。

- `injection_results.csv`：每设备/方法/场景的所有非目标点最大伪响应，以及关键非目标点最大伪响应。
- `injection_YXJ_channels.csv`、`injection_YJ_2026-11-06.csv`、`injection_YJ_2026-11-07.csv`：逐目标/非目标关键通道的完整矩阵，日期为注入日，分别对应11/05和11/06夜。
- `additional_key_fault_propagation.csv`：逐帧计算“候选注入响应−原V51注入响应”后取非目标关键点最大值，**不是两个最大值相减**。
- `coefficient_delay_diagnostics.csv`：真实序列0–5帧滞后代理，以及已知模态形状阶跃相对原模型最终系数增量的95%响应，需连续5帧满足。无可辨识输入标记缺失，333715无关键点因而该特定归一化模态注入未定义，不计作0帧通过。
- 逐点`step_95pct_retention_delay_frames`是该点达到已知输入95%的时间，若最终保留不足则留空；它不能代替系数时序估计器的延迟。

冻结方案中的0.9–1.1保留区间、0.1 mm附加传播和10%低频退化是本研究的筛选线，未经现场物理验收，不是项目正式容差。原V51本身在部分同型变化注入中也会误抵消，完整报告，不以它天然通过作假设。

## 诊断证据

`reference_and_mode_diagnostics.csv`：每30分钟的真实运行系数、参考资格、有效/降权数量和残差。`model_birth_diagnostics.csv`：每夜每点Ai、b/cbar、历史残余尺度、杠杆和资格。`point_mode_contributions.csv`：关键点逐小时的三阶gAi vi、gcbar、总修正及非模态增量。`runtime_and_failure.csv`保留所有设备：活动帧median/P99/max及含22–07:20学习建模的全夜P99/max，避免漏掉模型初始化开销。

耗时是该Windows开发机的整个Process调用，包括原始X/Y和缓冲诊断日志；没有做生产性能承诺。第一夜冷启动、第二夜一份过去历史的差别必须保留。CSV是未压缩UTF-8，单文件<2 MB。仅8份03–05点关键连续CSV和4张图；完整源数据、PR2观察时序和本轮可重建二进制缓存支持其余窗口，缓存不提交。

## 复现

需要Python 3.12、numpy、pandas，绘图另需matplotlib，C++17 g++。实测数值运行Python3.12.14/numpy2.3.5/pandas3.0.1；绘图使用已有Python3.12.13/numpy2.5.3/pandas3.0.6/matplotlib3.11.2，通过CSV/固定二进制格式交换，不跨环境交换pickle。源码身份及编译器见build_provenance.json。

在仓库根目录：

```powershell
python analysis/right_x/scripts/load_data.py
python analysis/right_x_enhancement/scripts/prepare.py
python analysis/right_x_enhancement/scripts/build.py --cxx C:/msys64/ucrt64/bin/g++.exe
python analysis/right_x_enhancement/scripts/run.py --stage ea --inject
python analysis/right_x_enhancement/scripts/results.py --stage ea
# 按冻结筛查核对E/A；本批不满足E+A联合条件，未运行联合方案。
python analysis/right_x_enhancement/scripts/run.py --stage all --tag final --inject
python analysis/right_x_enhancement/scripts/results.py --stage final
python analysis/right_x_enhancement/scripts/diagnostics.py
python analysis/right_x_enhancement/scripts/spatial_audit.py
python analysis/right_x_enhancement/scripts/screen.py
python analysis/right_x_enhancement/scripts/plots.py
python analysis/right_x_enhancement/scripts/validate.py
```

`.work`内保存可执行程序、每设备完整回放、独立状态分叉及日志。不覆写生产文件或状态包。可用RX_REPO/RX_CACHE/RX_WORK/RX_OUTPUT选择输入/派生目录。重建会覆盖该研究目录的派生结果；CSV指标应复现，机器耗时和PE编译时间戳不要求字节一致。`--stage ea`只运行E/A；最终代码包含空间秩处理澄清，原EA正常序列的X仍逐位一致。本文手工评审结论不因脚本运行自动变成“通过”。

本次还利用已存在的PR2回放缓存额外核对75,564条原始冷启动参考输出。复现该可选检查可设置RX_PRIOR_REPLAY指向PR2的replay_cache；未设置时validation中的该项计数为0，其他原始独立实例/形状/逐位检查仍执行。内存分叉恢复通过不等于生产重启协议通过：新增冻结尺度、资格、偏置和滤波状态尚未加入现场状态包版本，本轮不提供部署状态。

生产V51/V53、Y、在线配置及状态包未改；没有部署入口。缺真实串联条件，不输出候选x0，不把数据变平当精度改善。下一候选须在查看新夜结果前冻结，并加入真实几何/独立真值验证。
