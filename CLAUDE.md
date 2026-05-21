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
python -m uasset_read file.uasset  # 等价（模块入口）

# 测试
python -m pytest tests/ -v                    # 全部测试
python -m pytest tests/ -v --cov=uasset_read  # 带覆盖率
python -m pytest tests/kismet/ -v             # 单个目录
python -m pytest tests/test_xyz.py -v         # 单个文件
python -m pytest tests/test_xyz.py::test_func -v  # 单个测试
python -m pytest tests/ -k "kismet" -v        # 按关键词过滤
```

测试资产：`E:\Develop\lib\UnrealEngine\Samples\FirstPerson`（源码参考文件夹，非项目内）
UE5.8 源码参考路径：`D:\Program Files\Epic Games\Engine\UE_5.8\Engine\Source`

## 当前状态

**v12.0 开发中**（2026-05-21 启动）— N2C 中间格式 + 节点分类体系 + 处理器架构
v11.0 (P61-66) 已归档 2026-05-21。1271 tests collected。

| Phase | 内容 | 状态 |
|-------|------|------|
| 67 | UE5.4+ PropertyTag 兼容 + FString 健壮性 | 🆕 Planned |
| 68 | N2CNodeTypeRegistry — 100+ K2Node 语义类型注册表 | 🆕 Planned |
| 69 | Processor 模式替代 switch/case | 🆕 Planned |
| 70 | N2CStruct JSON Schema — LLM 优化中间格式 | 🆕 Planned |
| 71 | 执行流链式表达 N1->N2->N3 | 🆕 Planned |

详见 `.planning/STATE.md` 和 `.planning/ROADMAP.md`。

## 架构

管道：`.uasset → FArchive → Deserializer → Models → OutputFormatter`

扩展：GraphParser → AdvancedPropParser → DependencyGraphBuilder → **PackageLinker（v7.0）** → KismetDecompiler（v11.0）→ AgentTranslator（v11.0）

v7.0 引入两阶段对象图重建：`PackageLinker.link()` 从 ImportMap/ExportMap 创建 UObjectInstance 外壳 → `preload()` 按需反序列化属性。

| 模块 | 文件 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器（字节交换/mmap/边界验证） |
| 序列化 | `serializers/` | PackageSummary/Import/Export/PropertyTag/Graph |
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

## 关键架构模式（需跨文件理解）

### FArchive 流式解析

所有二进制读取必须使用 `FArchive` 流式方法（`read_int32()`, `read_fstring()`, `read_tarray()` 等），**禁止直接 `read(n)` 裸字节读取**。FArchive 自动处理字节序交换和边界验证。

### 管线容错约定

- Kismet 反编译失败**不阻塞**主管线（D-10 约定），`_extract_kismet_decompiled()` 中 try/except 吞掉异常
- 解析器 tolerant 模式为默认（`--tolerant` CLI 标志），`--strict` 才在警告时终止
- 可恢复错误记录到 `warnings` 列表，不抛异常

### PackageLinker 两阶段模式

```
Phase 1: link()   — 从 ImportMap/ExportMap 创建 UObjectInstance 外壳（仅 Header）
Phase 2: preload() — 按需反序列化属性数据到外壳
```

使用 `parse_uasset_with_linker()` 入口函数，返回 `LinkerParseResult`。

### Kismet 表达式层次结构

```
kismet/tokens.py        — EExprToken 枚举（~100+ token 类型）
kismet/bytecode_extractor.py — FKismetArchive，原始字节码读取
kismet/expressions/     — KismetExpression 子类（base.py + 各语义类型）
kismet/translator.py    — KismetTranslator，AST → C++ 伪代码
kismet/body_builder.py  — 结构化控制流重建
kismet/pipeline.py      — decompile_single_function() 端到端入口
```

### 数据模型分层

```
models/core.py       — 基础类型（FEdGraphPinType 等）
models/node_types.py — K2Node 专用类型（K2Node_CallFunction 等）
models/properties.py — 属性值类
models/transforms.py — VectorValue/RotatorValue/ScaleValue
models/blueprint.py  — BlueprintMetadata/Variable/Function/Event
models/result.py     — ParseResult（主解析结果容器）
```

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
- `.planning/milestones/` — 已归档里程碑（v7.0-v11.0）
- `.planning/MILESTONES.md` — 历史里程碑

## 上下文与效率

- 上下文 >70% 时执行 `compact`
- 独立任务优先并行 subagent，主线程只看结构化摘要
- **GSD：** wave 或 PLAN 之间互补不干扰时均可并行执行
- 有依赖或共享状态的任务不可并行；写冲突风险可通过 git 分支管理规避
