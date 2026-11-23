# ex0 原版 V53 双轴回放

## 冻结配置和输入

采用指定 1110 包中 `modelselfcalV52/algorithm/ModalSelfCal.{h,cpp}`，程序在编译前验证两个 SHA-256。启用原版默认参数，包括三夜历史、60 秒标称间隔和 `max_frame_dev=0`。10 月 16 日冷启，沿真实时间顺序执行 `ModalSelfCalState::Process`，使用返回的 x/y。数据库中的 calX/calY 可能由不同版本计算，不参与输入和生成基准。

左右线各 6 台设备，主快照目录为 `01data-sql/左线/NewDevice`、`01data-sql/右线`。仅读取 Marker 表真实时间戳、点名、点序、RoiCalState、x/y。读入包含重叠数据的右线 7 号分片副本，同一设备、时间戳、点名只保留一条，坐标相同的副本合并，冲突的轴置为 NaN。未通过 ROI 检测、非有限和缺测坐标也传入 NaN。每个进程仅以只读模式打开 SQLite。

分片损坏时按时间二分至最长 60 秒，记录无法读取的终端区间。部分截断索引即使请求文件末帧之后也会报错，错误查询范围不等于实际丢失帧数。日历覆盖另按真实时间戳去重计算。相邻两个时间戳之间超过 30 分钟的缺口按设备单独记录。跨缺口保留原版状态，让 V53 自行处理时间跳跃。右线在 10 月 16 日上午至 18 日上午有采集空档，左线在 11 月 6 日中午至 7 日下午有采集空档。

回放器在首次出现新点的当前帧扩大点表。某点连续 60 帧完全没有对应原始行时，从第 60 帧移除该点；包含无效 ROI 标记的行仍视为点存在。点表成员变化时原版重新冷启；其余时刻沿用初始化顺序。会话记录含每次增删的点、准确时刻和冷启次数。输出 NPZ 的联合列名只供回放结束后对齐，在线 V53 输入按当时已知点集构造。

## 复现

Windows x86-64，MinGW-w64 的 g++、SQLite 开发库可从 PATH 访问，离线整理使用 Python、NumPy、pandas，画图另用 Matplotlib。部署的 V53 引擎不需要 Python 或 SQLite。

```powershell
python ../replay/build_cache.py --root E:/Wiz/GZMetro-Cpp/01data-sql --v53 E:/Wiz/GZMetro-Cpp/module/modal-selfcal/modelselfcal-V53-1110/modelselfcalV52/algorithm --cache ./private/cache --work ./private/native --results ./provenance --jobs 2
python ../replay/summarize.py --provenance ./provenance --cache ./private/cache --out ./results --binary ./private/native/replay.exe
python plot_raw.py ./private/native/780630499846 ./results/raw_vs_v53.png
```

独立运行第二次可使用新的 work/cache/provenance 目录；给 summarize.py 增加 `--check 第二次缓存目录`，将逐位比较时间、点名、双轴数组（包括 NaN 位模式）。

## 报告字段

- `results/native_summary.json` 和 `results/device_replay.csv` 记录全量与分设备原生资源数据。帧耗时为每次 Process 前后计时后对真实帧加权的均值。包括引擎自身默认日志格式化，stderr 指向空设备。计时不含 SQLite 读取、文件读写和 Python 打包。
- 峰值取每一设备、每一个点表时期独立的 x86-64 原生进程执行到最后一帧时 Windows 的峰值工作集，报告所有时期的最大值。相对预 Init 工作集的增加是进程级估计。序列化状态大小取各时期末次导出的最大值，V53 无独立训练权重文件。
- `results/calendar_coverage.csv` 给出每线、每设备、每个日历日的真实有效时钟分钟覆盖，包括白天候选窗和对应夜晚。逐点有效分钟及平稳筛选由统一评分器另行计算。
- `results/raw_vs_v53.png` 由 780630499846 最后点表时期的真实输入和原版输出生成。在该设备的完整测试夜中选择基线方差最大的点轴；11 月 19 日夜 ZD1305/Y 的原始方差 12.09939 mm²，V53 后 1.55336 mm²。
