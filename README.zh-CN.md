# uasset_read

解析 Unreal Engine `.uasset` 文件的 Python 工具，使 AI 代理能够在不依赖 UE 编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

[English](README.md) | [中文版](README.zh-CN.md)

## 状态

| 指标 | 值 |
|------|-----|
| 版本 | **v6.0**（模块化重构完成，Phase 35 进行中） |
| 测试 | **397 passed, 71 skipped, 0 failed** |
| 新模块 | `src/uasset_read/` — 15 个模块，50+ 公共 API 导出 |
| 旧版入口 | `uasset_read.py` — Phase 33 后删除 (2026-05-12) |

### 当前阶段：Phase 35b - Pin 连接深度调试与修复

**状态**: 🟢 PLAN.md 已创建，P0 优先级（阻塞）  
**目标**: 修复 `linked_to_raw` 为空根因，恢复 execution_flows/data_flows  
**时间线**: 2026-05-13 创建

**关键修复已完成**:
- ✅ Phase 35a - 快速修复 (start_event fallback, 脚本清理, logging 迁移)
- ✅ Phase 34 - 等价验证 (397 passed, 0 bugs to fix)
- ✅ Phase 33 - 入口适配 + 旧 uasset_read.py 删除
- ✅ Phase 33a - UE5 序列化修复 (FText, PropertyTag 容错)

**下一步任务**:
1. Phase 35b - Pin 连接深度调试 (35b-01 至 35b-05)
2. Phase 35c - v6.0 里程碑完成与发布准备

### 问题描述

| 问题 | 来源 | 影响 |
|------|------|------|
| `read_pin_array` 返回空列表 (array_count=0) | AUDIT-REPORT.md FINDING-2/5 | execution_flows 无法构建 |
| `pins_offset` 动态扫描不准确 | Phase 22 VERIFICATION.md | Pin 解析偏移错误 |
| UE5 UEdGraphPin 格式版本差异 | Phase 31 graph 模块 | Pin 字段错位 |
| `FText` 跳过逻辑影响偏移 | Phase 33a, 35a | 后续字段读取错误 |

**计划任务**:
- 35b-01: 调试环境搭建 (二进制分析工具 + DEBUG_PIN_PARSING 增强)
- 35b-02: read_ue_graph_pin 字段序列化顺序验证与修复
- 35b-03: read_pin_array 修复 (array_count 正确读取)
- 35b-04: FText 跳过逻辑修复
- 35b-05: execution_flows / data_flows 集成测试验证

**产出文档**:
- `.planning/phases/35b-pin-connection-debug/35b-PLAN.md` — 完整计划
- `.planning/phases/35b-pin-connection-debug/35b-CONTEXT.md` — 问题上下文

**成功标准**:
- `pin.linked_to_raw` 非空，包含连接引用
- `execution_flows` 能追踪从 Event 到 CallFunction 的完整链路
- `data_flows` 能提取非 exec pins 的数据传递关系
- BP_FirstPersonCharacter.uasset 的 EventGraph 能输出 IA_Jump → Jump → StopJumping 执行链路
- 全部测试通过 (411+ passed, 0 failed)

**相关修复记录**:
- Phase 35a - 快速修复 (不包含根因修复)
- Phase 33a - UE5 序列化问题修复 (FText, PropertyTag, 偏移校验 - 部分相关)

### Phase 28a 修复记录

**关键发现：UE5 节点序列化格式变化**

UE5 将 `NodePosX`, `NodePosY`, `NodeGuid` 作为 PropertyTags 存储在 `script_serial` 区域，而非 pins 解析后的裸 i32 字段。

**修复内容**:

- uasset_read.py: 在 PropertyTags 循环中提取 NodePosX/NodePosY/NodeGuid/NodeComment
- build_graphs_summary: 过滤空 flow (EnhancedInputAction Started/Ongoing)
- test_property_parsing.py: 12 个测试更新为 FPropertyTypeName 格式
- test_output_formatting.py: mock 数据连接方向修复

**测试结果**：411 passed, 47 skipped

## 功能

- **PackageFileSummary** — 文件头解析
- **NameMap** — 名称表提取
- **ImportMap** — 依赖映射
- **ExportMap** — 导出映射
- **蓝图图解析** — UEdGraph / Node / Pin 结构
- **高级属性** — Struct / Map / Set / Enum / Text / Delegate
- **蓝图变量提取** — 变量、函数、事件、元数据
- **组件变换解析** — Transform / Rotation / Scale
- **依赖分析** — ImportMap + SoftObjectPaths 依赖图构建
- **循环依赖检测** — ImportMap 相互引用检测
- **执行流追踪** — Event → CallFunction 链路追踪
- **数据流提取** — 非 exec pins 的数据传递关系

## 安装

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
pip install -e ".[dev]"
```

零运行时依赖，仅需 Python 3.10+。

## 使用

### CLI

```bash
# 基本用法
uasset-read path/to/file.uasset           # JSON 输出到 stdout
uasset-read path/to/file.uasset --output output.json   # 保存到文件

# 输出模式
uasset-read path/to/file.uasset --summary      # 仅摘要（不含属性）
uasset-read path/to/file.uasset --graphs       # 仅图结构
uasset-read path/to/file.uasset --output-md    # Markdown 输出

# 严格模式
uasset-read path/to/file.uasset --strict       # 遇到警告即停止
uasset-read path/to/file.uasset --tolerant     # 容错模式（默认）
```

### Python API

```python
from uasset_read import parse_uasset

# 解析 .uasset 文件
result = parse_uasset('BP_FirstPersonCharacter.uasset')

# 访问解析数据
print(result.name_map)          # 名称表
print(result.import_map)        # 导入依赖
print(result.export_map)        # 导出表
print(result.blueprint)         # 蓝图信息
print(result.graphs)            # 蓝图图结构
print(result.dependencies)      # 依赖图

# 输出格式
print(result.format_json())     # 完整 JSON 输出
print(result.format_text())     # 可读文本
print(result.format_markdown()) # Markdown（含 Mermaid 图）
```

### 模块级 API（v6.0）

```python
from uasset_read import (
    # 数据模型
    UEdGraph, UEdGraphNode, UEdGraphPin,
    ParseResult, BlueprintMetadata, BlueprintVariable,
    PropertyTag, PropertyValue, StructValue, MapValue, EnumValue,

    # 解析器
    parse_property_value, parse_properties_from_export,
    parse_array_property, parse_struct_property, parse_map_property,

    # 蓝图
    extract_blueprint_variables, extract_blueprint_metadata,
    parse_component_transform, extract_component_transforms,

    # 流追踪（Phase 35）
    build_execution_flows, build_data_flows, build_connections_map,

    # 格式化（Phase 32）
    format_json_full, format_json_summary,
    format_text_full, format_markdown,
    format_graphs_json, format_blueprint_dict,

    # 常量 & 异常
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError, VersionError,
)
```

完整 API 列表见 `src/uasset_read/__init__.py`（`__all__` 导出 50+ 项）。

## 测试

```bash
# 运行所有测试（397 passed, 71 skipped）
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_graph_parsing.py -v

# 运行单个测试函数
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v

# 运行覆盖率报告
python -m pytest tests/ --cov=uasset_read --cov-report=html
```

测试覆盖：边界验证、蓝图提取、依赖分析、图解析、流追踪、高级属性等（397 个测试用例）。

### 测试结果按阶段

| 阶段 | 测试数 | 状态 | 说明 |
|------|--------|------|------|
| Phase 35a | 397 | ✅ 完成 | UAT 修复，start_event fallback，logging 迁移 |
| Phase 34 | 397 | ✅ 完成 | 等价验证（0 bugs to fix） |
| Phase 33 | 397 | ✅ 完成 | 入口适配 + 旧 uasset_read.py 删除 |
| Phase 33a | 383 | ✅ 完成 | UE5 FText/PropertyTag 容错修复 |
| Phase 28a | 411 | ✅ 完成 | UE5 NodePosX/NodeGuid 提取修复 |

## 架构

采用镜像 UE 的 FArchive 管道模式：

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser (Phase 31)
          BlueprintParser (Phase 30)
          DependencyGraphBuilder (Phase 10)
```

### 模块结构 (`src/uasset_read/`)

| 模块 | 路径 | 阶段 | 说明 |
|------|------|------|------|
| **核心** | | | |
| FArchive | `archive.py` | 28 | 二进制读取器，支持字节交换、mmap、边界验证 |
| 常量 | `constants.py` | 27 | 版本号、阈值、MMAP_THRESHOLD |
| 异常 | `exceptions.py` | 27 | UAssetError、ParseError、VersionError |
| **序列化** | | | |
| 序列化器 | `serializers/` | 28 | PackageFileSummary、ObjectImport/Export、PropertyTag |
| **数据模型** | | | |
| 核心模型 | `models/core.py` | 29 | UEdGraph/Node/Pin、节点类型子类 |
| 蓝图模型 | `models/blueprint.py` | 29 | ParseResult、蓝图元数据、属性数据类 |
| 变换 | `models/transforms.py` | 33 | VectorValue、RotatorValue、ScaleValue |
| **解析器** | | | |
| 属性解析器 | `parsers/` | 30 | 14 种属性类型解析函数 + 分派器 |
| **蓝图** | | | |
| 变量提取 | `blueprint/variable_extractor.py` | 30 | 变量、函数、事件提取 |
| 变换解析 | `blueprint/transform_parser.py` | 33 | 组件 Transform/Rotation/Scale |
| 元数据提取 | `blueprint/metadata_extractor.py` | 30 | 蓝图元数据 |
| **图** | | | |
| 从 Archive 读取 | `graph/from_archive.py` | 31 | UEdGraph/Node/Pin 从 FArchive 解析 |
| 流构建器 | `graph/flow_builder.py` | 32 | 执行流与数据流追踪 |
| 摘要生成 | `graph/summary_builder.py` | 32 | 图摘要生成 |
| **格式化器** | | | |
| JSON 格式化器 | `formatters/json.py` | 32 | 完整/摘要 JSON 输出 |
| 文本格式化器 | `formatters/text.py` | 32 | 可读文本输出 |
| Markdown 格式化器 | `formatters/markdown.py` | 32 | Markdown（含 Mermaid 图） |
| **主管线** | | | |
| 主解析器 | `parse_uasset.py` | 33 | 顶层解析函数 |
| CLI | `cli.py` | 33 | 命令行接口 |

### 已移除（Legacy）

- `uasset_read.py` — 8100+ 行单文件 **Phase 33 后删除** (2026-05-12)

## 技术栈

- **语言**: Python 3.10+（match/case，类型提示）
- **依赖**: 零运行时依赖 — 仅使用标准库（struct、mmap、dataclasses、json、argparse）
- **构建**: setuptools（src layout），pyproject.toml 配置
- **测试**: pytest（可选 dev 依赖）
- **工作流**: GSD（Guided Software Development）

## 版本历史

| 版本 | 日期 | 状态 | 主要特性 |
|------|------|------|----------|
| v1.0 | 2026-05-02 | ✅ 已发布 | 核心解析、基本属性、蓝图元数据 |
| v2.0 | 2026-05-02 | ✅ 已发布 | 蓝图图解析、高级属性、依赖分析 |
| v3.x | 2026-05-04 | ✅ 已发布 | 属性值提取、输出优化、skill封装 |
| v4.0 | 2026-05-05 | ✅ 已发布 | 节点属性深度解析、执行流、连接验证 |
| v5.0 | 2026-05-06 | ✅ 已发布 | 蓝图编译研究、元数据增强 |
| v5.1 | 2026-05-07 | ✅ 已发布 | 项目结构初始化（constants.py, exceptions.py） |
| v6.0 | 2026-05-10 | 🟢 进行中 | 模块化重构（Phase 27-35），397 测试通过 |
| v6.1 | 📋 计划中 | - | Phase 35b 完成、v6.0 发布 |

## 限制

- **仅支持未烘焙/编辑器保存的资产**: Cooked 资产已剥离图数据，使用不同序列化格式
- **不支持字节码反编译**: 编译蓝图使用字节码格式，本项目专注于编辑器保存的资产
- **不输出资源文件**: 纹理、模型等二进制数据过于庞大，仅提取元数据
- **不支持修改**: 仅支持只读解析
- **依赖 UE 源码参考**: .uasset 格式无官方文档，需要 UE 源码作为参考

## 规划

- `.planning/ROADMAP.md` — 版本路线图（50 个阶段）
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/REQUIREMENTS.md` — 需求追溯表
- `.planning/PROJECT.md` — 项目概览
- `.planning/phases/35b-pin-connection-debug/` — Phase 35b 调试文档

---

**最后更新**: 2026-05-13  
**版本**: v6.0（Phase 35b 进行中）  
**测试**: 397 passed, 71 skipped, 0 failed
