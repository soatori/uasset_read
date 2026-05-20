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

**v11.0 开发中** — Phase 61✅ (Kismet 表达式系统), Phase 62✅ (字节码→AST), Phase 63✅ (AST→C++ 伪代码)。Phase 64✅ (Kismet 集成), Phase 65✅ (图解析修复)。Phase 66✅ (Agent 翻译管线 — translator + writer 已实现)。1271 tests collected。
v12.0 (N2C 中间格式 + 节点分类体系 + 处理器架构) 计划中。详见 `.planning/STATE.md`。

## 架构

管道：`.uasset → FArchive → Deserializer → Models → OutputFormatter`

扩展：GraphParser → AdvancedPropParser → DependencyGraphBuilder → **PackageLinker（v7.0）** → KismetDecompiler（v11.0）→ AgentTranslator（v11.0）

v7.0 引入两阶段对象图重建：`PackageLinker.link()` 从 ImportMap/ExportMap 创建 UObjectInstance 外壳 → `preload()` 按需反序列化属性。

| 模块 | 文件 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器（字节交换/mmap） |
| 序列化 | `serializers/` | PackageSummary/Import/Export/PropertyTag |
| 数据模型 | `models/` | UEdGraph/Node/Pin + 属性数据类 + Transform 值类 |
| 解析器 | `parsers/` | 14 种属性类型 + 分派器 |
| 蓝图 | `blueprint/` | 变量/组件变换/元数据提取 |
| 图解析 | `graph/` | 执行流/数据流/连接映射/function_graphs |
| 链接器 | `link/` | PackageLinker / UObjectInstance（UE FLinkerLoad 模式） |
| Kismet | `kismet/` | 字节码提取/EExprToken/KismetExpression AST/C++ 翻译（v11.0） |
| CPP Gen | `cpp_gen/` | C++ 骨架/函数提取/IR 格式化（v10.0） |
| Agent | `agent/` | AgentTranslationPipeline + CppFileWriter（v11.0 P66） |
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
| 图解析 | `extract_blueprint_graphs`, `build_execution/data_flows`, `build_connections_map`, `build_function_graphs` |
| 链接器 | `PackageLinker`, `UObjectInstance`, `LinkerParseResult`, `parse_uasset_with_linker` |
| Kismet | `EExprToken`, `KismetExpression`, `FKismetArchive`, `KismetTranslator`, `decompile_uasset` |
| CPP Gen | `CppClassIR`, `CppMethodIR`, `CppPropertyIR`, `extract_cpp_class_skeleton`, `format_cpp_header` |
| Agent | `AgentTranslationPipeline`, `translate_blueprint_to_cpp`, `CppFileWriter`, `write_cpp_class_files` |
| 格式化 | `format_json/text/markdown/graphs_*`, `build_status/schema_info` |
| CPF 标志 | `CPF_Edit`, `CPF_BlueprintVisible`, `CPF_InstancedReference`, `CPF_EditAnywhere` 等 |
| 管线/CLI | `parse_uasset`, `parse_uasset_with_linker`, `python -m uasset_read` 或 `uasset-read` |

## 规划文档

- `.planning/ROADMAP.md` — 阶段路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/milestones/` — 已归档里程碑（v7.0-v9.0）
- `.planning/MILESTONES.md` — 历史里程碑

## 上下文与效率

- 上下文 >70% 时执行 `compact`
- 独立任务优先并行 subagent，主线程只看结构化摘要
- **GSD：** wave 或 PLAN 之间互补不干扰时均可并行执行
- 有依赖或共享状态的任务不可并行；写冲突风险可通过 git 分支管理规避
