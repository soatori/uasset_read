# uasset_read

解析 Unreal Engine `.uasset` 文件的 Python 工具，使 AI 代理能够在不依赖 UE 编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

[English](README.md) | [中文版](README.zh-CN.md)

## 状态

| 指标 | 值 |
|------|-----|
| 版本 | v6.0（模块化重构中） |
| 测试 | 411 passed, 47 skipped, 0 failed |
| 新模块 | `src/uasset_read/` — 19 个文件，50+ 公共 API 导出 |
| 旧版入口 | `uasset_read.py` — 8100+ 行单文件，Phase 33 后删除 |

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

## 安装

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
pip install -e ".[dev]"
```

零运行时依赖，仅需 Python 3.10+。

## 使用

### CLI（旧版入口，Phase 33 前）

```bash
python uasset_read.py path/to/file.uasset
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
```

### 新版模块化 API（v6.0）

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
    parse_component_transform,

    # 常量 & 异常
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError,
)
```

完整 API 列表见 `src/uasset_read/__init__.py`（`__all__` 导出 50+ 项）。

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_graph_parsing.py -v

# 运行单个测试函数
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v
```

测试覆盖：边界验证、蓝图提取、依赖分析、图解析、高级属性等（411 个测试用例）。

## 架构

采用镜像 UE 的 FArchive 管道模式：

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓ 扩展组件
          GraphParser (Phase 7/31)
          AdvancedPropParser (Phase 9/30)
          DependencyGraphBuilder (Phase 10)
```

### 新版模块结构 (`src/uasset_read/`)

| 模块 | 路径 | 说明 |
|------|------|------|
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap、边界验证 |
| 常量 | `constants.py` | 版本号、属性类型阈值、MMAP_THRESHOLD |
| 异常 | `exceptions.py` | UAssetError、VersionError、ParseError、ErrorContext |
| 序列化 | `serializers/` | PackageFileSummary、ObjectImport/Export、PackageIndex、PropertyTag |
| 数据模型 | `models/` | UEdGraph/Node/Pin、节点类型子类、ParseResult、蓝图元数据、属性数据类 |
| 解析器 | `parsers/` | 14 种属性类型解析函数 + 分派器 |
| 蓝图 | `blueprint/` | 蓝图变量提取、组件变换解析、元数据提取 |

### 旧版单文件 (`uasset_read.py`)

完整解析管线，包含所有组件。Phase 33（入口适配+等价验证）完成后将删除。

## 技术栈

- **语言**: Python 3.10+（match/case，类型提示）
- **依赖**: 零运行时依赖 — 仅使用标准库（struct、mmap、dataclasses、json、argparse）
- **构建**: setuptools（src layout），pyproject.toml 配置
- **测试**: pytest（可选 dev 依赖）

## 限制

专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。烘焙后的资产仅包含烘焙数据，无蓝图源码。

## 规划

- `.planning/ROADMAP.md` — 版本路线图（50 个阶段）
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/REQUIREMENTS.md` — 需求追溯表
- `.planning/PROJECT.md` — 项目概览
