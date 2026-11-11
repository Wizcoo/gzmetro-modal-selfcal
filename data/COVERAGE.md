# 数据覆盖与已知缺口

窗口：北京时间 2026-11-05 至 2026-11-11，实际仅到本地已有最新记录。

| 线路 | 来源记录数（未跨库去重） | 最早记录 | 最新记录 |
| --- | ---: | --- | --- |
| 左线 | 5,381,599 | 2026-11-05T00:00:22.443+08:00 | 2026-11-11T09:36:49.906+08:00 |
| 右线 | 2,792,294 | 2026-11-05T00:00:19.164+08:00 | 2026-11-07T15:00:00.826+08:00 |

总计 8,173,893 条源记录，gzip 分片合计 272,294,493 字节。

## 缺口

- 右线本地记录最多到 2026-11-07 15:00（设备级表到 14:59），11 月 8–11 日未在本次本地源库中找到。
- 左线 SubDeviceDisData 从 2026-11-06 11:38 至 2026-11-07 14:33 存在约 27 小时的库间缺口。该时段没有补造。
- 左线第 4 卷结构损坏。可以读取的记录已导出；下表列出读取时发生错误的表。清单保留具体 rowid 区间，无法读出或无法独立计数的数量不作推测。

| 线路 | 来源卷 | 表 | 导出行数 | 独立源计数检查 |
| --- | --- | --- | ---: | --- |
| left | 1793507670403_DataBaseFile_4 | MarkerData | 173,760 | unavailable_corrupt_source |
| left | 1793507670403_DataBaseFile_4 | Marker_780630499846 | 18,594 | partial_corrupt; 比源计数少 18 行 |
| left | 1793507670403_DataBaseFile_4 | Marker_780637798298 | 28,756 | partial_corrupt; 比源计数少 8 行 |
| left | 1793507670403_DataBaseFile_4 | Marker_780638271319 | 28,756 | partial_corrupt; 比源计数少 8 行 |
| left | 1793507670403_DataBaseFile_4 | Marker_780638310097 | 79,458 | partial_corrupt; 比源计数少 66 行 |
| left | 1793507670403_DataBaseFile_4 | SinglePoint_780637798298 | 28,730 | unavailable_corrupt_source |
| left | 1793507670403_DataBaseFile_4 | SinglePoint_780638271319 | 28,730 | unavailable_corrupt_source |
| left | 1793507670403_DataBaseFile_4 | SinglePoint_780638310097 | 79,430 | unavailable_corrupt_source |
| left | 1793507670403_DataBaseFile_4 | SinglePoint_780638327479 | 42,250 | unavailable_corrupt_source |

## 校验

- 181 个 gzip 分片逐行 JSON 解析、字段列表、行数、时间极值及 SHA-256 检查通过。
- 对 140 张来源表独立执行源库计数与时间极值对账；损坏源的不可计数情况单独保留。
- CSV 转换脚本对 1,293 条环境记录验证了行数、设备号及末条时间戳。
- 详细验证结果见 `../docs/data_validation.json`，完整来源与分片索引见 `manifest.json`。
- 数据是原库实存结果，未重跑 V51/V53，不能据此推断全周都运行当前上线版本。
