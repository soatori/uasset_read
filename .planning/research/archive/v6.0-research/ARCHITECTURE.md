# Architecture Research

**Domain:** Python模块化重构 - .uasset文件解析器
**Researched:** 2026-05-06
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   argparser │  │  main()     │  │   output    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                 │                 │              │
└─────────┴─────────────────┴─────────────────┴──────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Parser Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Property   │  │   Blueprint │  │    Graph    │        │
│  │  Parser     │  │   Parser    │  │   Parser    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                 │                 │              │
└─────────┴─────────────────┴─────────────────┴──────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Model Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Models    │  │   Types     │  │  Constants  │        │
│  │  (dataclass)│  │  (dataclass)│  │   (const)   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                 │                 │              │
└─────────┴─────────────────┴─────────────────┴──────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   I/O Layer                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   FArchive  │  │  Formatter  │  │  Validator  │        │
│  │  (binary)   │  │  (output)   │  │   (checks)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **FArchive** | 二进制文件读取、字节序处理、mmap支持 | 独立类，提供read_i32/seek/tell等方法 |
| **Models** | 数据模型定义，所有dataclass | 按功能分组：core/models/blueprint/graph |
| **PropertyParser** | 属性值解析（基本+高级类型） | 模块化解析器，可扩展类型系统 |
| **BlueprintParser** | 蓝图元数据、变量提取 | 独立模块，处理蓝图特定逻辑 |
| **GraphParser** | 蓝图图结构解析（Graph→Node→Pin） | 分层解析器，支持节点类型扩展 |
| **Formatter** | 输出格式化（JSON/Text/Markdown） | 策略模式，可添加新格式 |
| **CLI** | 命令行接口、参数解析、输出路由 | 独立模块，可替换为MCP/Skill |
| **Validator** | 边界验证、错误检测 | 防御性编程，安全常量 |

## Recommended Project Structure

```
uasset_read/
├── pyproject.toml              # 项目配置
├── README.md                   # 项目说明
├── setup.py                    # 安装脚本（向后兼容）
├── src/
│   └── uasset_read/
│       ├── __init__.py         # 公共API导出
│       ├── constants.py        # 常量定义（版本号、阈值）
│       ├── exceptions.py       # 异常类定义
│       ├── archive.py          # FArchive二进制读取器
│       ├── models/
│       │   ├── __init__.py     # 模型导出
│       │   ├── core.py         # 核心模型（PackageFileSummary等）
│       │   ├── properties.py   # 属性模型（PropertyTag等）
│       │   ├── blueprint.py    # 蓝图模型（BlueprintMetadata等）
│       │   ├── graph.py        # 图模型（UEdGraph等）
│       │   └── advanced.py     # 高级属性模型（StructValue等）
│       ├── parsers/
│       │   ├── __init__.py     # 解析器导出
│       │   ├── core.py         # 核心解析（表解析）
│       │   ├── property.py     # 属性解析
│       │   ├── blueprint.py    # 蓝图解析
│       │   └── graph.py        # 图解析
│       ├── formatters/
│       │   ├── __init__.py     # 格式化器导出
│       │   ├── json.py         # JSON格式化
│       │   ├── text.py         # 文本格式化
│       │   └── markdown.py     # Markdown格式化
│       ├── cli/
│       │   ├── __init__.py     # CLI导出
│       │   └── main.py         # CLI入口和参数解析
│       └── utils/
│           ├── __init__.py     # 工具函数导出
│           ├── validation.py   # 边界验证
│           └── helpers.py      # 辅助函数
├── tests/                      # 测试文件（保持不变）
├── uasset_read.py              # 向后兼容层（重定向到src）
└── docs/                       # 文档（可选）
```

### Structure Rationale

- **src/uasset_read/**: 采用官方推荐的src布局，避免导入问题
- **models/**: 按功能分组模型，每个文件约300-500行，易于维护
- **parsers/**: 解析逻辑与模型分离，便于测试和扩展
- **formatters/**: 输出格式独立，可添加新格式而不影响核心逻辑
- **cli/**: CLI作为独立模块，可替换为MCP/Skill封装
- **utils/**: 通用工具函数，避免代码重复
- **uasset_read.py**: 保留作为向后兼容层，重定向到新模块

## Architectural Patterns

### Pattern 1: 分层架构（Layered Architecture）

**What:** 将代码按职责分层（I/O → Parser → Model → CLI），每层只依赖下层。

**When to use:**
- 项目需要清晰的职责分离
- 测试需要模拟特定层
- 未来可能替换某一层的实现

**Trade-offs:**
- 优点：模块化强，易于测试和维护
- 缺点：初期设计成本高，可能增加间接调用

**Example:**
```python
# Layer 1: I/O Layer (archive.py)
class FArchive:
    def read_i32(self) -> int: ...
    def seek(self, offset: int): ...

# Layer 2: Parser Layer (parsers/core.py)
def read_package_summary(archive: FArchive) -> PackageFileSummary:
    summary = PackageFileSummary()
    summary.tag = archive.read_u32()
    ...

# Layer 3: Model Layer (models/core.py)
@dataclass
class PackageFileSummary:
    tag: int
    version: int
    ...

# Layer 4: CLI Layer (cli/main.py)
def parse_uasset(path: str) -> ParseResult:
    archive = FArchive(path)
    result = ParseResult()
    result.summary = read_package_summary(archive)
    ...
```

### Pattern 2: 策略模式（Strategy Pattern）

**What:** 将可变的算法（输出格式化）封装成独立策略，运行时选择。

**When to use:**
- 同一功能有多种实现方式
- 需要在运行时切换算法
- 避免大量if-else/switch

**Trade-offs:**
- 优点：易于扩展新格式，符合开闭原则
- 缺点：增加类的数量，需要工厂模式管理

**Example:**
```python
# formatters/base.py
from abc import ABC, abstractmethod

class Formatter(ABC):
    @abstractmethod
    def format(self, result: ParseResult) -> Any: ...

# formatters/json.py
class JSONFormatter(Formatter):
    def format(self, result: ParseResult) -> str:
        return json.dumps(result.to_dict(), indent=2)

# formatters/text.py
class TextFormatter(Formatter):
    def format(self, result: ParseResult) -> str:
        return str(result)

# cli/main.py
formatters = {
    'json': JSONFormatter(),
    'text': TextFormatter(),
    'markdown': MarkdownFormatter(),
}
formatter = formatters[args.format]
output_str = formatter.format(result)
```

### Pattern 3: 工厂模式（Factory Pattern）

**What:** 将对象创建逻辑封装在工厂中，客户端通过工厂获取对象。

**When to use:**
- 对象创建逻辑复杂
- 需要根据条件创建不同类型
- 想隐藏具体实现

**Trade-offs:**
- 优点：解耦创建和使用，便于管理
- 缺点：增加类的数量，可能过度设计

**Example:**
```python
# parsers/property.py
def create_property_parser(prop_type: str, archive: FArchive) -> 'PropertyParser':
    parsers = {
        'BoolProperty': BoolPropertyParser(),
        'IntProperty': IntPropertyParser(),
        'StructProperty': StructPropertyParser(),
        'MapProperty': MapPropertyParser(),
    }
    return parsers.get(prop_type, DefaultPropertyParser())

# Usage
parser = create_property_parser(prop_tag.type_name, archive)
value = parser.parse(archive, prop_tag)
```

## Data Flow

### Request Flow

```
CLI: parse_uasset('file.uasset')
    ↓
FArchive: 打开文件，mmap/常规读取
    ↓
read_package_summary(): 解析文件头
    ↓
read_name_table(): 解析名称表
    ↓
read_import_map(): 解析导入表
    ↓
read_export_map(): 解析导出表
    ↓
parse_properties_from_export(): 解析每个导出的属性
    ↓
extract_blueprint_metadata(): 提取蓝图元数据
    ↓
extract_blueprint_graphs(): 提取蓝图图结构
    ↓
Formatter: format_json_full/format_text_full
    ↓
Output: 写入stdout或文件
```

### Import/Export Flow

```
# __init__.py - Public API
from .archive import FArchive
from .models.core import PackageFileSummary, ParseResult
from .parsers.core import parse_uasset
from .formatters.json import format_json_full

__all__ = [
    'FArchive',
    'PackageFileSummary',
    'ParseResult',
    'parse_uasset',
    'format_json_full',
    ...
]

# Backward compatibility (uasset_read.py)
from src.uasset_read import *

# Tests can import directly
from src.uasset_read.archive import FArchive
from src.uasset_read.models.core import PackageFileSummary
from src.uasset_read.parsers.property import parse_property_value
```

### Key Data Flows

1. **解析流程：** FArchive → Parser → Models → ParseResult → Formatter → Output
2. **依赖解析：** ImportMap + ExportMap → resolve_package_index() → ObjectReference
3. **图解析流程：** ExportMap → ClassIndex检测 → read_ue_graph() → Nodes → Pins → Connections
4. **属性解析流程：** PropertyTag → 根据类型选择Parser → PropertyValue → 高级属性处理

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 当前（单文件） | 模块化拆分，保持功能不变 |
| 10K-50K lines | 按功能模块拆分，每个模块<1000行 |
| 50K-100K lines | 引入插件系统，支持第三方节点类型处理器 |
| 100K+ lines | 考虑微服务架构，将解析和输出分离 |

### Scaling Priorities

1. **First bottleneck:** 单文件7805行，难以维护 → 模块化拆分为10-15个文件
2. **Second bottleneck:** 属性解析器硬编码 → 使用工厂模式支持动态注册新类型
3. **Third bottleneck:** 输出格式耦合 → 策略模式，便于添加新格式

## Anti-Patterns

### Anti-Pattern 1: 过度拆分（Over-Segmentation）

**What people do:** 将每个类、函数都放到单独文件中，导致数百个小文件

**Why it's wrong:**
- 导入开销增加
- 难以理解代码关系
- 导航困难

**Do this instead:**
- 按功能分组（如models/blueprint.py包含所有蓝图相关模型）
- 每个文件300-500行
- 相关类放在同一文件

### Anti-Pattern 2: 循环导入（Circular Imports）

**What people do:** models导入parsers，parsers导入models

**Why it's wrong:**
- Python无法处理循环导入
- 导致模块加载失败

**Do this instead:**
- 使用类型注解字符串（from __future__ import annotations）
- 延迟导入（在函数内部导入）
- 重新设计依赖关系，models不应该导入parsers

### Anti-Pattern 3: 忽略向后兼容性（Breaking Changes Without Migration Path）

**What people do:** 直接删除uasset_read.py，强制所有用户更新代码

**Why it's wrong:**
- 破坏现有用户的使用方式
- 测试需要大量修改
- 社区接受度低

**Do this instead:**
- 保留uasset_read.py作为兼容层
- 新代码使用from src.uasset_read import
- 提供清晰的迁移指南
- 逐步废弃旧API（DeprecationWarning）

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| UE源码（只读参考） | 文档参考，不直接集成 | 位于E:\Develop\lib\UnrealEngine |
| 测试框架 | pytest | tests/目录保持不变 |
| Claude Code Skill | MCP Server封装 | 未来Phase，独立的mcp/模块 |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| FArchive ↔ Parsers | 方法调用 | FArchive提供read_*方法 |
| Parsers ↔ Models | 返回dataclass | Parsers创建和填充Models |
| Models ↔ Formatters | to_dict()方法 | 使用dataclasses.asdict() |
| CLI ↔ Parsers | 函数调用 | CLI调用parse_uasset() |

## Migration Strategy

### Phase 1: 准备工作（不破坏现有代码）

1. 创建src/uasset_read/目录结构
2. 创建__init__.py占位符
3. 设置pyproject.toml（可选，为未来打包做准备）

### Phase 2: 拆分I/O和Models

1. 创建archive.py（FArchive类）
2. 创建constants.py（常量定义）
3. 创建exceptions.py（异常类）
4. 创建models/core.py（PackageFileSummary, ObjectImport, ObjectExport）

### Phase 3: 拆分Models和Parsers

1. 创建models/properties.py（PropertyTag, PropertyValue）
2. 创建models/blueprint.py（BlueprintMetadata等）
3. 创建models/graph.py（UEdGraph等）
4. 创建parsers/core.py（表解析函数）
5. 创建parsers/property.py（属性解析）

### Phase 4: 拆分Formatters和CLI

1. 创建formatters/json.py（JSON格式化）
2. 创建formatters/text.py（文本格式化）
3. 创建formatters/markdown.py（Markdown格式化）
4. 创建cli/main.py（CLI入口）

### Phase 5: 向后兼容层

1. 修改uasset_read.py，重定向到新模块
2. 运行所有测试，确保通过
3. 更新__all__导出列表

### Phase 6: 文档和清理

1. 更新README.md
2. 添加迁移指南
3. 删除冗余代码
4. 运行完整测试套件

### 建议的构建顺序

**优先级1（核心）：**
1. constants.py
2. exceptions.py
3. archive.py
4. models/core.py
5. parsers/core.py

**优先级2（属性）：**
6. models/properties.py
7. parsers/property.py

**优先级3（蓝图和图）：**
8. models/blueprint.py
9. models/graph.py
10. parsers/blueprint.py
11. parsers/graph.py

**优先级4（输出和CLI）：**
12. formatters/*.py
13. cli/main.py

**优先级5（兼容性）：**
14. __init__.py（公共API）
15. uasset_read.py（向后兼容层）

### 向后兼容性保证

```python
# uasset_read.py - 向后兼容层
# 重定向所有导出到新模块

from src.uasset_read.archive import FArchive
from src.uasset_read.constants import *
from src.uasset_read.exceptions import *
from src.uasset_read.models.core import *
from src.uasset_read.models.properties import *
from src.uasset_read.models.blueprint import *
from src.uasset_read.models.graph import *
from src.uasset_read.parsers.core import *
from src.uasset_read.parsers.property import *
from src.uasset_read.parsers.blueprint import *
from src.uasset_read.parsers.graph import *
from src.uasset_read.formatters.json import *
from src.uasset_read.formatters.text import *
from src.uasset_read.formatters.markdown import *
from src.uasset_read.cli.main import *

# 保持__all__不变，测试无需修改
__all__ = [
    # ... 所有原有的导出
]

# 主函数保持兼容
if __name__ == '__main__':
    from src.uasset_read.cli.main import main
    main()
```

## Sources

- [Python Packaging User Guide - src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) - 官方推荐的src布局
- [Real Python - Python Project Layout](https://realpython.com/ref/best-practices/project-layout/) - 项目结构最佳实践
- [Medium - Python Project Structure: Why the 'src' Layout Beats Flat Folders](https://medium.com/@adityaghadge99/python-project-structure-why-the-src-layout-beats-flat-folders-and-how-to-use-my-free-template-808844d16f35) - src布局优势分析
- [Reddit - How to best structure a large project into multiple installable packages](https://discuss.python.org/t/how-to-best-structure-a-large-project-into-multiple-installable-packages/5404) - 大型项目结构建议
- [HackerNoon - Why Refactoring? How to Restructure Python Package?](https://hackernoon.com/why-refactoring-how-to-restructure-python-package-51b89aa91987) - 重构策略
- [Stack Overflow - Best practices for writing argparse parsers](https://stackoverflow.com/questions/46719811/best-practices-for-writing-argparse-parsers) - CLI模块分离最佳实践
- [Devin J. Cornell - Patterns and Antipatterns for Dataclasses](https://devinjcornell.com/post/dsp0_patterns_for_dataclasses.html) - dataclass设计模式
- [Python official documentation - argparse](https://docs.python.org/3/library/argparse.html) - argparse官方文档

---
*Architecture research for: Python模块化重构 - .uasset文件解析器*
*Researched: 2026-05-06*