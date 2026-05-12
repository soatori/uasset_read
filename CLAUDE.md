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

测试资产：`E:\Develop\lib\UnrealEngine\Samples\FirstPerson`

## 当前状态

**v6.0 完成** — 373 passed, 71 skipped, 0 failed。模块化包在 `src/uasset_read/`。

## 架构

管道：`.uasset → FArchive → Deserializer → Models → OutputFormatter`

扩展：GraphParser → AdvancedPropParser → DependencyGraphBuilder

| 模块 | 文件 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器（字节交换/mmap） |
| 序列化 | `serializers/` | PackageSummary/Import/Export/PropertyTag |
| 数据模型 | `models/` | UEdGraph/Node/Pin + 属性数据类 |
| 解析器 | `parsers/` | 14 种属性类型 + 分派器 |
| 蓝图 | `blueprint/` | 变量/组件变换/元数据提取 |
| 图解析 | `graph/` | 执行流/数据流/连接映射 |
| 格式化 | `formatters/` | JSON/Text/Markdown/Mermaid |
| CLI | `cli.py` | argparse 入口 |
| 管线 | `parse_uasset.py` | 主编排函数 |

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
| 属性 | `PropertyValue`, `Struct/Map/Set/Enum/Text/DelegateValue`, `parse_*` 系列 |
| 蓝图 | `BlueprintMetadata/Variable/Function/Event`, `extract_blueprint_*`, `parse_component_transform` |
| 图解析 | `extract_blueprint_graphs`, `build_execution/data_flows`, `build_connections_map` |
| 格式化 | `format_json/text/markdown/graphs_*`, `build_status/schema_info` |
| 管线/CLI | `parse_uasset`, `python -m uasset_read` 或 `uasset-read` |

## 规划文档

- `.planning/ROADMAP.md` — 50 阶段路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/REQUIREMENTS.md` — 需求追溯
- `.planning/PROJECT.md` — 项目概览
- `.planning/MILESTONES.md` — 历史里程碑
