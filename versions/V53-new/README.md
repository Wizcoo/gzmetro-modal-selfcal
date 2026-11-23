# ModalSelfCal V53-new datapackage

用 `ModalSelfCal.h` 和 `ModalSelfCal.cpp` 替换集成侧的 V53 算法源码。点表变更时先保存最新状态包，再按 `Destroy → Init(新点表) → ImportState` 切换。逐帧 X/Y 向量按新点表顺序传入，缺测用 `NaN`。导入日志记录 `added` 和 `removed`。

默认以当夜 02:00 起的首帧收夜。新增点需要满足基线和学习窗样本门槛，且载荷求解成功。达到条件的点按自己的斜坡进入修正，参与老点求解的学习集在当夜保持原有值。次夜从历史中按该点实际在场的夜统计有效率。保留的历史学习点少于 `K + 2` 时，修正窗内进入 `WAIT_MODES`。

V53-new 可导入旧 V53 状态包。回滚到旧 V53 DLL 时使用旧 V53 导出的状态包。

## 运行回归测试

```sh
cmake -S . -B build
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

PowerShell 可直接用 MinGW g++ 运行同一组用例。

```powershell
g++ -std=c++17 -O2 -I . ModalSelfCal.cpp tests/test_dynamic_markers.cpp -o test_dynamic_markers.exe
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
foreach ($scenario in @('add', 'remove', 'missing', 'restart', 'legacy', 'attachment_limits')) {
    .\test_dynamic_markers.exe $scenario .\tests\fixtures
    if ($LASTEXITCODE -ne 0) { throw "Test failed: $scenario" }
}
```

`tests/fixtures/` 中的两个快照由原版 V53 源码和合成数据生成，分别保存三夜历史和冷启动斜坡期状态。需要重建快照时，用原版 `ModalSelfCal.cpp` 编译 `tests/test_dynamic_markers.cpp`，定义 `MSC_GENERATE_V53_FIXTURES`，并以输出目录作为可执行文件的唯一参数。
