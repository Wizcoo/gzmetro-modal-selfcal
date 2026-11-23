# ModalSelfCal

一个用于多通道时序数据处理的 C++17 算法库，支持逐帧处理、缺测跳过和状态快照。V53-new 支持通过状态导入切换测点配置。

## 现场数据分析

[2026-11-19 至 11-22 夜 V53 Y 向分析交接](analysis/v53_y_20261119_22/README.md)包含左右线提点、共模修正后值、下游 y0、原生回放和独立复核任务。

## 构建与测试

```sh
cmake -S versions/V53-new -B build/V53-new
cmake --build build/V53-new --config Release
ctest --test-dir build/V53-new -C Release --output-on-failure
```

[V53-new 接入说明](versions/V53-new/README.md)包含调用方式，以及基于合成数据的 C++ 回归测试。

## 版本

- [V53-new](versions/V53-new/) 支持动态测点配置，并兼容 V53 状态快照。
- [V53](versions/V53/) 和 [V51](versions/V51/) 可通过根目录的 CMake 配置选用，例如 `cmake -S . -B build/V53 -DMODALSELFCAL_VERSION=V53`。

通用接口见[软件接入说明](docs/integration.md)。
