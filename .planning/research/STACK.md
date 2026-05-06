# 技术栈：模块化重构与C++代码生成准备

**项目:** uasset_read v5.1
**研究日期:** 2026-05-06
**聚焦:** Python单文件模块化重构、零依赖架构、代码组织最佳实践

---

## 推荐技术栈

### 核心框架

| 技术 | 版本 | 用途 | 为什么 |
|------|------|------|--------|
| Python | 3.10+ | 语言运行时 | 项目指定，支持match/case、类型提示增强、dataclasses kw_only |
| Python标准库 | 内置 | 所有功能 | 零依赖原则，无需外部包 |

### 代码组织

| 技术 | 版本 | 用途 | 为什么 |
|------|------|------|--------|
| 包布局 | src layout | 模块结构 | 防止意外导入本地源码，更贴近生产环境 |
| __init__.py | 标准 | API暴露 | 控制公共接口，简化导入 |
| dataclasses | Python 3.7+ | 数据模型 | 零依赖，asdict()自动序列化到JSON |
| typing | 标准 | 类型提示 | 提高可维护性，支持循环依赖类型检查 |
| match/case | Python 3.10+ | 模式匹配 | 比if-elif链更清晰，dataclasses配合良好 |

### 模块拆分策略

| 技术 | 版本 | 用途 | 为什么 |
|------|------|------|--------|
| 按职责拆分 | 标准 | 逻辑分组 | 每个模块单一职责，易于理解 |
| 分层架构 | 标准 | 依赖方向 | FArchive → Deserializer → Models → OutputFormatter |
| 延迟导入 | 标准 | 避免循环依赖 | 在函数内部导入，打破循环依赖 |
| TYPE_CHECKING | 标准 | 类型提示循环依赖 | 类型检查时不实际导入 |

### 避免循环依赖

| 技术 | 用途 | 为什么 |
|------|------|--------|
| 第三模块法 | 提取共享代码 | 两个模块依赖的公共代码放到第三个模块 |
| 延迟导入 | 函数内部导入 | 仅在需要时导入，模块加载时已就绪 |
| TYPE_CHECKING | 类型提示 | 仅类型检查时导入，运行时不导入 |
| 字符串类型注解 | 运行时避免导入 | `"ClassName"` 而非 `ClassName` |

---

## 模块拆分建议

### 推荐结构（src layout）

```
uasset_read/
├── src/
│   └── uasset_read/
│       ├── __init__.py                    # 公共API暴露
│       ├── archive.py                     # FArchive二进制读取器
│       ├── models.py                      # 所有dataclass模型
│       ├── serializers/                   # 序列化器
│       │   ├── __init__.py
│       │   ├── package_summary.py         # PackageFileSummary
│       │   ├── object_resources.py        # ImportMap/ExportMap
│       │   ├── property_tags.py           # PropertyTag解析
│       │   └── property_values.py         # 高级属性值
│       ├── parsers/                       # 解析器
│       │   ├── __init__.py
│       │   ├── base_parser.py             # 基础解析器
│       │   ├── property_parser.py         # 属性解析
│       │   ├── graph_parser.py            # 蓝图图解析
│       │   └── variable_parser.py         # 变量解析
│       ├── blueprint/                     # 蓝图相关
│       │   ├── __init__.py
│       │   ├── graph.py                   # UEdGraph
│       │   ├── node.py                    # UEdGraphNode子类
│       │   ├── pin.py                     # UEdGraphPin
│       │   └── variable.py                # BlueprintVariable
│       ├── output/                        # 输出格式化
│       │   ├── __init__.py
│       │   ├── json_formatter.py          # JSON输出
│       │   └── text_formatter.py          # 文本输出
│       ├── dependencies.py                 # 依赖图构建
│       ├── cli.py                         # 命令行接口
│       └── exceptions.py                  # 异常类
├── tests/                                 # 测试（现有）
├── uasset_read.py                         # 向后兼容入口（导入并运行）
├── pyproject.toml                         # 项目配置
└── README.md
```

### 单职责模块划分

| 模块 | 职责 | 包含类/函数 |
|------|------|-------------|
| `archive.py` | 二进制读取 | FArchive及其方法 |
| `exceptions.py` | 异常处理 | UAssetError, VersionError, ParseError, ErrorContext |
| `models.py` | 顶层模型 | ParseResult, StatusInfo |
| `serializers/package_summary.py` | 文件头序列化 | PackageFileSummary, GenerationInfo, EngineVersion, CustomVersion |
| `serializers/object_resources.py` | 资源序列化 | ObjectImport, ObjectExport, PackageIndex, resolve_*函数 |
| `serializers/property_tags.py` | 属性标签序列化 | PropertyTag |
| `serializers/property_values.py` | 属性值模型 | PropertyValue, AdvancedPropertyValue及其子类（StructValue, MapValue等） |
| `parsers/property_parser.py` | 属性解析 | parse_property, parse_*_property函数 |
| `parsers/graph_parser.py` | 蓝图图解析 | parse_graph, parse_node, parse_pin |
| `parsers/variable_parser.py` | 变量解析 | parse_blueprint_variables |
| `blueprint/graph.py` | 图结构 | UEdGraph |
| `blueprint/node.py` | 节点类型 | UEdGraphNode, K2NodeCallFunction, K2NodeEvent等所有节点子类 |
| `blueprint/pin.py` | Pin结构 | UEdGraphPin, FEdGraphPinType |
| `blueprint/variable.py` | 变量结构 | BlueprintVariable, BlueprintMetadata, FunctionParameter |
| `output/json_formatter.py` | JSON输出 | format_json, to_json_dict |
| `output/text_formatter.py` | 文本输出 | format_text |
| `dependencies.py` | 依赖分析 | DependencyGraphBuilder, build_dependency_graph |
| `cli.py` | CLI接口 | main(), parse_uasset（保持向后兼容） |

---

## 替代方案考虑

### 方案：Flat Layout（扁平结构）

**结构：**
```
uasset_read/
├── uasset_read/
│   ├── __init__.py
│   ├── archive.py
│   ├── models.py
│   └── ...
├── tests/
├── pyproject.toml
└── README.md
```

**优点：**
- 不需要安装即可运行代码
- 开发更简单
- 适合快速原型和脚本

**缺点：**
- 可能意外导入本地源码而非已安装包
- 测试环境与生产环境不一致
- Python Packaging官方不推荐用于生产代码

**为什么不选：**
本项目是长期维护的工具，需要稳定的API和一致的导入行为，src layout更符合生产实践。

---

## Python 3.10+ 特性利用

### 结构化模式匹配

**用途：** 替代复杂的if-elif-else链，特别是属性类型判断

**示例：**
```python
# 替代 if isinstance检查
match property_tag:
    case PropertyTag(type_name="StructProperty"):
        parse_struct_property(...)
    case PropertyTag(type_name="ArrayProperty"):
        parse_array_property(...)
    case PropertyTag(type_name="MapProperty"):
        parse_map_property(...)
    case _:
        raise ParseError(f"Unknown property type: {property_tag.type_name}")
```

**何时使用：**
- 属性类型分发（property_parser.py）
- 节点类型处理（node.py）
- 输出格式选择（json_formatter.py vs text_formatter.py）

### dataclasses kw_only 参数

**用途：** 强制关键字参数，提高API清晰度

**示例：**
```python
from dataclasses import dataclass

@dataclass(kw_only=True)
class UEdGraphNode:
    node_guid: str
    node_pos: tuple[int, int]
    # ... 其他字段

# 强制显式传递参数，避免位置参数混淆
node = UEdGraphNode(
    node_guid="123",
    node_pos=(100, 200),
    # ...
)
```

### TYPE_CHECKING 避免循环依赖

**用途：** 类型提示中引用其他模块的类，但不实际导入

**示例：**
```python
# parsers/graph_parser.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .node import UEdGraphNode
    from .pin import UEdGraphPin

def parse_graph(archive: FArchive) -> "UEdGraph":
    # 实际使用字符串注解或延迟导入
    pass
```

---

## 零依赖保证

### 验证方法

**1. 运行时导入检查**
```bash
# 确保仅使用标准库
python -c "import uasset_read; import sys; [print(f'External: {x}') for x in sys.modules if 'site-packages' in getattr(sys.modules[x], '__file__', '')]"
```

**2. pyproject.toml 配置**
```toml
[project]
name = "uasset_read"
version = "5.1.0"
dependencies = []  # 空列表 = 零依赖

[project.optional-dependencies]
# 可选依赖（如需要的话）
dev = ["pytest>=7.0"]
```

**3. 安装测试**
```bash
# 确保不拉取任何外部包
pip install --dry-run -e .
```

### 标准库依赖清单

| 模块 | 用途 |
|------|------|
| `struct` | 二进制数据打包/解包 |
| `mmap` | 大文件内存映射 |
| `json` | JSON序列化 |
| `argparse` | CLI参数解析 |
| `pathlib` | 路径操作 |
| `typing` | 类型提示 |
| `dataclasses` | 数据模型 |
| `enum` | 枚举类型 |
| `collections` | 数据结构（defaultdict等） |
| `functools` | 函数工具（partial等） |
| `itertools` | 迭代器工具 |
| `re` | 正则表达式 |

---

## 向后兼容策略

### 保留单文件入口

**文件：** `uasset_read.py`（根级别）

**内容：**
```python
"""
向后兼容入口 - 保持现有API不变
导入新模块化结构并暴露公共接口
"""

from src.uasset_read import (
    parse_uasset,
    ParseResult,
    PackageFileSummary,
    FArchive,
    UAssetError,
)

# 保持现有CLI接口
if __name__ == "__main__":
    from src.uasset_read.cli import main
    main()
```

**优点：**
- 现有代码无需修改即可工作
- 渐进式迁移
- 降低重构风险

---

## 避免循环依赖的具体策略

### 策略1：分层架构（推荐）

**依赖方向：**
```
OutputFormatter
    ↓
Models
    ↓
Parsers
    ↓
Serializers
    ↓
FArchive
```

**规则：** 任何层只能依赖其下方的层

### 策略2：延迟导入

**适用场景：** 函数内部需要引用其他模块的类

**示例：**
```python
# output/json_formatter.py
def format_graph_node(node: "UEdGraphNode") -> dict:
    # 仅在函数内部导入，避免循环依赖
    from ..blueprint.node import UEdGraphNode

    # 实际使用
    if isinstance(node, UEdGraphNode):
        return {...}
```

### 策略3：共享接口模块

**创建：** `src/uasset_read/interfaces.py`

**内容：**
```python
"""共享接口和类型定义"""

from typing import Protocol

class IGraphNode(Protocol):
    """所有图节点的公共接口"""
    node_guid: str
    def to_dict(self) -> dict: ...
```

**使用：**
```python
# 两个模块都依赖 interfaces.py，而不是互相依赖
```

---

## 测试适配

### 测试导入路径变化

**之前：**
```python
from uasset_read import ParseResult
```

**之后：**
```python
from src.uasset_read import ParseResult
# 或者通过向后兼容入口
from uasset_read import ParseResult
```

**建议：**
1. 保持 `from uasset_read import *` 有效（通过根级别uasset_read.py）
2. 新测试使用 `from src.uasset_read import *`
3. 渐进式迁移现有测试

---

## 性能考虑

### 模块导入性能

**影响：** 将单文件拆分为多个模块会增加初始导入时间

**缓解措施：**
1. 按需导入（延迟导入）
2. 避免在 `__init__.py` 中导入所有内容
3. 使用 `__all__` 控制公开接口

**示例：**
```python
# src/uasset_read/__init__.py
"""公共API - 仅导入常用接口"""

from .models import ParseResult
from .cli import parse_uasset
from .exceptions import UAssetError

__all__ = ["ParseResult", "parse_uasset", "UAssetError"]
```

---

## 安装与配置

### pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "uasset_read"
version = "5.1.0"
description = "Unreal Engine .uasset file parser for AI agents"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []  # 零依赖

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

[project.scripts]
uasset-read = "src.uasset_read.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

### 安装命令

```bash
# 开发模式安装（可编辑）
pip install -e .

# 验证零依赖
pip show uasset_read  # 应该显示 "Requires: (empty)"
```

---

## 来源与置信度

| 信息 | 来源 | 置信度 |
|------|------|--------|
| Python 3.10 结构化模式匹配 | [PEP 634, PEP 636](https://peps.python.org/pep-0634/), [Ben Hoyt文章](https://benhoyt.com/writings/python-pattern-matching/) | HIGH |
| dataclasses kw_only | [Python 3.10 What's New](https://docs.python.org/3/whatsnew/3.10.html) | HIGH |
| src layout vs flat layout | [Python Packaging User Guide](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/), [RealPython](https://realpython.com/ref/best-practices/project-layout/) | HIGH |
| 避免循环依赖 | [Stack Overflow](https://stackoverflow.com/questions/7336802/how-to-avoid-circular-imports-in-python), [Medium文章](https://medium.com/@hamana.hadrien/so-you-got-a-circular-import-in-python-e9142fe10591) | HIGH |
| 零依赖架构 | [Zero-Dependency Python](https://medium.com/@CodeWithHannan/zero-dependency-python-building-tools-that-avoid-external-libraries-f2a8f5092b57), [Toptal文章](https://www.toptal.com/developers/software/creating-modular-code-with-no-dependencies) | HIGH |
| __init__.py API暴露 | [Real Python](https://realpython.com/python-init-py/), [Stack Overflow](https://stackoverflow.com/questions/79187368/how-to-use-init-py-to-create-a-clean-api) | HIGH |
| 大文件拆分最佳实践 | [Stack Overflow](https://stackoverflow.com/questions/32067936/how-to-split-a-very-large-python-file) | MEDIUM（经验性建议） |
| Python架构模式 | [Architecture Patterns with Python](https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/), [Medium文章](https://medium.com/codrift/15-python-architecture-patterns-that-scale-beautifully-b68ff12ce7e6) | MEDIUM |

---

## 总结

**核心原则：**
1. **零依赖** - 仅使用Python标准库
2. **分层架构** - 清晰的依赖方向，避免循环依赖
3. **单一职责** - 每个模块一个明确职责
4. **向后兼容** - 保留单文件入口，渐进式迁移
5. **Python 3.10+** - 利用match/case、dataclasses增强等特性

**推荐方案：**
- 使用 `src` layout 结构
- 按职责拆分为7个核心模块（archive, models, serializers, parsers, blueprint, output, cli）
- 通过 `__init__.py` 控制公共API
- 保留根级别 `uasset_read.py` 向后兼容入口
- 使用分层架构和延迟导入避免循环依赖

**零依赖验证：**
- `pyproject.toml` 中 `dependencies = []`
- 所有导入仅来自 `sys.builtin_module_names` 或标准库
- 运行时导入检查无 `site-packages` 模块