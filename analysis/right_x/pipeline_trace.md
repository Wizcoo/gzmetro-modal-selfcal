# 右线 X 专项：已证实链路与缺失环节

审查日期：2026-11-11。生产源码只读，使用私有协作仓库基线 `30b365f6405b10b297ec1546f4bff8b64b911384`。本轮没有运行现场部署、没有改写状态或配置。用户确认只按现有模块分析，其他业务数据无权访问。

## 证据等级

- **代码确认**：当前可读函数实现或明确 API 契约。只能证明该模块行为，不能自动证明业务软件如何接线。
- **现场字段恒等式/关联**：本批记录可复算，不能替代缺失的写入、求解或发布代码。
- **历史文档线索**：需要调用方实现核实。文档中的模型、设备数、符号和路径不自动视为 2026-11 的部署事实。

## 流程逐段核对

| 环节 | 可定位证据 | 可以确认 | 尚不能确认 |
| --- | --- | --- | --- |
| 视觉输出 | 本地 `modelselfcal-1016/Dot2DDIC_V0.0.0.51(1)/Dot2DDIC.h:132-147`，`RoiResult` | `uv_cal/uv_temp/uv_corre` 注释为像素位移阶段，`uv_mm` 明确为参考点校准后的毫米位移；`RoiCalState` 是计算状态 bool | DLL 内部公式，以及哪个输出实际写入 Marker.x/y |
| 提点调用入口 | 同头文件 `CDot2DDIC::PixelDisplInCam:173`、`solveSingleCam:179`；`ProcessModalSelfCalState:237-240` | 有视觉计算和共模状态式接口；状态式入口约定原始毫米数组、无效点 NaN，见 `:226-240` | 业务软件实际调用点、是否同时调用旧接口、有效性屏蔽、持久化顺序 |
| ModalSelfCal 内部 | 仓库 [V51/ModalSelfCal.cpp:1177](../../versions/V51/ModalSelfCal.cpp#L1177)，`ModalSelfCalState::Process` | `:1196` 分别调用 X/Y `Ingest`；`:1201` 取得逐轴状态；`:1203` 修正量为输入减输出；`:1204` 决定 output_ready | 生产软件是否把 `result.x/y` 写入 calX/calY、返回失败时实际处理 |
| 模态补偿 | 同文件 `ModalSelfCalAxis::Ingest:738-878` | `z_i=输入_i−当夜基线_i`；成功时 `输出_i=输入_i−gate×(A_i·v−cbar_i)`（`:853-875`）；`use[i]` 为假时不修正该点 | 本批每帧实际 use/learn/gate/modes_ready，JSONL 未保存这些诊断字段 |
| calX/calY → 串联 | 本地串联技能数学说明 `series-network-verification/.../references/algorithms_and_math.md:7-21` | 文档描述像素重建 `center + displacement × scale` 和有效性规则 | 缺少当前串联求解器与调用方，不能确认实际选 raw 或 cal、单位缩放、相机标定、参考约束、测点/设备拓扑及 Jacobian |
| 串联 → MarkerData | 本批字段恒等式，见 `field_identity_checks.csv` | 全部保留的下游记录均满足 `x0 ≈ filteredX0−initX`、`y0 ≈ filteredY0−initY`，绝对差不超过 0.0001 mm | `MarkerData.x/y` 是否就是该版本串联直接输出；滤波函数、窗口、重置规则与故障填充值 |
| 减初值/后处理 | 本地 `module/model-xy0/ModelXY0.cpp:835-850`，`ApplyModelXY0`；`:995-997`，`ApplyPostFilter` | 现有二级模块接收 solved_axis 后调用 `Ingest`，没有在此适配函数里减 initX | 该模块是否在本批线上启用。不能从存在该源码认定被部署 |
| 发布到云 | 未提供发送端实现、发布日志或云平台数据 | 用户说明其业务流程最终减初值后上传 | 实际 JSON 字段、缩放、符号、滤波顺序、异常回退、发布值是否等于本地 x0 |

以上本地路径均相对 `E:/Wiz/GZMetro-Cpp` 或算法目录 `E:/Wiz/GZMetro-Cpp/module/modal-selfcal`。定位到的业务求解器旧技能路径 `D:/Test/VisualTracking/TrackingServer` 在本机不存在；用户已明确不扩展权限范围，停止追索。没有复制或上传额外公司源码。

## 字段语义：确认与限制

| 表/字段 | 本轮可确认的处理阶段 | 限制 |
| --- | --- | --- |
| `Marker_<device>.x/y` | 本批作为共模前坐标输入；设备身份来自真实表名 | 无 DB 写入代码，不能证明与 `RoiResult.uv_mm` 的逐字段赋值；统计用 mm 依据共模 API 契约，保留此限制 |
| `Marker_<device>.calX/calY` | 本批作为共模后实存坐标；与 raw 的差用于判断观察到的补偿 | cal==raw 不能单独证明 gate=0、模式失败、点不 eligible 或修正值恰为零 |
| `RoiCalState` | 分析有效条件为等于 1，另要求数值有限、无冲突键 | 头文件计算状态与历史技能规则支持该筛选；实际串联是否严格使用它仍缺代码 |
| `markerName/markerIndex/markerPos` | 真实观测标识，原样保留 | 编号不能跨设备直接当全局唯一业务键 |
| `MarkerData.x0/y0` | **本批是 filtered−init 的相对结果，不是可直接认定的串联原始结果** | 仅确认恒等式；最终云值仍未知 |
| `MarkerData.initX/initY` | 下游相对值的减数；11/05 12:49 集中改变，见事件与初值索引 | 谁调整、为何调整、如何取初值，无法从数据证明 |
| `MarkerData.filteredX0/Y0` | 恒等式中的被减数；与 x/y 不同且出现滞后/拖尾 | 文档称设备端初级滤波坐标，当前滤波实现/单位转换没有独立核实 |
| `MarkerData.postFilteredX0/Y0` | 本批均恒为 0 | 不作为有效后处理结果，更不能把全零解释为物理零位移或优秀精度 |
| `MarkerData.x/y` | 下游另一处理阶段的实存坐标，用于关联检查 | 当前材料不足以确定它是否直接等于串联 Dis、以及符号约定 |
| `MarkerData.inimmDispX/Y` | 保留列名和数值 | 写入公式缺失，不凭字段名解释为初始化量 |
| `SubDeviceDisData.x/y/x0/y0/Pitch/Yaw` | 设备级时序与姿态候选，保留原值 | 几何定义、角度单位与参与串联方式缺失，不能擅定 Pitch/Yaw 的单位为度 |
| `SinglePoint_<device>` | 单点上游观测与参考/图像编号候选；保留 `pointName,pId,refId,imgId,cameraPos,xv,yu,...` | xv/yu/absv 的确切定义和单位、pointName 与 Marker 的业务映射无实现证据 |
| `EnvData_<device>.temp/humidity/...` | 设备环境相关性候选 | innerTemp、innerLensTemp 为常零；sx/sy/sz 单位未核实，sz 有 ±180 附近折返，不能线性相关后声称姿态因果 |

## 设备映射与重复：不把空 deviceId 补成一个猜测设备

`MarkerData.deviceId` 大部分为空。本轮用 Marker 表中真实出现的 `(markerName, observing_device)` 建立**观测成员关系**，再按完全一致的 `(timestamp, markerName)` 保留所有候选上游边。该关系不是串联拓扑，也不是测点唯一所有权。

同一物理 Marker 可被两台或三台设备观测。多候选不取第一条、不把 x0 复制后混算成独立下游样本、不把相关系数称为设备敏感度。源表/源 rowid 保留在事件 CSV，见 `marker_device_membership.csv`、`upstream_downstream_associations.csv` 与 `data_audit.json`。完整的计数由运行脚本生成；先移除跨卷完全一致观测，再检查业务键冲突。

还有一类更强的字段关系：非空 `MarkerData.deviceId` 明确连接 YXJ2→780639298317、YXJ3→780639333715、YXJ4→780639346578、YXJ5→780639376393、YXJ6→780639414923。全部 18,775 条连接都有同时间戳 SubDeviceDisData，且双方 x/y 完全一致；x0/y0 只在 YXJ2/YXJ3 完全一致，不能将 YXJ4–6 的两个阶段混用。详见 `explicit_device_marker_mapping.csv`。这证明了实存字段关系，仍不是完整串联观测拓扑。

## 运行配置、状态与时间

- V51 默认值在 `versions/V51/ModalSelfCal.h:13-36`：基线 22–23、学习到次日 02、apply_end=次日 07、20 分钟斜坡、K=3、历史 3 夜、max_frame_dev=8、max_frame_residual=2.5。它们不等于已核验的现场实际配置。
- `Init:1132-1148` 默认等待导入；`ImportState:1152-1173` 检查设备、点表、ConfigKey 和完整状态；`ConfigKey:1064-1070` 包含数学配置。已有状态不匹配不会自动安全续算。
- `ModesFrom:456-527` 用历史统计建立模态：有效率、fit_only 前缀、spread、guard、特征值等均会影响学习和 use 资格。一个点可以未进入学习集但通过回归被修正；**未学习点≠未修正点**。只有 use=false 或无基线等条件才可能完全不修正，具体需状态证明。
- `Ingest:794-813` 有历史时在 23 点后用历史模态；`:835-840` 冷启动可能到 02 点后才开始渐入。`:849-864` gate>0 仍可能 WAIT_MODES 或 DEGRADED_FRAME。
- `SolveV:530-578` 的 8 mm 绝对偏差初筛与 2.5 mm 残差筛选决定求解学习点。被剔出求 v 的学习点不等价于该点输出一定透传；输出另由 use 和有效性控制。
- 每帧实际日志字段在 `Process:1205`，但本批 JSONL 没有该日志及 gate/modes_ready。所有报表阶段列明确叫 `nominal_phase`，实际字段标 `not_recorded`；仅将观测到的非零 raw−cal 作为有补偿发生的证据。不能把 nominal_full_correction 全部称为真正 CORRECTING。
- 当前部署“右线 V51、左线 11/11 V53”来自项目负责人；本轮没有现场 DLL 指纹、当前右线配置或匹配起始状态。本仓库左线参考状态不能用于填补右线状态。
- 本地 `.51` DLL 头文件仍有 StreamKey 和 seed 许可接口，而仓库 V51 状态类接口已简化为设备号。DLL 文件版本号 `.51` 与算法目录名 V51 不能互相替代为部署身份证明。

## 为什么不能声称串联放大已获证明

若串联几何已知，局部线性传播可写作 `δq ≈ J δu`，多个设备的同向扰动能否叠加取决于 J、坐标投影、控制/传递点及约束。当前没有该 J、标定与初始化；这只是下一轮验证框架，不是本轮数值结果。

本轮可验证同名候选的 raw/cal、下游 x、filtered、init 与 x0 的时间关系，不能据斜率把它认定为几何放大因子。无法运行完整同条件“原始输入/修正输入”串联 A/B；两路必须有相同时间戳、有效性、标定、拓扑、初始化和独立状态，不能用现场 x0 充当原始路解算结果。
