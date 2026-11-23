# 软件接入

选择一个版本的 `ModalSelfCal.cpp` 和 `ModalSelfCal.h` 加入 C++17 工程。`ModalSelfCalState` 接收按时间顺序到达的两组测量通道。

1. 构造 `ModalSelfCalConfig` 和 `ModalSelfCalState`，调用 `Init(device_id, names, &error)` 绑定数据流和测点顺序。全新的数据流可设 `allow_new_stream=true`。
2. 续算时调用 `ImportState(bytes, &resume, &error)`。成功后从 `resume.last_timestamp_ms` 之后的下一帧继续。V53-new 支持根据测点名称迁移状态，参见 [V53-new 接入说明](../versions/V53-new/README.md)。
3. 调用 `Process(timestamp_ms, raw_x, raw_y, &result, &error)`。数组顺序与 `names` 一致，缺测用 `NaN`。返回成功且 `output_ready` 为真时，可读取 `result.x` 和 `result.y`。
4. 调用 `ExportState(&bytes, &last_timestamp_ms, &error)` 获取二进制状态。应用侧保存包含 NUL 的完整字节串。实例因内部异常失效时，从应用侧已保存的状态快照恢复。

时间戳使用 Unix 毫秒。基准、学习和修正窗口使用 `ModalSelfCalConfig` 设置。
