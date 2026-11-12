# 独立稳定趋势版本：可以影子验证，不能替换监测值

提供 `scripts/XTrendL1.h` 单头C++数值模块、C ABI和Python CSV适配器。接入点是原V51/V53完成calX之后的只读副本；不在Raw输入、学习历史、串联解算或告警链路中插入。现场尚未部署，本目录示例也不连接数据库或网络。

```text
原流程 → 原calX/calY → 原串联/减初值/原报警和发布（完全保留）
                 └只读副本→ XTrendL1 → stableTrendX + ΔX + 资格/版本
```

`stableTrendX`是观测坐标域calX的稳定趋势，当前没有云平台最终位移的串联映射，不能把该字段直接替换成云平台最终X。原事件/报警仍按原值判定；原界面需能查看原曲线与新增差值。D不判断物理事件，适配器的新增事件列不是原告警状态，原告警字段始终原样保留。

最小可运行示例（仓库根目录，先build_l1.py）：

```powershell
python analysis/x_trend_shadow/scripts/shadow_cli.py `
  analysis/x_trend_shadow/demo/original.csv `
  analysis/x_trend_shadow/.work/my_shadow.csv `
  --points analysis/x_trend_shadow/demo/points.json `
  --state-out analysis/x_trend_shadow/.work/my_shadow_state.json
```

输出必须是新文件。输入按设备曝光业务时间排序、每帧一个点最多一行、点序固定；必要字段timestamp/markerName/calX/base_gate/base_ready/base_ncorrected。calY及alarmPayload等任意原字段按字符串逐项复制。只追加stableTrendX、stableTrendDeltaX、stableTrendEligible、stableTrendEvent、stableTrendForAlarm=0、stableTrendVersion。每设备独立状态；JSON只属于影子模块，绝非现场ModalSelfCal状态包。重启传入`--state-in`可延续同一模型状态。

D不检测物理事件，stableTrendEvent留空；stableTrendNumericFallback记录数值资格失败。若任一点原对偶证书未达标，整设备该帧透传B0并标无资格；本轮全部历史/注入未触发此回退。直接C++调用同样检查Point.gap，不能忽略证书。

`demo/`使用实际独立B0输出和**合成不透明告警测试载荷**。3240行、29160个原字段逐项不变，完整运行与分块JSON重启结果逐行一致。不是实测现场报警触发试验。

回退：无效观测不造值，>90s/反向时间重置该点短窗；原核心未ready或无实际修正、白天均透传原值。早晨跟随实际gate渐出，07:20后附加差值严格为0；即使渐出连续，逐帧仍可能产生可量化新增变化，详见night_day_transitions，不能声称切换无代价。若未提供实际状态，禁止按时钟假定已修正。

研究D对1mm持续阶跃的典型额外95%延迟约9–13分钟，单帧冲击削弱、转折可过冲；这些代价要求显示明确标识、原通道和事件可见。当前适合客户并列审阅和影子运行，不满足替换监测、安全告警或“高精度消漂”的条件。新夜验证需冻结版本/阈值后开展，不以当前历史曲线重新挑参数。
