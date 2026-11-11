# 软件接入

选择一个版本的 `ModalSelfCal.cpp` 和 `ModalSelfCal.h` 加入 C++17 工程。`ModalSelfCalConfig` 属于 `gzmetro_msc` 且有全局别名；`ModalSelfCalState`、`ModalSelfCalResult`、`ModalSelfCalResumeInfo` 在当前头文件中直接位于全局命名空间。

1. 构造配置与 `ModalSelfCalState`。对已经运行的设备，调用 `Init(device_id, names, &error)` 后导入配套状态包。`allow_new_stream` 默认为 false，此时没有成功导入状态不能处理实时帧。只有明确开启全新数据流才使用 true。
2. 软件读取完整二进制状态，调用 `ImportState(bytes, &resume, &error)`。校验设备、点表和数学参数，成功后从 `resume.last_timestamp_ms` 之后的下一真实帧继续。
3. `Process(timestamp_ms, raw_x, raw_y, &result, &error)`。数组与初始化点名顺序一致，缺失点按接口约定传 NaN。返回成功且 `output_ready` 后使用 `result.x/y` 作为算法校正结果。
4. 调用 `ExportState(&bytes, &last_timestamp_ms, &error)`，软件负责把含 NUL 的完整字节持久化。算法不负责数据库和文件读写。导出成功不代表软件已经可靠落盘。
5. 内部异常导致实例失效时，按源码约定销毁并从软件已提交快照恢复，不能继续使用可能部分推进的内存状态。

时间使用 Unix 毫秒，默认换算北京时间。22:00–23:00 为基线窗，22:00–次日 02:00 为学习窗，修正与斜坡时段以配置为准。x/y 为 Marker 表算法输入，calX/calY 为其校正值；MarkerData 的 x0/y0 是下游输出字段，不能直接视为同一处理阶段。

状态 checksum 用于一致性检查。当前快照是内存计算组件，未提供用户登录、网络认证或凭据存储接口；不要把设备 ID、配置指纹或状态 checksum 当作访问令牌。
