# uasset_read

解析 Unreal Engine `.uasset` 文件的 Python 工具，使 AI 代理能够在不依赖 UE 编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

[English](README.md) | [中文版](README.zh-CN.md)

## 状态

| 指标 | 值 |
|------|-----|
| 版本 | **dev-0.3.0** (v14, Phase 76) |
| 测试 | **1646 tests** (1516 passed, 124 skipped) |
| 模块 | `src/uasset_read/` — 39 文件, 150+ 公共 API 导出 |
| 分支 | `dev-0.3.0` |

### 当前里程碑：v14.0 — CUE4Parse 核心对齐

- ✅ Phase 74 — PinReference null/non-null 主路径对齐
- ✅ Phase 75 — EventGraph 节点字段级对齐
- ✅ Phase 77 — Pak 解析 + 压缩 + AES-ECB (62 tests)
- ⬜ Phase 76 — FArchive 补齐 + COR 修复 (下一个)
- ⬜ Phase 78 — UObject 继承树 + PackageLinker 重构
- ⬜ Phase 79 — IoStore (.utoc/.ucas) 解析
- ⬜ Phase 80 — 输出格式 PascalCase 对齐

## 功能

- **PackageFileSummary** — 文件头解析
- **NameMap** — 名称表提取
- **ImportMap** — 依赖映射
- **ExportMap** — 导出映射
- **蓝图图解析** — UEdGraph / Node / Pin 结构
- **高级属性** — Struct / Map / Set / Enum / Text / Delegate
- **蓝图变量提取** — 变量、函数、事件、元数据
- **组件属性解析** — Transform/Rotation/Scale + 标量属性（Float/Int/Bool/Byte/Enum/Struct）
- **依赖分析** — ImportMap + SoftObjectPaths 依赖图构建
- **循环依赖检测** — ImportMap 相互引用检测
- **执行流追踪** — Event → CallFunction 链路追踪
- **数据流追踪** — Pure 函数返回值 → 调用参数，Knot 链穿透
- **EnhancedInput 支持** — ETriggerEvent 类型识别（Started/Ongoing/Completed/Canceled）
- **函数图分析** — FunctionEntry 识别、函数内执行/数据流追踪
- **函数图输出** — 按函数粒度的调用链 + 数据流标注（v9.0）
- **PackageLinker** — 两阶段对象图重建（v7.0）

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
uasset-read path/to/file.uasset                    # JSON 输出到 stdout
uasset-read path/to/file.uasset --output output.json   # 保存到文件

# 输出模式
uasset-read path/to/file.uasset --summary          # 仅摘要（不含属性）
uasset-read path/to/file.uasset --markdown         # Markdown 输出
uasset-read path/to/file.uasset --function-graphs  # 包含 function_graphs 数组（v9.0）

# 严格度
uasset-read path/to/file.uasset --strict           # 遇到警告即停止
uasset-read path/to/file.uasset --tolerant         # 容错模式（默认）

# 调试
uasset-read path/to/file.uasset --debug            # 启用调试日志
```

### Python API

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

    # 流追踪
    build_execution_flows, build_data_flows, build_connections_map,
    build_function_graphs,  # v9.0

    # 格式化
    format_json_full, format_json_summary,
    format_text_full, format_markdown,
    format_graphs_json, format_blueprint_dict,

    # 链接器（v7.0）
    parse_uasset_with_linker, PackageLinker, UObjectInstance,

    # 常量 & 异常
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError, VersionError,
)

# 解析 .uasset 文件
result = parse_uasset('BP_FirstPersonCharacter.uasset')

# 输出 JSON（含 function_graphs）
json_output = format_json_full(result, include_function_graphs=True)
```

完整 API 列表见 `src/uasset_read/__init__.py`（`__all__` 导出 150+ 项）。

## 架构

采用镜像 UE 的 FArchive 管道模式：

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser
          BlueprintParser
          DependencyGraphBuilder
          PackageLinker (v7.0: 两阶段对象图重建)
```

### 模块结构 (`src/uasset_read/`)

| 模块 | 路径 | 说明 |
|------|------|------|
| **核心** | | |
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap、边界验证 |
| 常量 | `constants.py` | 版本号、属性类型阈值、CPF 标志 |
| 异常 | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| 主解析器 | `parse_uasset.py` | 顶层 `parse_uasset()` 和 `parse_uasset_with_linker()` |
| CLI | `cli.py` | argparse 入口 (`uasset-read`) |
| **序列化** | `serializers/` | |
| Package 摘要 | `serializers/package_summary.py` | PackageFileSummary, NameMap |
| 对象资源 | `serializers/object_resources.py` | ImportMap, ExportMap, SoftObjectPaths |
| 属性标签 | `serializers/property_tags.py` | PropertyTag 读取 |
| 图序列化 | `serializers/graph.py` | 从 FArchive 解析 UEdGraph/Node/Pin |
| **数据模型** | `models/` | |
| 核心模型 | `models/core.py` | UEdGraph/Node/Pin, FEdGraphPinType, FMemberReference |
| 节点类型 | `models/node_types.py` | K2NodeCallFunction, K2NodeEvent, K2NodeKnot, K2NodeEnhancedInputAction |
| 蓝图模型 | `models/blueprint.py` | ParseResult, BlueprintMetadata, Variable, Function, Event |
| 属性 | `models/properties.py` | PropertyValue, StructValue, MapValue, EnumValue 等 |
| 变换 | `models/transforms.py` | VectorValue, RotatorValue, ScaleValue |
| 结果 | `models/result.py` | ParseResult, StatusInfo |
| **解析器** | `parsers/` | |
| 属性解析 | `parsers/property_parser.py` | 分派器 + 14 种属性类型解析器 |
| 属性类型 | `parsers/property_types.py` | parse_default_value, format_variable_type |
| **蓝图** | `blueprint/` | |
| 变量提取 | `blueprint/variable_extractor.py` | 变量、函数、事件提取 |
| 变换解析 | `blueprint/transform_parser.py` | 组件 Transform/Rotation/Scale |
| 组件提取 | `blueprint/component_extractor.py` | SCS 组件发现 + 标量属性（Phase 48） |
| 元数据提取 | `blueprint/metadata_extractor.py` | 蓝图元数据 |
| **图** | `graph/` | |
| 流构建器 | `graph/flow_builder.py` | 执行流、数据流追踪、function_graphs |
| 图解析器 | `graph/parser.py` | 蓝图图提取 |
| **链接器** | `link/` | |
| PackageLinker | `link/linker.py` | 类 FLinkerLoad 两阶段加载（v7.0） |
| 对象实例 | `link/object_instance.py` | UObjectInstance — UE 对象表示 |
| 链接器结果 | `link/result.py` | LinkerParseResult |
| **格式化器** | `formatters/` | |
| JSON | `formatters/json_formatter.py` | 完整/摘要 JSON 输出 |
| 文本 | `formatters/text_formatter.py` | 可读文本输出 |
| Markdown | `formatters/markdown_formatter.py` | Markdown（含 Mermaid 流程图） |
| 工具 | `formatters/helpers.py` | 共享格式化实用程序 |

### 已移除（Legacy）

- `uasset_read.py` — 8100+ 行单文件 **Phase 33 后删除** (2026-05-12)

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行覆盖率
python -m pytest tests/ -v --cov=uasset_read
```

**当前**: 554 tests collected.

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
| v6.0 | 2026-05-10 | ✅ 已发布 | 模块化重构，373 测试通过 |
| v7.0 | 2026-05-14 | ✅ 已发布 | UObjectInstance 对象图重建, PackageLinker, UE5.6 适配, 432 tests |
| v8.0 | 2026-05-17 | ✅ 已发布 | BP→C++ JSON 可翻译性 (Pin LinkedTo, 组件属性, 函数调用引脚, EnhancedInput, 二进制清理) |
| v9.0 | 2026-05-17 | ✅ 已发布 | 函数调用链解析 (FunctionEntry 模型, 执行流/数据流追踪, function_graphs 输出) |

## 限制

- **仅支持未烘焙/编辑器保存的资产**: Cooked 资产已剥离图数据，使用不同序列化格式
- **不支持字节码反编译**: 编译蓝图使用字节码格式，本项目专注于编辑器保存的资产
- **不输出资源文件**: 纹理、模型等二进制数据过于庞大，仅提取元数据
- **不支持修改**: 仅支持只读解析
- **依赖 UE 源码参考**: .uasset 格式无官方文档，需要 UE 源码作为参考

## 规划

- `.planning/ROADMAP.md` — 阶段路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/milestones/` — 已归档的里程碑（v7.0, v8.0, v9.0）
- `.planning/MILESTONES.md` — 历史里程碑

---

**最后更新**: 2026-05-18
**版本**: v9.0 已发布 (Phase 52-55 完成)
**测试**: 554 tests collected
**__version__**: 6.0.0 (待更新)
