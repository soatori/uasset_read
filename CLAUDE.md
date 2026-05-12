# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言设置

请使用中文进行所有回复和编写文件。

## 项目概述

解析 Unreal Engine .uasset 文件的 Python 工具，使 AI 代理能够在不依赖 UE 编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

## 当前状态

**v6.0 模块化重构已完成** — 373 个测试通过，71 个跳过，0 个失败。旧版 `uasset_read.py` 已删除。

代码库结构：
- `src/uasset_read/` — 完整模块化包（v6.0），包含序列化、数据模型、属性解析、蓝图提取、图解析、格式化输出、CLI 入口

## 常用命令

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 解析 .uasset 文件
python -m uasset_read path/to/file.uasset
# 或使用 CLI 入口（pip install -e . 后）
uasset-read path/to/file.uasset

# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_graph_parsing.py -v

# 运行单个测试函数
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v

# 运行测试（简要输出）
python -m pytest tests/ --tb=short

# 查看特定解析结果
python -c "
from uasset_read import parse_uasset
import json
r = parse_uasset('BP_FirstPersonCharacter.uasset')
print(json.dumps(r.to_dict(), indent=2))
"
```

测试资产位于 `E:\Develop\lib\UnrealEngine\Samples\FirstPerson`。

## 架构

采用镜像 UE 的 FArchive 管道模式：

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓ 扩展组件
          GraphParser (Phase 7/31)
          AdvancedPropParser (Phase 9/30)
          DependencyGraphBuilder (Phase 10)
```

### 模块结构 (`src/uasset_read/`)

| 模块 | 路径 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap、边界验证 |
| 常量 | `constants.py` | 版本号、属性类型阈值、MMAP_THRESHOLD |
| 异常 | `exceptions.py` | UAssetError、VersionError、ParseError、ErrorContext |
| 序列化 | `serializers/` | PackageFileSummary、ObjectImport/Export、PackageIndex、PropertyTag |
| 数据模型 | `models/` | UEdGraph/Node/Pin、节点类型子类、ParseResult、蓝图元数据、属性数据类 |
| 解析器 | `parsers/` | 14 种属性类型解析函数 + 分派器 |
| 蓝图 | `blueprint/` | 蓝图变量提取、组件变换解析、元数据提取 |
| 图解析 | `graph/` | 蓝图图提取、执行流/数据流构建、连接映射 |
| 格式化 | `formatters/` | JSON/Text/Markdown 输出格式化、Mermaid 图表 |
| CLI 入口 | `cli.py` | argparse 参数解析、格式路由、退出码管理 |
| 主解析管线 | `parse_uasset.py` | 完整解析管线编排函数 |

## 技术栈

- **语言**: Python 3.10+（match/case，类型提示）
- **依赖**: 零运行时依赖 — 仅使用标准库（struct、mmap、dataclasses、json、argparse）
- **构建**: setuptools（src layout），pyproject.toml 配置
- **测试**: pytest（可选 dev 依赖）

## 注意事项

- 使用 `python -m uasset_read` 或 `uasset-read`（pip install -e . 后）作为 CLI 入口
- 新版 `src/uasset_read/` 包含完整解析管线，`parse_uasset` 函数位于 `parse_uasset.py`
- 公共 API 通过 `__init__.py` 导出 100+ 项，使用 `from uasset_read import X` 即可

## gsd-sdk 使用

gsd-sdk v0.1.0 已全局安装（npm），但仅支持以下三个命令：
- `gsd-sdk run "<prompt>"` — 运行完整里程碑
- `gsd-sdk auto` — 运行自主生命周期（discover → execute → advance）
- `gsd-sdk init [input]` — 引导新项目（PRD 或描述文本）

**不支持 `gsd-sdk query`、`gsd-sdk list` 等子命令。** 这些是 AI agent 幻觉出来的语法。如需查询 phase 状态、计划、需求等信息，请直接读取 `.planning/` 目录下的文件，或使用 GSD slash commands（如 `/gsd-progress`）。

## 文件组织

```
uasset_read/
├── src/uasset_read/        # 源代码模块
├── tests/                  # 测试文件
├── uasset_read_cpp/        # C++ 移植参考
├── .planning/              # GSD 规划文档
├── output/                 # 输出文件（JSON/TXT/MD）
├── debug/                  # 调试文件
├── reports/                # 报告文件
└── test/                   # 测试脚本
```

外部目录（Git 忽略）：
- `UnrealEngine/` — UE 引擎源码参考
- `LyraStarterGame/` — 示例游戏资产

**规则：**
- 源代码 → `src/uasset_read/`
- 测试 → `tests/`
- 规划 → `.planning/`
- 输出产物 → `output/`、`debug/`、`reports/`

## API 导出

当前公共 API（通过 `src/uasset_read/__init__.py`，100+ 导出项）：

```python
from uasset_read import (
    # 常量
    PACKAGE_FILE_TAG, MMAP_THRESHOLD, PROPERTY_TAG_COMPLETE_TYPE_NAME, ...
    # 异常
    UAssetError, VersionError, ParseError, ErrorContext,
    # 序列化模块
    PackageFileSummary, PackageIndex, ObjectImport, ObjectExport,
    read_package_summary, read_name_table,
    read_import_map, read_export_map, detect_blueprint, ...
    # FArchive（基础读取器）
    FArchive,
    # 数据模型（Phase 29-30）
    UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType, FMemberReference,
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction,
    ParseResult, StatusInfo,
    BlueprintMetadata, BlueprintVariable, BlueprintFunction, BlueprintEvent,
    PropertyTag, PropertyValue, StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue,
    # 解析器（Phase 30）
    parse_property_value, parse_properties_from_export,
    parse_bool_property, parse_int_property, parse_float_property, parse_str_property,
    parse_array_property, parse_struct_property, parse_map_property, ...
    # 蓝图（Phase 30）
    extract_blueprint_variables, parse_component_transform, extract_blueprint_metadata,
    # 主解析管线（Phase 33）
    parse_uasset,
    # 图解析（Phase 31）
    extract_blueprint_graphs, build_execution_flows, build_data_flows, build_connections_map,
    # 格式化（Phase 32）
    format_json_full, format_json_summary, format_text_full, format_text_summary,
    format_markdown, format_graphs_json, build_status_info, build_schema_info,
    # CLI 入口（Phase 33）
    # 通过 python -m uasset_read 或 uasset-read 使用
)
```

## 规划文档

- `.planning/ROADMAP.md` — 版本路线图（50 个阶段）
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/REQUIREMENTS.md` — 需求追溯表
- `.planning/PROJECT.md` — 项目概览
- `.planning/MILESTONES.md` — 已发布里程碑历史
