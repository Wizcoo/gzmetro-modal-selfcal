# V53 左右线 Y 向共模与下游 y0｜2026-11-19 至 11-22 夜

四个连续夜间的现场落库 `y`、`calY`、测点 `y0` 和设备节点 `y0`，用于复核共模修正后的局部离群和参考点成组异常。夜号按开始日期命名。时间为北京时间 22:00–次日 08:00，全幅修正统计窗为 23:20–次日 07:00（含起点，不含终点）。

- [结论和事件证据](FINDINGS.md)汇总原始值、修正值、另一视角和下游表现。
- [给 Gemini 的分析任务](GEMINI_TASK.md)列出待验证的问题、离线对照和交付要求。
- [逐事件表](evidence/point_events.csv) · [全夜统计](evidence/nightly_summary.csv) · [11/21 右线节点事件](evidence/1121_right_node_event.csv) · [ZD1403 原生回放](evidence/native_replay_zd1403.json)

| 夜间 | 上游原始 y / calY | 修正后 1 px 刻度放大图 | 下游 y0 |
|---|---|---|---|
| 11/19 | [前后对照](figures/1119_camera_before_after.png) | [像素放大](figures/1119_camera_pixel_zoom.png) | [全体和重点点](figures/1119_downstream_y0.png) |
| 11/20 | [前后对照](figures/1120_camera_before_after.png) | [像素放大](figures/1120_camera_pixel_zoom.png) | [全体和重点点](figures/1120_downstream_y0.png) |
| 11/21 | [前后对照](figures/1121_camera_before_after.png) | [像素放大](figures/1121_camera_pixel_zoom.png) | [全体、重点点与节点](figures/1121_downstream_y0.png) |
| 11/22 | [前后对照](figures/1122_camera_before_after.png) | [像素放大](figures/1122_camera_pixel_zoom.png) | [全体和重点点](figures/1122_downstream_y0.png) |

## 数据目录

每个 `data/YYYY-MM-DD/{left,right}/` 包含四份普通 CSV。`frame_id` 只在该线路、该夜内有效。跨文件、跨相机对齐使用同一目录的 `frame_id` 或 `timestamp_ms`。左右线分别保留各自采样时钟。

| 文件 | 每行内容 |
|---|---|
| `frames.csv` | `frame_id`、Unix 毫秒 `timestamp_ms`、带 `+08:00` 的 `local_time`、上游数据库分片名、`has_y0` |
| `camera_y.csv` | `frame_id,channel_id,roi,y_mm,cal_y_mm`。`roi` 是原库 `RoiCalState`。计算只用 `roi=1` 且两个坐标均有限的观测 |
| `marker_y0.csv` | `frame_id,point_id,y0_mm`，取 `MarkerData.y0`，同名点是串联后的单一测点输出 |
| `node_y0.csv` | `frame_id,node_id,y0_mm`，取 `SubDeviceDisData.y0`，每帧六设备 |
| `data/channels.csv`、`markers.csv`、`devices.csv` | 连接 ID 与线路、12 位设备号、测点名。区分同名点的不同相机观测时用 `channel_id` |
| `data/calibration.csv` | 用 `night,channel_id` 关联。`scale_px_per_mm`、`center_x_px`、`center_y_px`，每夜每通道固定 |
| `data/replay_zd1403/` | 设备 `780638271319` 的 5,148 帧连续 X/Y 原生回放输入 CSV、落库 `calY` 以及 11/19 初始 `.state` |

上游 **1,253,054 行**，每晚左/右线分别覆盖 **254/268 路**设备–测点。下游测点 **938,400 行**，左/右线分别覆盖 **191/200 个**测点，设备节点 **28,800 行**。每条线每晚均有 **600 帧**下游落库值。左线 11/22 夜有 601 个上游时间戳，11/23 04:02:07.155 仅有上游记录，同一分钟 04:02:24.162 有下游。左线 11/20 夜跨库处 11/21 06:48:05.202 的上下游分属相邻数据库，导出时按精确时间戳合并。分片覆盖见 [data/manifest.json](data/manifest.json)。

上游两条曲线均减去同一点当晚 22:00–23:00 有效原始 `y` 均值。等效像素为该毫米变化量乘 `scale_px_per_mm`。`y0` 用落库 mm 原值和原零点。主分析 CSV 毫米值保留 7 位小数，标定保留双精度所需有效位，原生回放输入保留 17 位有效数字。无效 ROI 保留原字段，不参与计算。±3.2 px 放大图标出越界时间与实际极值，CSV 保留数据。

### 浅克隆本分支

~~~sh
git clone --depth 1 --single-branch --branch analysis/v53-y-20261119-22 https://github.com/Wizcoo/gzmetro-modal-selfcal.git
~~~

## 复核

在仓库根目录执行。分析脚本从随分支提供的 CSV 读取，原生回放另外需要可执行 `g++` 的 C++17 工具链。

~~~sh
python -m pip install -r analysis/v53_y_20261119_22/requirements.txt
python analysis/v53_y_20261119_22/scripts/analyze.py
python analysis/v53_y_20261119_22/scripts/replay_zd1403.py
~~~

`scripts/export_from_sqlite.py` 记录从本地六个 SQLite 分片只读导出、按下游数据页行号读取、以及重叠/缺帧核对的过程。复核可直接用随分支提供的数据。回放使用 [V53 C++ 源码](../../versions/V53/)，`ModalSelfCal.cpp` 和 `ModalSelfCal.h` 与此次使用的 `modelselfcal-V53-1110` 逐字节一致。V53-new 作为分支基线提供，回放对象是 `versions/V53`。

Branch for independent review. The night ID is the evening start date in Asia/Shanghai. `y` / `calY` are camera-side values. `y0` is the stored downstream result in mm. Pixel values express camera-equivalent changes around the nightly baseline.
