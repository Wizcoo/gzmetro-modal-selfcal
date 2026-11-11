# 重建数据表

这些是本轮自编只读输入的诊断脚本，没有生产算法调用或部署入口。需要 Python、pandas、numpy。`load_data.py` 自动以本仓库为输入，核对已有 JSONL 分片 SHA-256，只读取右线指定窗口；缓存保存在本分析目录的 `.cache/`，不会提交。

从仓库根目录按依赖顺序运行：

```sh
python analysis/right_x/scripts/load_data.py
python analysis/right_x/scripts/analyze.py
python analysis/right_x/scripts/learning_audit.py
python analysis/right_x/scripts/coverage.py
python analysis/right_x/scripts/night_compare.py
python analysis/right_x/scripts/events.py
python analysis/right_x/scripts/enrich.py
python analysis/right_x/scripts/validate.py
```

事件脚本依赖 analyze 产生的缓存；learning/coverage/night_compare 可在输入缓存就绪后独立运行。所有原分辨率证据不采样、不插值。重复运行会覆盖本分析目录的派生 CSV，建议另开分析分支保留审查版本。Markdown 结论按当前冻结结果人工审阅，脚本不自动宣布物理原因。具体方法见上一层 metric_definitions.md。
