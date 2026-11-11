# 近期现场数据库导出

北京时间窗口为 `[2026-11-05 00:00, 2026-11-12 00:00)`。源库为本地已下载副本，实际覆盖以 `manifest.json` 为准。缺失日期和损坏记录没有补造。

先看 [覆盖与缺口汇总](COVERAGE.md)，再使用逐库逐表清单。

## 格式与读取

全量为 `.jsonl.gz`，解压后每行一个 JSON 对象。JSON 保留数字、文本和 SQL NULL（`null`），没有改变输入/校正/下游字段的含义。每片最多 100,000 行，便于 Git 传输。每表另有最多 3 行的 `.preview.json`，可在 GitHub 直接预览。

路径按 `left或right/来源数据库/原表名.partNNN.jsonl.gz` 分开；每行额外的 `_source_rowid` 结合文件路径追踪源记录。没有跨库去重或拼接，分析时应按表的真实业务主键核对重复，不能直接把多个阶段的记录相加。

Python 标准库直接读取：

```python
import gzip, json
with gzip.open('data/left/<source_db>/Marker_<device>.part001.jsonl.gz', 'rt', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        # 按 timestamp 和 markerName 处理原始记录
```

需要 Excel/CSV 时转换同一张表的分片（Python 3.8+，无第三方依赖）：

```sh
python tools/to_csv.py data/left/<source_db>/Marker_<device>.part001.jsonl.gz --output build/table.csv
```

可传入多个同表分片。CSV 用 UTF-8 BOM，`\N` 表示原 SQL NULL。不同库相同业务观测可能重叠；转换保留所有源行。全量 JSONL 是保留字段类型的主档。

## 数据字典

- `Marker_<device>`：逐设备测点。`x/y` 是校正前坐标，`calX/calY` 是数据库实存算法校正结果，`RoiCalState` 等字段原样保留。
- `MarkerData`：下游测点记录，包含 `x0/y0`、过滤和初值等字段，与 Marker 表的处理阶段不同。
- `SubDeviceDisData`：设备级位移、姿态及时间。
- `SinglePoint_<device>`：单点观测、图像/参考编号、原始及过滤值。
- `EnvData_<device>`：温度、湿度等环境记录；字段存在不等于数据一定有效，需检查实际值和覆盖。
- `timestamp`/`ts`：本批库使用 Unix 毫秒，原始数值不改写；`dateTime` 保留原文本。筛选依据时间戳。
- 表结构和声明类型逐库逐表保存在清单。设备号从 Marker 表名读取，不能用下游 MarkerData 关系替代设备点表。

## 来源与损坏处理

左线选择 11 月 1 日数据库家族中覆盖窗口的第 3–7 卷。右线选择 10 月 27 日数据库家族第 6 卷和第 7 卷副本；第 7 卷副本替代损坏的原第 7 卷，两个副本没有合并，避免重复导出同一来源。

所有源库以 `mode=ro` 打开，按源文件 SHA-256 留档。优先正序扫描；出现损坏时按 rowid 区间缩小读取范围，保留可读取记录并在 `unreadable_rowid_ranges` 列出跳过区间。区间中的记录可能落在本窗口内或外，未把损坏区间估算成零记录。`complete_read` 表示所选文件的表能完整扫描，不证明现场采样完整。

验证：`python tools/verify_data.py data` 检查所有分片 SHA-256、逐行 JSON 解析、字段列表、行数与时间极值。原库导出脚本为 `tools/export_week.py`；再次导出必须使用新目录。

历史记录未重跑当前 V51/V53，也未把 11 月 11 日以前的数据批量标成 V53。来源库没有逐行版本身份时，应结合部署日志判断。
