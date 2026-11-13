# V54 协作快照

导入日期：2026-11-13。来源为本地 `modelselfcal-V54` 目录，原始 CPP、头文件、自带测试均按原字节保存，见 [来源清单](source_manifest.json)。

本目录是当前算法的协作起点。YD2603 的历史学习与回归保护修复尚未实现，不应把本分支当成已经修复该问题的上线版本。

## 构建与验证

在仓库根目录执行，选择 V54，避免与 V51/V53 同名符号混合链接：

```sh
cmake -S . -B build/V54 -DMODALSELFCAL_VERSION=V54 -DCMAKE_BUILD_TYPE=Debug
cmake --build build/V54 --config Debug
ctest --test-dir build/V54 -C Debug --output-on-failure
```

也可直接使用 GCC：

```sh
g++ -std=c++17 -O2 -UNDEBUG versions/V54/ModalSelfCal.cpp versions/V54/test_v54.cpp -o test_v54
./test_v54
```

MSVC 使用 `/std:c++17 /utf-8 /EHsc /UNDEBUG`。自带测试依赖 `assert`，CMake 为该测试显式取消 `NDEBUG`。

## 配置和状态

- 头文件默认 `max_frame_dev=8.0`；本次左右线 11/12 夜回放使用调用方显式设置的 `max_frame_dev=0.0`，其余参数为默认值。
- `0` 关闭的是实时求解中的绝对偏差门限；它不会清理历史统计，也不会自动解决 YD2603 的过度修正。
- 导入旧状态时，需要设备、点表和数学参数指纹匹配。当前源码支持 V54 新层缓存序列化；旧 V53 状态没有这些缓存，导入成功不代表新层已经完成预热。
- 修改历史学习/回归规则后，应重建或明确迁移历史状态，并验证连续运行与保存后恢复的一致性。

## 已知问题与协作边界

详见 [协作交接](../../docs/V54_COLLABORATION.md)。优先修复 X 向历史异常进入统计，以及因异常被剔出学习的普通测点仍无条件回归修正的问题；对显式 `YJ/ZJ` 回归点需保持独立处理。

`README.source.md` 是原始说明留档。其中对物理保真、全天透传、长期运行和重启连续性的表述属于原文主张，不能当作独立验收结论。自带用例通过、状态导入成功和曲线更平稳均不能单独证明现场位移精度。
