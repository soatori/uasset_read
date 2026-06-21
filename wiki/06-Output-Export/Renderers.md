---
title: 渲染器系统
section: renderers
---

# 渲染器系统

渲染器（Renderers）是 0.4.1 引入的新输出系统，替代了原有的 Exporter 架构。渲染器接收 `PackageIR`（中间表示），不直接访问 `ParseResult`，实现了解析与输出的完全解耦。

## 架构概览

```
ParseResult → build_package_ir() → PackageIR → Renderer → Output String
                                          ↓
                                  RENDERER_REGISTRY
                                  ├── json
                                  └── markdown
```

## 核心类

<!-- data-api="IRenderer" -->
```python
class IRenderer(ABC):
    @abstractmethod
    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        """将 PackageIR 渲染为字符串。"""
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """渲染器处理的格式名。"""
        ...
```

<!-- data-api="RenderOptions" -->
```python
@dataclass
class RenderOptions:
    verbose: bool = False
    include_schema: bool = False
    include_function_graphs: bool = False
    linker_result: LinkerParseResult | None = None
```

<!-- data-api="RENDERER_REGISTRY" -->
```python
RENDERER_REGISTRY: dict[str, type[IRenderer]] = {}

def register_renderer(format_name: str, renderer_class: type[IRenderer]) -> None:
    """注册渲染器。"""

def get_renderer(format_name: str) -> IRenderer:
    """获取渲染器实例。"""

def list_formats() -> list[str]:
    """返回所有已注册的格式名。"""
```

## 已注册的渲染器

| 格式名 | 渲染器类 | 文件 | 说明 |
|--------|----------|------|------|
| `json` | `JSONRenderer` | `json_renderer.py` | 结构化 JSON 输出（C++ 翻译参考） |
| `markdown` | `MarkdownRenderer` | `markdown_renderer.py` | Markdown + Mermaid 文档 |

## 使用方式

### 通过 Core API（推荐）

```python
from uasset_read import parse_single, list_formats

# 直接渲染为 JSON
output = parse_single("MyBlueprint.uasset", format="json")

# 查看所有可用格式
print(list_formats())
```

### 直接使用渲染器

```python
from uasset_read.renderers import get_renderer, list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.ir_builder import build_package_ir
from uasset_read import parse_uasset

# 解析
result = parse_uasset("MyBlueprint.uasset")

# 构建 IR
ir = build_package_ir(result)

# 获取渲染器并渲染
renderer = get_renderer("markdown")
options = RenderOptions(verbose=True, include_schema=False)
output = renderer.render(ir, options)
```

## 自动注册机制

渲染器在模块导入时自动注册：

```python
# src/uasset_read/renderers/__init__.py
from . import json_renderer        # 自动注册 "json"
from . import markdown_renderer    # 自动注册 "markdown"
```

## 与旧 Exporter 的区别

| 特性 | 旧 Exporter | 新 Renderer |
|------|-------------|-------------|
| 数据源 | ParseResult | PackageIR |
| 配置 | ExportOptions dataclass | RenderOptions dataclass |
| 返回类型 | str | str |
| 注册表 | ExporterRegistry | RENDERER_REGISTRY |
| 验证支持 | validate() 方法 | 无（验证在 IR 构建层） |
| N2C 支持 | N2CExporter + 验证 | 已移除 |
| 批量导出 | BatchExporter | parse_batch() in core.py |

## 文件位置

| 文件 | 路径 |
|------|------|
| 模块根目录 | `src/uasset_read/renderers/` |
| 基类 | `renderers/base.py` |
| JSON 渲染器 | `renderers/json_renderer.py` |
| Markdown 渲染器 | `renderers/markdown_renderer.py` |

**相关章节**: [[IR 中间表示]] · [[CLI 接口]] · [[格式化器]]
