# GZMetro ModalSelfCal

## 2026-11-17 当前 V54-Astra 协作快照

此分支 `collab/v54-astra-20261117` 在原V54协作分支之上增加当前Astra源码、12设备初始状态、诊断报告及冻结回放数据清单（大数据本次未上传）。它不是现场升级或物理精度认证。

- **[完整中文 Agent Spec / Memory](V54-Astra/github_handoff_20261117/AGENT_SPEC_ZH.md)**
- **[一段可复制的 Agent Prompt](V54-Astra/github_handoff_20261117/PROMPT_ZH.md)**
- [当前版本、编译与复现入口](V54-Astra/README.md)

当前双文件位于 `V54-Astra/round8_release_111315/source/`。R11中的J活动门控已经否决，参考驱动增量方案尚未实现。原 `versions/V54` 保留2026-11-13快照；旧main中的V51/V53现场表格是历史记录，不代表2026-11-17现场版本已重新核实。

下面保留旧仓库说明，便于追溯。

---

# GZMetro ModalSelfCal

广州地铁模态自校准算法协同开发仓库。源码导入日期：2026-11-11。

| 线路 | 当前上线版本 | 状态来源 |
| --- | --- | --- |
| 左线 | V53，2026-11-11 上线 | 项目负责人本次说明 |
| 右线 | V51 | 项目负责人本次说明 |

现场 DLL、运行配置与当前状态包尚未在本次导入中独立核验指纹。历史数据库中的值保留原样，不能把全周数据都认定为当前版本的输出。

## V54 协作快照（2026-11-13）

- [V54 源码与构建入口](versions/V54/README.md)，对应本地 `modelselfcal-V54` 当前快照。
- [远程协作交接与已知问题](docs/V54_COLLABORATION.md)：YD2603 历史学习/回归保护修复尚未实现。
- 构建时显式选择 `-DMODALSELFCAL_VERSION=V54`；仓库默认仍为 V53。

## 代码和版本

- `versions/V51/`：原 `1030-modelselfcal-V51` 中的一 CPP 一 H，字节不改动。
- `versions/V53/`：原 `modelselfcal-V53-1110/modelselfcalV52/algorithm` 中的一 CPP 一 H，字节不改动。
- V53 原交付目录和文档沿用 V52 字样，头文件注释和状态格式可能仍标为 V50。这里按项目负责人的上线版本命名，具体文件身份见 [来源清单](docs/source_manifest.json)。
- [逐行差异](docs/V51_to_V53.diff) 记录两个快照的实际变化。
- [接入说明](docs/integration.md) 以当前头文件为准。`docs/original_V53_package_integration.txt` 是原始交付文档留档，其中历史效果说明和状态包说明不作为本次独立验收结论。
- [左线参考状态包](reference_states/README.md) 保留版本目录中的历史快照，按设备、时间和配置单独留档；其中 V51 左线参考包不能当作右线当前状态。

V51 默认 `max_frame_dev=8.0`，V53 默认 `max_frame_dev=0.0`。调用方显式配置会覆盖默认值；状态导入同时检查数学参数指纹。

## 编译

C++17，无额外数学库。一次构建选择一个版本，避免同名符号重复链接。

```sh
cmake -S . -B build/V53 -DMODALSELFCAL_VERSION=V53
cmake --build build/V53 --config Release
ctest --test-dir build/V53 -C Release --output-on-failure
```

构建 V51 时把两个命令中的目录和版本参数改为 V51。冒烟验证覆盖白天透传、状态字节往返和下一帧续算，不代表现场位移精度验证。

## 近一周数据库

数据窗口：北京时间 **2026-11-05 00:00 至 2026-11-12 00:00（结束不含）**，实际仅到本地数据库已有的最新记录。左右线独立保存，原始库保持只读。

见 [数据说明](data/README.md) 和 `data/manifest.json`，包括来源数据库、表结构、行数、时间覆盖、导出错误及校验值。全量记录使用按库、表分片的压缩可读文件，提供解压与读取脚本。数据库缺失时段不插值，不把离线回放混入现场原始记录。

## 协作

从 `main` 创建工作分支，通过 PR 合入。修改算法时记录源码、配置、点表、状态包和数据窗口；现场升级前由项目负责人确认配套 DLL、参数与状态包。左、右线的数据和状态不得交叉使用。原始状态包不随本次源码快照自动认定为当前现场状态。

