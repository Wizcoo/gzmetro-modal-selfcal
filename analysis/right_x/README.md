# 右线 X 专项诊断

先读 [第一轮结论](right_x_findings.md) 和 [实际链路](pipeline_trace.md)，再按 [事件索引](right_x_events.csv) 查看连续证据。

[指标与分段定义](metric_definitions.md) 适用于每个 CSV；`file_catalog.csv` 为逐文件单位、时间窗口、行数和 SHA-256 目录。所有文件均小于2 MB，无压缩附件。

生产源码、配置、状态和原始JSONL保持不变。本分析分支仅新增允许分享的诊断结果与本轮自编脚本，没有复制额外公司实现。
