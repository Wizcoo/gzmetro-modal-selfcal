# 复现入口

先读 [findings.md](findings.md) 和 [methodology.md](methodology.md)。本目录是PR #1的后续研究，原始JSONL及生产源码均沿用仓库，不重复上传。

## 运行顺序

在仓库根目录使用Python 3.12及numpy、pandas、matplotlib；C++回放使用支持C++17的g++。实测统计/回放编排：Python 3.12.14、pandas 3.0.1、numpy 2.3.5；绘图使用现有工程Python 3.12.13、matplotlib 3.11.2、pandas 3.0.6。精确运行版本见provenance.json。跨环境优先交换CSV，不交换pickle。

```powershell
python analysis/right_x/scripts/load_data.py
python analysis/right_x_yj_yxj/scripts/relations.py
python analysis/right_x_yj_yxj/scripts/candidates.py
python analysis/right_x_yj_yxj/scripts/replay_prepare.py
g++ -std=c++17 -O2 -pthread -I versions/V51 analysis/right_x_yj_yxj/scripts/replay_driver.cpp versions/V51/ModalSelfCal.cpp -o analysis/right_x_yj_yxj/.work/replay_cache/replay.exe
python analysis/right_x_yj_yxj/scripts/run_replays.py
python analysis/right_x_yj_yxj/scripts/injections.py
python analysis/right_x_yj_yxj/scripts/reference_fault_ablation.py
python analysis/right_x_yj_yxj/scripts/downstream.py
python analysis/right_x_yj_yxj/scripts/endpoint_coefficients.py
python analysis/right_x_yj_yxj/scripts/scale_audit.py
python analysis/right_x_yj_yxj/scripts/phase_common.py
python analysis/right_x_yj_yxj/scripts/prepare_plot_inputs.py
python analysis/right_x_yj_yxj/scripts/plots_and_residuals.py
python analysis/right_x_yj_yxj/scripts/summary_figures.py
python analysis/right_x_yj_yxj/scripts/full_yxj_plot.py
python analysis/right_x_yj_yxj/scripts/validate_artifacts.py
```

全部输入只读；允许覆盖本目录的派生分析文件及.work缓存。不要把.work、二进制输入、exe或pickle提交。若需保护已提交结果，可用环境变量YJ_ANALYSIS_OUTPUT指定另一输出目录，YJ_ANALYSIS_WORK指定工作缓存，YJ_ANALYSIS_INPUT_CACHE指定PR1去重缓存。绘图可用独立Python环境，通过prepare_plot_inputs.py的CSV交换。

54次主回放加6次参考故障消融，共60次原始源码运行。空状态默认回放是受控基线，不能恢复未提供的现场历史。V51/V53生产文件不写入；源码前缀仅改变独立X实验实例，Y取独立默认V51实例。修改本研究脚本不等于生产算法已变更。

## 主要文件

- observed_traces：20路参考/节点观测，完整11/05–11/07，毫秒时间戳及溯源字段。
- relations、endpoint_response_coefficients、cross_night_response_stability：分日夜相关和方向/比例，不是几何传递系数。
- candidate_traces：两折隔夜验证，含实际raw/cal、候选X、回退标志、Y对照；完整基线至渐出，不随机抽样。
- injection_traces：6形态×6路YXJ×2候选；02:00–07:00完整连续分辨率；观察坐标域测试，不能冒充世界位移真值。
- downstream_traces：仅实际下游时序，未生成候选x0。
- file_catalog.csv：单位、范围、用途、字节和SHA；validation.json：实跑核验结果；provenance.json：输入/源码/环境身份。

CSV时间范围、单位和分段规则以各行显式字段、文件索引及methodology.md联合解释。原始字段单位采用共模API的毫米契约，数据库业务写入实现仍缺失。没有“真实误差”标签。PNG用于阅读，逐帧CSV用于复核。
