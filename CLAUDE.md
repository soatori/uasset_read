# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Language

请使用中文回复以及编写文档

## 项目概述

Unreal Engine .uasset 文件解析器 — 让 AI 代理在不依赖 UE 编辑器的情况下读取蓝图内容。

## 快速参考

```bash
pip install -e ".[dev]"           # 安装
uasset-read file.uasset           # 解析文件
python -m pytest tests/ -v        # 测试
```

测试资产：`E:\Develop\lib\UnrealEngine\Samples\FirstPerson`（源码参考文件夹，非项目内）

## 当前状态

**v12.0 已归档** — Phase 67✅ (序列化修复), Phase 68✅ (N2CNodeTypeRegistry), Phase 69✅ (节点处理器架构), Phase 70✅ (N2CStruct JSON Schema), Phase 71✅ (执行流链式表达)。1290 tests collected。`__version__` 仍为 `9.0.0`（尚未 bump）。

**v13.0 活跃** — Phase 72-A✅ (Pin 连接二进制诊断，2 bugs 定位)，Phase 72-B✅ (Pin 连接修复)，Phase 72-C✅ (BPGC 字节码提取)，Phase 72-UAT✅ (1319 tests passed)，Phase 72-D⬜ (FString/FName 区分待执行)，Phase 72-E🔴 (EventGraph 节点解析修复插入中)，Phase 72-F🔴 (BPGC 缓存隔离修复插入中)。

## 架构

管道：`.uasset → FArchive → Deserializer → Models → OutputFormatter`

扩展：GraphParser → AdvancedPropParser → DependencyGraphBuilder → **PackageLinker（v7.0）**

v7.0 引入两阶段对象图重建：`PackageLinker.link()` 从 ImportMap/ExportMap 创建 UObjectInstance 外壳 → `preload()` 按需反序列化属性。

| 模块 | 文件 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器（字节交换/mmap） |
| 序列化 | `serializers/` | PackageSummary/Import/Export/PropertyTag |
| 数据模型 | `models/` | UEdGraph/Node/Pin + 属性数据类 + Transform 值类 |
| 解析器 | `parsers/` | 14 种属性类型 + 分派器 |
| 蓝图 | `blueprint/` | 变量/组件变换/元数据提取 |
| 图解析 | `graph/` | 执行流/数据流/连接映射/链式表达（Phase 71） |
| 链接器 | `link/` | PackageLinker / UObjectInstance（UE FLinkerLoad 模式） |
| Kismet | `kismet/` | 字节码提取/反编译/C++翻译/BPGC fallback（Phase 61-64, 72-C） |
| N2C | `n2c/` | N2CStruct/Graph/Node/Pin 中间格式 JSON Schema（Phase 70） |
| Agent | `agent/` | AgentTranslationPipeline + CppFileWriter（Phase 66） |
| CPP Gen | `cpp_gen/` | C++ 骨架提取/IR formatter（Phase 56-60） |
| 格式化 | `formatters/` | JSON/Text/Markdown/Mermaid |
| CLI | `cli.py` | argparse 入口 |
| 管线 | `parse_uasset.py` | 主编排函数（含 `parse_uasset_with_linker`） |

**技术栈**：Python 3.10+，零运行时依赖，setuptools + pytest。

## 文件组织

```
src/uasset_read/  # 源码    tests/          # 测试
.planning/        # 规划    temp/            # 缓存/临时生成文件
uasset_read_cpp/  # C++参考 UnrealEngine/ LyraStarterGame/  # 外部（Git忽略）
```

> 所有缓存、临时性生成文件统一放在 `temp/` 目录，已在 `.gitignore` 中排除。

## gsd-sdk 使用

仅支持 3 个命令：`run "<prompt>"` / `auto` / `init [input]`

**不支持** `query`、`list`、`get` 等子命令（会报错）。查 phase 信息请直接读 `.planning/` 文件或用 GSD slash commands。

## API 导出（`from uasset_read import X`）

按模块分类，具体符号见各模块 `__init__.py`：

| 类别 | 核心符号 |
|------|---------|
| 常量/异常 | `PACKAGE_FILE_TAG`, `MMAP_THRESHOLD`, `UAssetError`, `VersionError`, `ParseError` |
| 序列化 | `PackageFileSummary/Index`, `ObjectImport/Export`, `FArchive`, `PropertyTag` |
| 数据模型 | `UEdGraph`, `UEdGraphNode`, `UEdGraphPin`, `FEdGraphPinType`, `K2Node*` 系列 |
| 变换值类 | `VectorValue`, `RotatorValue`, `ScaleValue`, `format_transform_value` |
| 属性 | `PropertyValue`, `Struct/Map/Set/Enum/Text/DelegateValue`, `parse_*` 系列 |
| 蓝图 | `BlueprintMetadata/Variable/Function/Event`, `extract_blueprint_*`, `parse_component_transform` |
| 图解析 | `extract_blueprint_graphs`, `build_execution/data_flows`, `build_connections_map`, `build_execution_chains` |
| 链接器 | `PackageLinker`, `UObjectInstance`, `LinkerParseResult`, `parse_uasset_with_linker` |
| Kismet | `EExprToken`, `KismetExpression`, `KismetTranslator`, `to_function_body`, `decompile_uasset` |
| N2C | `N2CStruct`, `N2CGraph`, `N2CNode`, `N2CPin`, `to_n2c_json`, `from_n2c_json` |
| Agent | `AgentTranslationPipeline`, `translate_blueprint_to_cpp`, `CppFileWriter`, `write_cpp_class_files` |
| 格式化 | `format_json/text/markdown/graphs_*`, `build_status/schema_info` |
| CPF 标志 | `CPF_Edit`, `CPF_BlueprintVisible`, `CPF_InstancedReference`, `CPF_EditAnywhere` 等 |
| 管线/CLI | `parse_uasset`, `parse_uasset_with_linker`, `python -m uasset_read` 或 `uasset-read` |

## 规划文档

- `.planning/ROADMAP.md` — 阶段路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/milestones/` — 已归档里程碑（v7.0-v12.0）
- `.planning/MILESTONES.md` — 历史里程碑

## 上下文与效率

- 上下文 >70% 时执行 `compact`
- 独立任务优先并行 subagent，主线程只看结构化摘要
- **GSD：** wave 或 PLAN 之间互补不干扰时均可并行执行
- 有依赖或共享状态的任务不可并行；写冲突风险可通过 git 分支管理规避
