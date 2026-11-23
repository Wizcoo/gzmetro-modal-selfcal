# 复现实验

下面的 PowerShell 命令在本分支仓库根目录运行。离线读库与绘图依赖 Python、NumPy、Pandas、Matplotlib；C++17 推理依赖标准库。实验使用 Windows x86-64 MinGW-w64 GCC 16.1.0，SQLite 开发库仅用于离线提取，PSAPI 用于读取工作集。原始 SQLite 需要另行提供。将下列 `$id` 改为当前分支的实验号。

```powershell
$p = 'experiments/longcal_1016_1123'
$id = 'ex1'
$exp = "$p/$id"
$candidate = if ($id -eq 'ex0') { "$p/common/identity" } else { $exp }
$v53 = 'versions/V53'
$db = 'E:/Wiz/GZMetro-Cpp/01data-sql'
$scratch = 'build/longcal'
python "$p/replay/build_cache.py" --root $db --v53 $v53 --cache "$scratch/cache" --work "$scratch/native" --results "$scratch/provenance" --jobs 2
python "$p/common/check_causality.py" --candidate $candidate --scratch "$scratch/qa"
```

各候选均配有已冻结参数。使用下面的命令复现结果。ex0 的资源数字读取原版 V53 进程；ex0 的 identity 处理器用来产生相同的因果参考锚和抽样训练集。

```powershell
if ($id -eq 'ex0') {
    python "$p/common/evaluate.py" --cache "$scratch/cache" --candidate $candidate --work "$scratch/$id" --results "$scratch/results-$id" --identity --collect "$scratch/train_samples.npz"
    python "$p/common/edge_benchmark.py" --v53 $v53 --segments "$scratch/native" --candidate $candidate --work "$scratch/bench-$id" --out "$scratch/results-$id/edge_benchmark.csv" --baseline-only
} else {
    python "$p/common/evaluate.py" --cache "$scratch/cache" --candidate $candidate --work "$scratch/$id" --results "$scratch/results-$id"
    python "$p/common/diagnostics.py" --cache "$scratch/cache" --work "$scratch/$id" --results "$scratch/results-$id"
    python "$p/common/edge_benchmark.py" --v53 $v53 --segments "$scratch/native" --candidate $candidate --work "$scratch/bench-$id" --out "$scratch/results-$id/edge_benchmark.csv"
}
```

ex1 可在拟合前用 identity 模式生成训练样本，再运行 `python "$exp/train.py" --samples "$scratch/train_samples.npz" --out $exp`。ex4 的权重及哈希随分支提供；同权重构造与比较命令见其 METHOD.md。

## 指标

每个夜窗每分钟取第一帧，同一测点轴至少有 480 个有效分钟。先算各单元总体方差，再等权平均；夜间毛刺率为相邻有效分钟中绝对差超过 0.50 mm 的比例。锚 MAE、RMSE 按有可信锚的观测加权。均值纳入所有合格单元，包括缺锚、事件冻结等导致的透传。报告的两线和 X/Y 分别重算，各子组均使用同一批配对样本。白天覆盖 10:00–16:00 所有有效输出，并给出通过筛选的半小时块数。P95 退化为候选方差减 V53 方差的第 95 百分位。

每台设备依次在不同测试夜 01:10 注入单点与设备全点的阶跃、45 分钟斜坡和小阶跃。单点选择该夜满足完整性条件的第一个测点。X/Y 同时注入，符号相反。大阶跃和斜坡幅值 1 mm，小阶跃 0.35 mm，全部维持到窗口第 60 分钟。阶跃按全程，斜坡按平台段计算“注入输出减原输出”与注入幅值之比。注入位于 V53 输出端，检验新增校准器对输入事件的额外影响。每个事件复制注入前状态，结束后丢弃。此前 30 分钟平均绝对修正大于 0.001 mm 的点轴另列。90% 门槛用所有被评估注入观测的最低保持率。

运行时间以整台设备全部点的双轴单帧为单位，独立进程从真实原始帧逐帧运行。全链路基准对每台设备最后一个固定点表段分别冷启，测量读取帧之后到 V53 或 V53+附加器输出完成的时间，不含 SQLite 与磁盘 I/O。`peak_bytes` 为进程峰值工作集；配对进程工作集之差包含操作系统分配噪声。`kernel_state_bytes` 是附加器持久内存的直接计数。实际设备需在现场持续负载下复核。

原版 V53 每帧会格式化诊断消息。全链路性能测试将标准错误输出指向空设备，保留原库格式化开销；现场的日志存储耗时依实际写入方式而定。
