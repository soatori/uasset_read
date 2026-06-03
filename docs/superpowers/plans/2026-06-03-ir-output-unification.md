# IR 输出格式统一化 + CLI 核心分离 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 IR（中间表示）+ 多渲染器架构取代旧 exporter/formatter 系统，实现单一数据源、多格式渲染，同时 CLI 核心逻辑与入口分离。

**Architecture:** 一次性替换策略。删除 `exporter/`、`n2c/`、`agent/` 全部模块。新建 `models/ir.py`（IR 数据结构）、`ir_builder.py`（构建层）、`renderers/`（6 个渲染器）、`core.py`（纯解析 API）。CLI 瘦身委托 `core.py`。

**Tech Stack:** Python 3.10+, pytest, dataclasses

**全局约束:**
- 测试命令: `python -m pytest tests/ -v --tb=short`
- 临时文件放在 `temp/` 目录
- 每个 Task 提交一次

---

## 文件结构

### 新建文件

| 文件 | 职责 |
|------|------|
| `src/uasset_read/models/ir.py` | IR 数据结构（7 个 dataclass） |
| `src/uasset_read/ir_builder.py` | `build_package_ir()` 构建器 |
| `src/uasset_read/renderers/__init__.py` | 渲染器注册表 + `get_renderer()` |
| `src/uasset_read/renderers/base.py` | `IRenderer` ABC + `RenderOptions` |
| `src/uasset_read/renderers/json_renderer.py` | JSON 渲染器 |
| `src/uasset_read/renderers/text_renderer.py` | YAML 风格文本渲染器 |
| `src/uasset_read/renderers/markdown_renderer.py` | Markdown + Mermaid 渲染器 |
| `src/uasset_read/renderers/blueprint_text_renderer.py` | 蓝图翻译参考文本 |
| `src/uasset_read/renderers/blueprint_ue_renderer.py` | UE 格式文本 |
| `src/uasset_read/renderers/cpp_skeleton_renderer.py` | C++ 头文件骨架 |
| `src/uasset_read/core.py` | 核心解析 API（`parse_single`, `parse_batch`, `list_formats`） |
| `diag.py` | 快捷诊断入口 |
| `src/uasset_read/simple.py` | 快速诊断脚本 |
| `tests/test_ir_structures.py` | IR 结构测试 |
| `tests/test_ir_builder.py` | IR 构建器测试 |
| `tests/test_renderers.py` | 渲染器测试 |
| `tests/test_core_api.py` | core.py API 测试 |

### 修改文件

| 文件 | 修改 |
|------|------|
| `src/uasset_read/__init__.py` | 更新 `__all__`，删除旧导出 |
| `src/uasset_read/cli.py` | 重写：删除 `_handle_graph_mode`/`_build_export_options`，委托 `core.parse_single()` |
| `tests/test_api_cleanup.py` | 删除 `_handle_graph_mode` 相关测试，删除 exporter 引用 |

### 删除目录

| 目录 | 文件数 | 理由 |
|------|--------|------|
| `src/uasset_read/exporter/` | 12 | 被 renderers/ 替代 |
| `src/uasset_read/n2c/` | 15+ | 专用工具，非核心需求 |
| `src/uasset_read/agent/` | 2 | AI 翻译管线，高级功能 |

---

## Task 1: 定义 IR 数据结构

**Files:**
- Create: `src/uasset_read/models/ir.py`
- Test: `tests/test_ir_structures.py`

- [ ] **Step 1: 编写 IR 结构测试**

```python
# tests/test_ir_structures.py
"""IR 数据结构单元测试。"""
import pytest
from dataclasses import fields
from uasset_read.models.ir import (
    PackageHeaderIR,
    PinIR,
    NodeIR,
    GraphIR,
    PropertyIR,
    ExportIR,
    LinkerSummaryIR,
    PackageIR,
)


class TestPinIR:
    def test_pin_ir_minimal(self):
        pin = PinIR(pin_name="Exec", pin_type="exec", pin_type_value=None,
                    linked_to=[], direction="EGPD_Output", default_value=None)
        assert pin.pin_name == "Exec"
        assert pin.linked_to == []

    def test_pin_ir_full(self):
        pin = PinIR(pin_name="Target", pin_type="Object", pin_type_value="Actor",
                    linked_to=["abc123..."], direction="EGPD_Input",
                    default_value="SomeValue")
        assert len(pin.linked_to) == 1
        assert pin.default_value == "SomeValue"


class TestNodeIR:
    def test_node_ir_minimal(self):
        node = NodeIR(node_guid="0" * 32, node_class="K2Node_Event",
                      node_comment=None, pins=[], execution_flow=[])
        assert node.node_guid == "0" * 32
        assert node.pins == []

    def test_node_ir_with_comment(self):
        node = NodeIR(node_guid="a" * 32, node_class="K2Node_Comment",
                      node_comment="My Note", pins=[], execution_flow=[])
        assert node.node_comment == "My Note"


class TestGraphIR:
    def test_graph_ir_minimal(self):
        g = GraphIR(graph_guid="0" * 32, graph_name="EventGraph",
                    graph_class="EdGraph", nodes=[], execution_chains=[])
        assert g.graph_name == "EventGraph"


class TestPropertyIR:
    def test_property_ir_minimal(self):
        p = PropertyIR(name="Health", type="FloatProperty", value=100.0,
                       array_index=-1, guid=None)
        assert p.name == "Health"
        assert p.value == 100.0


class TestExportIR:
    def test_export_ir_minimal(self):
        e = ExportIR(index=0, object_name="Default__BP_Test_C",
                     object_class="BlueprintGeneratedClass", serial_size=100,
                     outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None)
        assert e.index == 0
        assert e.graphs == []
        assert e.bulk_data is None


class TestPackageIR:
    def test_package_ir_minimal(self):
        header = PackageHeaderIR(
            package_name="/Game/Test/BP_Test", package_class="BP_Test_C",
            package_flags=0, total_export_count=1, total_import_count=1,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["BP_Test"], imports=[],
                       exports=[], linker=None)
        assert ir.header.package_name == "/Game/Test/BP_Test"
        assert len(ir.exports) == 0


class TestLinkerSummaryIR:
    def test_linker_summary_ir(self):
        ls = LinkerSummaryIR(has_linker=True, import_paths=["/Engine/Core"],
                             export_paths=["/Game/Test"])
        assert ls.has_linker is True
        assert len(ls.import_paths) == 1
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_ir_structures.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 IR 数据结构**

```python
# src/uasset_read/models/ir.py
"""IR（中间表示）数据结构 — PackageIR 层级模型。

IR 是解析结果的统一数据源，渲染器只接收 PackageIR，不访问 ParseResult。
所有 GUID（Node/Pin）统一为 32 位小写 hex。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PackageHeaderIR:
    """包头部精简摘要。"""
    package_name: str            # 包完整路径（/Game/.../BP_FirstPersonCharacter）
    package_class: str           # 包内主类名
    package_flags: int           # 精简后的 flag 值
    total_export_count: int
    total_import_count: int
    ue_version: str             # "5.x" 或 "4.x"


@dataclass
class PinIR:
    """单个 Pin 的 IR 表示。"""
    pin_name: str
    pin_type: str               # "EdGraphPin", "EdGraphPinType"
    pin_type_value: str | None  # 类型具体值（int, float, Object 等）
    linked_to: list[str]        # 目标 PinID 列表，32位小写 hex
    direction: str              # "EGPD_Input" | "EGPD_Output"
    default_value: str | None   # 默认值字符串化


@dataclass
class NodeIR:
    """单个节点的 IR 表示。"""
    node_guid: str              # 32位小写 hex
    node_class: str             # "K2Node_Event" 等
    node_comment: str | None    # 蓝图原注释
    pins: list[PinIR]
    execution_flow: list[dict]  # 序列化顺序 + Pin 连接


@dataclass
class GraphIR:
    """单个图的 IR 表示。"""
    graph_guid: str             # 32位小写 hex
    graph_name: str
    graph_class: str
    nodes: list[NodeIR]
    execution_chains: list[list[str]]  # 节点 GUID 链


@dataclass
class PropertyIR:
    """单个属性的 IR 表示。"""
    name: str
    type: str
    value: Any                  # 原始值，渲染器负责格式化
    array_index: int            # 数组索引（-1 表示非数组元素）
    guid: str | None            # PropertyTag GUID，可选


@dataclass
class ExportIR:
    """单个导出对象的 IR 表示。"""
    index: int                  # 导出序号（0-based）
    object_name: str
    object_class: str
    serial_size: int            # 序列化数据大小
    outer_index_resolved: str | None  # 已解析的 outer 对象名
    super_index_resolved: str | None  # 已解析的父类路径（null 则无）
    parent_class: str | None    # 蓝图主类路径
    properties: list[PropertyIR]
    graphs: list[GraphIR]       # 仅蓝图类非空
    bulk_data: dict | None      # L3+ 资产的 BulkData 头部信息


@dataclass
class LinkerSummaryIR:
    """包链接摘要。"""
    has_linker: bool
    import_paths: list[str]     # 已解析的 import 对象路径列表
    export_paths: list[str]     # 已解析的 export 对象路径列表


@dataclass
class PackageIR:
    """顶层 IR 结构。"""
    header: PackageHeaderIR
    name_map: list[str]
    imports: list[dict]         # 轻量导入摘要
    exports: list[ExportIR]
    linker: LinkerSummaryIR | None
```

- [ ] **Step 4: 更新 models/__init__.py 导出新类型**

在 `src/uasset_read/models/__init__.py` 中添加：

```python
from .ir import (
    PackageHeaderIR,
    PinIR,
    NodeIR,
    GraphIR,
    PropertyIR,
    ExportIR,
    LinkerSummaryIR,
    PackageIR,
)

__all__ = [
    # ... existing exports ...
    "PackageHeaderIR",
    "PinIR",
    "NodeIR",
    "GraphIR",
    "PropertyIR",
    "ExportIR",
    "LinkerSummaryIR",
    "PackageIR",
]
```

- [ ] **Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_ir_structures.py -v`
Expected: ALL PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/models/ir.py src/uasset_read/models/__init__.py tests/test_ir_structures.py
git commit -m "feat: 定义 IR 数据结构（PackageIR, ExportIR, GraphIR, NodeIR, PinIR）
- 7 个 dataclass，覆盖完整 IR 层级
- GUID 统一为 32 位小写 hex
- 测试覆盖所有结构"
```

---

## Task 2: 删除旧 exporter/n2c/agent 模块

**Files:**
- Delete: `src/uasset_read/exporter/` (12 files)
- Delete: `src/uasset_read/n2c/` (15+ files)
- Delete: `src/uasset_read/agent/` (2 files)

- [ ] **Step 1: 确认删除范围**

```bash
# 列出将要删除的文件
git rm -rn src/uasset_read/exporter/ src/uasset_read/n2c/ src/uasset_read/agent/ 2>/dev/null || find src/uasset_read/exporter src/uasset_read/n2c src/uasset_read/agent -type f
```

- [ ] **Step 2: 执行删除**

```bash
git rm -rf src/uasset_read/exporter/ src/uasset_read/n2c/ src/uasset_read/agent/
```

- [ ] **Step 3: 运行测试确认哪些被破坏**

Run: `python -m pytest tests/ -v --tb=line 2>&1 | head -50`
Expected: 多个测试因 import 失败而 ERROR（预期，后续 Task 修复）

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "chore: 删除 exporter/ n2c/ agent/ 模块（被 IR + renderers 替代）
- exporter/: 12 文件，IExporter + 注册表 + 批量导出
- n2c/: 15+ 文件，N2C 中间格式
- agent/: 2 文件，AI 翻译管线"
```

---

## Task 3: 实现渲染器基础（IRenderer + 注册表）

**Files:**
- Create: `src/uasset_read/renderers/base.py`
- Create: `src/uasset_read/renderers/__init__.py`
- Test: `tests/test_renderers.py`（基础部分）

- [ ] **Step 1: 编写渲染器基础测试**

```python
# tests/test_renderers.py — 基础部分
"""渲染器测试。"""
import pytest
from dataclasses import dataclass
from uasset_read.renderers.base import RenderOptions, IRenderer
from uasset_read.renderers import get_renderer, RENDERER_REGISTRY


class TestRenderOptions:
    def test_defaults(self):
        opts = RenderOptions()
        assert opts.verbose is False
        assert opts.indent == 2
        assert opts.include_schema is False

    def test_custom(self):
        opts = RenderOptions(verbose=True, indent=4, include_function_graphs=True)
        assert opts.verbose is True
        assert opts.indent == 4


class TestRendererRegistry:
    def test_get_renderer_json(self):
        r = get_renderer("json")
        assert r.format_name == "json"

    def test_get_renderer_unknown(self):
        with pytest.raises(ValueError, match="未知格式"):
            get_renderer("nonexistent")

    def test_list_formats(self):
        from uasset_read.renderers import list_formats
        fmts = list_formats()
        assert "json" in fmts
        assert "text" in fmts
        assert "markdown" in fmts
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_renderers.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 IRenderer ABC**

```python
# src/uasset_read/renderers/base.py
"""渲染器基础 — IRenderer ABC + RenderOptions。

渲染器只接收 PackageIR，不访问 ParseResult。
渲染器不做数据转换（GUID 格式化等在 IR 构建时完成）。
渲染器不拼接业务逻辑，只负责格式排版。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


@dataclass
class RenderOptions:
    """渲染选项（渲染器只读，不修改）。"""
    verbose: bool = False          # 是否包含额外字段
    indent: int = 2                # JSON 缩进
    include_schema: bool = False   # 是否包含字段语义注解
    include_function_graphs: bool = False  # 是否包含顶层 function_graphs 数组


class IRenderer(ABC):
    """渲染器抽象基类。"""

    @abstractmethod
    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        """将 IR 渲染为字符串。

        Args:
            ir: PackageIR 实例
            options: 渲染选项

        Returns:
            渲染后的字符串
        """
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """此渲染器处理的格式名称。"""
        ...
```

- [ ] **Step 4: 实现渲染器注册表**

```python
# src/uasset_read/renderers/__init__.py
"""渲染器注册表 — 格式名到渲染器的映射与分发。

取代旧的 ExporterRegistry + FORMAT_REGISTRY。
"""
from __future__ import annotations

from typing import Type

from uasset_read.renderers.base import IRenderer

# 渲染器注册表（由具体渲染器模块 import 时自动注册）
RENDERER_REGISTRY: dict[str, Type[IRenderer]] = {}


def register_renderer(format_name: str, renderer_class: Type[IRenderer]) -> None:
    """注册一个格式名到渲染器类的映射。

    Args:
        format_name: 格式名称（如 "json", "markdown"）
        renderer_class: 实现 IRenderer 的类

    Raises:
        ValueError: 格式名已注册
    """
    if format_name in RENDERER_REGISTRY:
        raise ValueError(f"Render format '{format_name}' is already registered")
    RENDERER_REGISTRY[format_name] = renderer_class


def get_renderer(format_name: str) -> IRenderer:
    """获取指定格式的渲染器实例。

    Args:
        format_name: 格式名称

    Returns:
        IRenderer 实例

    Raises:
        ValueError: 未知格式
    """
    renderer_class = RENDERER_REGISTRY.get(format_name)
    if renderer_class is None:
        available = ", ".join(sorted(RENDERER_REGISTRY.keys()))
        raise ValueError(f"Unknown render format: '{format_name}'. Available: {available}")
    return renderer_class()


def list_formats() -> list[str]:
    """返回所有已注册的格式名。"""
    return sorted(RENDERER_REGISTRY.keys())
```

- [ ] **Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_renderers.py::TestRenderOptions tests/test_renderers.py::TestRendererRegistry -v`
Expected: FAIL（注册表为空，JSON 渲染器未注册）

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/renderers/base.py src/uasset_read/renderers/__init__.py tests/test_renderers.py
git commit -m "feat: 实现渲染器基础（IRenderer ABC + 注册表）
- RenderOptions dataclass
- IRenderer 抽象基类
- 注册表支持自动注册和 get_renderer()"
```

---

## Task 4: 实现 IR 构建器

**Files:**
- Create: `src/uasset_read/ir_builder.py`
- Test: `tests/test_ir_builder.py`

- [ ] **Step 1: 编写 IR 构建器测试**

```python
# tests/test_ir_builder.py
"""IR 构建器测试。"""
import pytest
from unittest.mock import MagicMock, patch
from uasset_read.ir_builder import build_package_ir
from uasset_read.models.ir import PackageIR, ExportIR, PackageHeaderIR


def _make_mock_parse_result():
    """构造最小 mock ParseResult。"""
    result = MagicMock()
    result.summary.package_name = "/Game/Test/BP_Test"
    result.summary.package_class = "BP_Test_C"
    result.summary.package_flags = 0
    result.summary.total_export_count = 1
    result.summary.total_import_count = 1
    result.name_map = ["BP_Test", "SomeName"]
    result.import_map = []
    result.export_map = []
    result.linker = None
    result.blueprint = None
    result.version_container = MagicMock()
    result.version_container.get_ue_version_string.return_value = "5.x"
    result.errors = []
    result.warnings = []
    result.is_success = True
    return result


class TestBuildPackageIR:
    def test_build_minimal_result(self):
        result = _make_mock_parse_result()
        ir = build_package_ir(result)
        assert isinstance(ir, PackageIR)
        assert ir.header.package_name == "/Game/Test/BP_Test"
        assert ir.name_map == ["BP_Test", "SomeName"]
        assert ir.exports == []

    def test_build_with_exports(self):
        result = _make_mock_parse_result()
        mock_export = MagicMock()
        mock_export.object_name = "Default__BP_Test_C"
        mock_export.object_class = "BlueprintGeneratedClass"
        mock_export.serial_size = 100
        mock_export.class_index = None
        mock_export.super_index = None
        mock_export.outer_index = None
        mock_export.properties = []
        mock_export.graphs = []
        mock_export.bulk_data_header = None
        result.export_map = [mock_export]

        ir = build_package_ir(result)
        assert len(ir.exports) == 1
        assert ir.exports[0].object_name == "Default__BP_Test_C"
        assert ir.exports[0].serial_size == 100

    def test_build_with_linker(self):
        result = _make_mock_parse_result()
        mock_linker = MagicMock()
        mock_linker.resolve_package_index.return_value = "/Engine/Core/Object"
        result.linker = mock_linker

        ir = build_package_ir(result)
        assert ir.linker is not None
        assert ir.linker.has_linker is True
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_ir_builder.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 IR 构建器**

```python
# src/uasset_read/ir_builder.py
"""IR 构建层 — 将 ParseResult 转换为 PackageIR。

构建阶段处理所有 FPackageIndex 跨引用解析和 GUID 标准化。
渲染器只接收 PackageIR，不访问 ParseResult。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    PropertyIR,
    ExportIR,
    GraphIR,
    NodeIR,
    PinIR,
    LinkerSummaryIR,
)

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult


def build_package_ir(result: ParseResult) -> PackageIR:
    """将 ParseResult 转换为 PackageIR。

    构建阶段：
    1. 从 summary 提取 header
    2. 逐条转换 export_map 为 ExportIR
    3. 通过 linker 解析 import/export 路径
    4. GUID 标准化为 32 位小写 hex

    tolerant 模式：单个 Export 解析失败时跳过该项继续。
    strict 模式：任何失败立即抛出 IRError。
    """
    header = _build_header(result)
    exports = _build_exports(result)
    linker = _build_linker(result)

    return PackageIR(
        header=header,
        name_map=list(result.name_map) if result.name_map else [],
        imports=_build_imports(result),
        exports=exports,
        linker=linker,
    )


def _build_header(result: ParseResult) -> PackageHeaderIR:
    """从 summary 提取包头部。"""
    summary = result.summary
    version = "5.x"
    if result.version_container:
        version = result.version_container.get_ue_version_string()

    return PackageHeaderIR(
        package_name=getattr(summary, 'package_name', '') or '',
        package_class=getattr(summary, 'package_class', '') or '',
        package_flags=getattr(summary, 'package_flags', 0) or 0,
        total_export_count=getattr(summary, 'total_export_count', 0) or 0,
        total_import_count=getattr(summary, 'total_import_count', 0) or 0,
        ue_version=version,
    )


def _build_imports(result: ParseResult) -> list[dict]:
    """构建轻量导入摘要。"""
    imports = []
    for imp in (result.import_map or []):
        imports.append({
            "class_package": getattr(imp, 'class_package', ''),
            "class_name": getattr(imp, 'class_name', ''),
            "object_name": getattr(imp, 'object_name', ''),
        })
    return imports


def _build_exports(result: ParseResult) -> list[ExportIR]:
    """逐条转换 export_map 为 ExportIR。"""
    exports = []
    for idx, export in enumerate(result.export_map or []):
        try:
            export_ir = _build_export_ir(idx, export, result)
            exports.append(export_ir)
        except Exception:
            # tolerant 模式：跳过失败 export
            pass
    return exports


def _build_export_ir(idx: int, export, result: ParseResult) -> ExportIR:
    """构建单个 ExportIR。"""
    # 解析 outer_index
    outer_resolved = None
    if hasattr(export, 'outer_index') and export.outer_index:
        outer_resolved = _resolve_package_index(result, export.outer_index)

    # 解析 super_index
    super_resolved = None
    if hasattr(export, 'super_index') and export.super_index:
        super_resolved = _resolve_package_index(result, export.super_index)

    # 解析 parent_class（蓝图主类）
    parent_class = None
    if result.blueprint and getattr(result.blueprint, 'parent_class', None):
        parent_class = result.blueprint.parent_class

    # 转换属性
    properties = []
    for prop in (getattr(export, 'properties', None) or []):
        properties.append(_build_property_ir(prop))

    # 转换图（仅蓝图类）
    graphs = []
    for graph in (getattr(export, 'graphs', None) or []):
        graphs.append(_build_graph_ir(graph))

    # BulkData 头部
    bulk_data = getattr(export, 'bulk_data_header', None)

    object_class = getattr(export, 'object_class', '') or ''
    object_name = getattr(export, 'object_name', '') or ''
    serial_size = getattr(export, 'serial_size', 0) or 0

    return ExportIR(
        index=idx,
        object_name=object_name,
        object_class=object_class,
        serial_size=serial_size,
        outer_index_resolved=outer_resolved,
        super_index_resolved=super_resolved,
        parent_class=parent_class,
        properties=properties,
        graphs=graphs,
        bulk_data=bulk_data,
    )


def _build_property_ir(prop) -> PropertyIR:
    """转换单个属性为 PropertyIR。"""
    return PropertyIR(
        name=getattr(prop, 'name', '') or '',
        type=getattr(prop, 'type', '') or '',
        value=getattr(prop, 'value', None),
        array_index=getattr(prop, 'array_index', -1) or -1,
        guid=_normalize_guid(getattr(prop, 'guid', None)),
    )


def _build_graph_ir(graph) -> GraphIR:
    """转换单个图 GraphIR。"""
    nodes = []
    for node in (getattr(graph, 'nodes', None) or []):
        nodes.append(_build_node_ir(node))

    return GraphIR(
        graph_guid=_normalize_guid(getattr(graph, 'graph_guid', None) or ''),
        graph_name=getattr(graph, 'graph_name', '') or '',
        graph_class=getattr(graph, 'graph_class', '') or '',
        nodes=nodes,
        execution_chains=getattr(graph, 'execution_chains', None) or [],
    )


def _build_node_ir(node) -> NodeIR:
    """转换单个 NodeIR。"""
    pins = []
    for pin in (getattr(node, 'pins', None) or []):
        pins.append(_build_pin_ir(pin))

    return NodeIR(
        node_guid=_normalize_guid(getattr(node, 'node_guid', None) or ''),
        node_class=getattr(node, 'class_name', '') or '',
        node_comment=getattr(node, 'node_comment', None),
        pins=pins,
        execution_flow=getattr(node, 'execution_flow', None) or [],
    )


def _build_pin_ir(pin) -> PinIR:
    """转换单个 PinIR。"""
    linked_to = []
    for ref in (getattr(pin, 'linked_to_raw', None) or []):
        guid = _extract_pin_guid(ref)
        if guid:
            linked_to.append(guid)

    direction = "EGPD_Input"
    if getattr(pin, 'direction', 0) == 1:
        direction = "EGPD_Output"

    return PinIR(
        pin_name=getattr(pin, 'pin_name', '') or '',
        pin_type=getattr(pin, 'pin_type', '') or '',
        pin_type_value=getattr(pin, 'pin_type_value', None),
        linked_to=linked_to,
        direction=direction,
        default_value=getattr(pin, 'default_value', None),
    )


def _resolve_package_index(result: ParseResult, pkg_index) -> str | None:
    """通过 linker 解析 PackageIndex 为对象路径。"""
    if result.linker is None:
        return None
    try:
        obj_ref = result.linker.resolve_package_index(pkg_index)
        return str(obj_ref) if obj_ref else None
    except Exception:
        return None


def _build_linker(result: ParseResult) -> LinkerSummaryIR | None:
    """构建 linker 摘要。"""
    linker = result.linker
    if linker is None:
        return None

    import_paths = []
    for imp in (result.import_map or []):
        path = f"{getattr(imp, 'class_package', '')}.{getattr(imp, 'class_name', '')}"
        if path.strip("."):
            import_paths.append(path)

    export_paths = []
    for exp in (result.export_map or []):
        path = getattr(exp, 'object_name', '')
        if path:
            export_paths.append(path)

    return LinkerSummaryIR(
        has_linker=True,
        import_paths=import_paths,
        export_paths=export_paths,
    )


def _normalize_guid(guid: str | None) -> str | None:
    """GUID 标准化为 32 位小写 hex。"""
    if not guid:
        return None
    cleaned = guid.replace("-", "").lower()
    if len(cleaned) == 32 and all(c in "0123456789abcdef" for c in cleaned):
        return cleaned
    return None


def _extract_pin_guid(ref) -> str | None:
    """从 PinReference 提取并标准化 GUID。"""
    if isinstance(ref, dict):
        raw = ref.get("pin_guid") or ref.get("pin_id")
        return _normalize_guid(raw) if raw else None
    if isinstance(ref, str):
        return _normalize_guid(ref)
    raw = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)
    return _normalize_guid(raw) if raw else None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_ir_builder.py -v`
Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/ir_builder.py tests/test_ir_builder.py
git commit -m "feat: 实现 IR 构建器（build_package_ir）
- ParseResult → PackageIR 转换
- 跨引用解析、GUID 标准化
- tolerant 模式跳过失败 export"
```

---

## Task 5: 实现 JSON 渲染器 + parse_single

**Files:**
- Create: `src/uasset_read/renderers/json_renderer.py`
- Create: `src/uasset_read/core.py`
- Test: `tests/test_renderers.py`（JSON 部分）+ `tests/test_core_api.py`

- [ ] **Step 1: 实现 JSON 渲染器**

```python
# src/uasset_read/renderers/json_renderer.py
"""JSON 渲染器 — 递归序列化 PackageIR 为 JSON。"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class JSONRenderer(IRenderer):
    """JSON 渲染器。递归序列化 IR 为 JSON，包含 status 字段。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        data = {
            "status": {"status": "success", "message": None, "code": None},
            "summary": {
                "package_name": ir.header.package_name,
                "package_class": ir.header.package_class,
                "package_flags": ir.header.package_flags,
                "total_export_count": ir.header.total_export_count,
                "total_import_count": ir.header.total_import_count,
                "ue_version": ir.header.ue_version,
            },
            "name_map": ir.name_map,
            "imports": ir.imports,
            "exports": [self._export_to_dict(e, options) for e in ir.exports],
        }
        if ir.linker is not None:
            data["linker"] = {
                "has_linker": ir.linker.has_linker,
                "import_paths": ir.linker.import_paths,
                "export_paths": ir.linker.export_paths,
            }

        if options.include_function_graphs:
            data["function_graphs"] = self._build_function_graphs(ir)

        return json.dumps(data, indent=options.indent, ensure_ascii=False)

    def _export_to_dict(self, export, options: RenderOptions) -> dict[str, Any]:
        d = {
            "index": export.index,
            "object_name": export.object_name,
            "object_class": export.object_class,
            "serial_size": export.serial_size,
            "outer_index_resolved": export.outer_index_resolved,
            "super_index_resolved": export.super_index_resolved,
            "parent_class": export.parent_class,
            "properties": [self._property_to_dict(p) for p in export.properties],
            "graphs": [self._graph_to_dict(g, options) for g in export.graphs],
        }
        if export.bulk_data is not None:
            d["bulk_data"] = export.bulk_data
        return d

    def _property_to_dict(self, prop) -> dict[str, Any]:
        return {
            "name": prop.name,
            "type": prop.type,
            "value": prop.value,
            "array_index": prop.array_index,
            "guid": prop.guid,
        }

    def _graph_to_dict(self, graph, options: RenderOptions) -> dict[str, Any]:
        d = {
            "graph_name": graph.graph_name,
            "graph_guid": graph.graph_guid,
            "nodes": [self._node_to_dict(n) for n in graph.nodes],
            "execution_chains": graph.execution_chains,
        }
        return d

    def _node_to_dict(self, node) -> dict[str, Any]:
        return {
            "node_guid": node.node_guid,
            "node_class": node.node_class,
            "node_comment": node.node_comment,
            "pins": [self._pin_to_dict(p) for p in node.pins],
            "execution_flow": node.execution_flow,
        }

    def _pin_to_dict(self, pin) -> dict[str, Any]:
        return {
            "pin_name": pin.pin_name,
            "pin_type": pin.pin_type,
            "pin_type_value": pin.pin_type_value,
            "linked_to": pin.linked_to,
            "direction": pin.direction,
            "default_value": pin.default_value,
        }

    def _build_function_graphs(self, ir: PackageIR) -> list[dict]:
        """按函数/事件分组节点 + 签名 + 执行流。"""
        graphs = []
        for export in ir.exports:
            for graph in export.graphs:
                graphs.append({
                    "export_name": export.object_name,
                    "graph_name": graph.graph_name,
                    "graph_guid": graph.graph_guid,
                    "node_count": len(graph.nodes),
                    "execution_chains": graph.execution_chains,
                })
        return graphs

    @property
    def format_name(self) -> str:
        return "json"


# Auto-registration
register_renderer("json", JSONRenderer)
register_renderer("json_summary", JSONRenderer)
```

- [ ] **Step 2: 实现 core.py（parse_single + parse_batch + list_formats）**

```python
# src/uasset_read/core.py
"""核心解析 API — 纯函数，无 argparse、无 sys.exit、无 print。

CLI、独立脚本、未来 Skill 共享此 API。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from uasset_read.ir_builder import build_package_ir
from uasset_read.models.ir import PackageIR
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.renderers import get_renderer, list_formats as _list_renderer_formats, RenderOptions


@dataclass
class BatchResult:
    """批量导出结果。"""
    total: int = 0
    success: list[str] = field(default_factory=list)
    skipped: list[tuple] = field(default_factory=list)
    failed: list[tuple] = field(default_factory=list)


def parse_single(
    file_path: str,
    format: str = "text",
    tolerant: bool = True,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
) -> str:
    """解析单个 .uasset/.umap，返回格式化字符串。

    纯函数，无 argparse、无 sys.exit、无 print。
    需要 linker 的格式内部自动选择 parse_uasset_with_linker。
    """
    # 需要 linker 的格式
    linker_formats = {"cpp_skeleton", "json", "json_summary"}
    if format in linker_formats:
        result = parse_uasset_with_linker(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
        )
    else:
        result = parse_package(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
        )

    if not result.is_success:
        raise ParseError(f"Parse failed: {'; '.join(result.errors)}")

    # 构建 IR
    ir = build_package_ir(result)

    # 渲染
    renderer = get_renderer(format)
    options = RenderOptions(
        verbose=verbose,
        include_schema=include_schema,
        include_function_graphs=include_function_graphs,
    )
    return renderer.render(ir, options)


class ParseError(Exception):
    """解析失败。"""
    pass


def parse_batch(
    input_dir: str,
    format: str = "text",
    output_dir: str | None = None,
    tolerant: bool = True,
    **format_options,
) -> BatchResult:
    """批量解析目录下所有 .uasset/.umap。"""
    input_path = Path(input_dir)
    if not input_path.is_dir():
        raise ValueError(f"Not a directory: {input_dir}")

    package_files = sorted([*input_path.glob("*.uasset"), *input_path.glob("*.umap")])
    if not package_files:
        raise ValueError(f"No .uasset/.umap files found in {input_dir}")

    if output_dir is None:
        output_dir = str(input_path / "output")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = BatchResult(total=len(package_files))

    for pf in package_files:
        try:
            output_str = parse_single(str(pf), format=format, tolerant=tolerant, **format_options)
            out_file = output_path / f"{pf.stem}.{format.split('_')[0]}"
            if format.startswith("json"):
                out_file = out_file.with_suffix(".json")
            elif format.startswith("text"):
                out_file = out_file.with_suffix(".txt")
            elif format == "markdown":
                out_file = out_file.with_suffix(".md")
            else:
                out_file = out_file.with_suffix(f".{format}")
            out_file.write_text(output_str, encoding="utf-8")
            result.success.append(str(out_file))
        except Exception as e:
            result.failed.append((str(pf), str(e)))

    return result


def list_formats() -> list[str]:
    """返回所有支持的格式名列表。"""
    return _list_renderer_formats()
```

- [ ] **Step 3: 编写 core.py API 测试**

```python
# tests/test_core_api.py
"""core.py API 测试。"""
import pytest
from unittest.mock import patch, MagicMock
from uasset_read.core import parse_single, list_formats, ParseError


class TestListFormats:
    def test_json_in_formats(self):
        fmts = list_formats()
        assert "json" in fmts

    def test_text_in_formats(self):
        fmts = list_formats()
        assert "text" in fmts


class TestParseSingle:
    def test_parse_single_raises_on_parse_failure(self):
        """parse_single 在解析失败时抛出 ParseError。"""
        with patch("uasset_read.core.parse_package") as mock_parse:
            mock_result = MagicMock()
            mock_result.is_success = False
            mock_result.errors = ["test error"]
            mock_parse.return_value = mock_result

            with pytest.raises(ParseError, match="Parse failed"):
                parse_single("nonexistent.uasset", format="text")
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_renderers.py::TestRendererRegistry tests/test_core_api.py -v`
Expected: JSON 注册测试 PASS，其他部分可能 FAIL（其他渲染器未注册）

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/renderers/json_renderer.py src/uasset_read/core.py tests/test_core_api.py tests/test_renderers.py
git commit -m "feat: 实现 JSON 渲染器 + core.py 核心 API
- JSONRenderer: 递归序列化 PackageIR
- parse_single/parse_batch/list_formats 纯函数
- 自动注册 json/json_summary 格式"
```

---

## Task 6: 迁移剩余 5 个渲染器

**Files:**
- Create: `src/uasset_read/renderers/text_renderer.py`
- Create: `src/uasset_read/renderers/markdown_renderer.py`
- Create: `src/uasset_read/renderers/blueprint_text_renderer.py`
- Create: `src/uasset_read/renderers/blueprint_ue_renderer.py`
- Create: `src/uasset_read/renderers/cpp_skeleton_renderer.py`
- Modify: `tests/test_renderers.py`（追加测试）

- [ ] **Step 1: 实现 Text 渲染器**

```python
# src/uasset_read/renderers/text_renderer.py
"""YAML 风格文本渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class TextRenderer(IRenderer):
    """YAML 风格缩进文本渲染器。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []
        self._render_package(lines, ir, options)
        return "\n".join(lines)

    def _render_package(self, lines: list[str], ir: PackageIR, options: RenderOptions) -> None:
        lines.append(f"Package: {ir.header.package_name}")
        lines.append(f"  Class: {ir.header.package_class}")
        lines.append(f"  Flags: {ir.header.package_flags}")
        lines.append(f"  Exports: {ir.header.total_export_count}")
        lines.append(f"  Imports: {ir.header.total_import_count}")
        lines.append(f"  UE Version: {ir.header.ue_version}")
        lines.append("")

        for export in ir.exports:
            self._render_export(lines, export, options)

    def _render_export(self, lines: list[str], export, options: RenderOptions) -> None:
        lines.append(f"Export[{export.index}]: {export.object_name}")
        lines.append(f"  Class: {export.object_class}")
        lines.append(f"  Size: {export.serial_size}")
        if export.parent_class:
            lines.append(f"  Parent: {export.parent_class}")
        lines.append(f"  Properties ({len(export.properties)}):")
        for prop in export.properties:
            val = self._format_value(prop.value)
            lines.append(f"    {prop.name} ({prop.type}): {val}")
        lines.append("")

    def _format_value(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return repr(value)

    @property
    def format_name(self) -> str:
        return "text"


# Auto-registration
register_renderer("text", TextRenderer)
register_renderer("text_summary", TextRenderer)
```

- [ ] **Step 2: 实现 Markdown 渲染器**

```python
# src/uasset_read/renderers/markdown_renderer.py
"""Markdown + Mermaid 流程图渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class MarkdownRenderer(IRenderer):
    """Markdown + Mermaid 流程图渲染器。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []
        lines.append(f"# {ir.header.package_name}")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Class | {ir.header.package_class} |")
        lines.append(f"| Flags | {ir.header.package_flags} |")
        lines.append(f"| Exports | {ir.header.total_export_count} |")
        lines.append(f"| Imports | {ir.header.total_import_count} |")
        lines.append(f"| UE Version | {ir.header.ue_version} |")
        lines.append("")

        for export in ir.exports:
            lines.append(f"## {export.object_name}")
            lines.append(f"- **Class**: {export.object_class}")
            lines.append(f"- **Size**: {export.serial_size}")
            if export.properties:
                lines.append("")
                lines.append("### Properties")
                lines.append("")
                lines.append("| Name | Type | Value |")
                lines.append("|------|------|-------|")
                for prop in export.properties:
                    val = str(prop.value)[:50] if prop.value is not None else "null"
                    lines.append(f"| {prop.name} | {prop.type} | {val} |")

            for graph in export.graphs:
                lines.append("")
                lines.append(f"### Graph: {graph.graph_name}")
                lines.append("")
                lines.append("```mermaid")
                lines.append("graph TD")
                for node in graph.nodes:
                    label = node.node_comment or node.node_class
                    lines.append(f'    {node.node_guid[:8]}["{label}"]')
                for node in graph.nodes:
                    for pin in node.pins:
                        for target in pin.linked_to:
                            lines.append(f'    {node.node_guid[:8]} --> {target[:8]}')
                lines.append("```")
            lines.append("")

        return "\n".join(lines)

    @property
    def format_name(self) -> str:
        return "markdown"


# Auto-registration
register_renderer("markdown", MarkdownRenderer)
```

- [ ] **Step 3: 实现 Blueprint Text 渲染器**

```python
# src/uasset_read/renderers/blueprint_text_renderer.py
"""蓝图翻译参考文本渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class BlueprintTextRenderer(IRenderer):
    """紧凑节点列表，用于蓝图翻译参考。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []
        for export in ir.exports:
            for graph in export.graphs:
                lines.append(f"Graph: {graph.graph_name}")
                for node in graph.nodes:
                    comment = f" # {node.node_comment}" if node.node_comment else ""
                    lines.append(f"  [{node.node_class}] {node.node_guid[:8]}...{comment}")
                    for pin in node.pins:
                        linked = f" -> {pin.linked_to}" if pin.linked_to else ""
                        lines.append(f"    Pin: {pin.pin_name} ({pin.pin_type}){linked}")
                lines.append("")
        return "\n".join(lines)

    @property
    def format_name(self) -> str:
        return "blueprint_text"


# Auto-registration
register_renderer("blueprint_text", BlueprintTextRenderer)
```

- [ ] **Step 4: 实现 Blueprint UE 渲染器**

```python
# src/uasset_read/renderers/blueprint_ue_renderer.py
"""模拟 UE Ctrl+C 文本格式渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class BlueprintUERenderer(IRenderer):
    """模拟 UE 编辑器 Ctrl+C 复制的蓝图文本格式。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []
        lines.append(f'Begin Object Class="{ir.header.package_class}" Name="{ir.header.package_name}"')
        for export in ir.exports:
            lines.append(f'   Begin Object Class="{export.object_class}" Name="{export.object_name}"')
            for prop in export.properties:
                lines.append(f'      {prop.name}={self._format_ue_value(prop.value)}')
            lines.append("   End Object")
        lines.append("End Object")
        return "\n".join(lines)

    def _format_ue_value(self, value) -> str:
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "True" if value else "False"
        return str(value)

    @property
    def format_name(self) -> str:
        return "blueprint_ue_text"


# Auto-registration
register_renderer("blueprint_ue_text", BlueprintUERenderer)
```

- [ ] **Step 5: 实现 Cpp Skeleton 渲染器**

```python
# src/uasset_read/renderers/cpp_skeleton_renderer.py
"""C++ 头文件骨架渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class CppSkeletonRenderer(IRenderer):
    """C++ 类骨架生成器（.h header）。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []
        class_name = ir.header.package_class.replace("_C", "")
        parent = ir.exports[0].parent_class if ir.exports else None
        parent_cpp = self._ue_to_cpp_class(parent) if parent else "UObject"

        lines.append(f'#pragma once')
        lines.append(f'')
        lines.append(f'#include "CoreMinimal.h"')
        lines.append(f'#include "{self._header_for_class(parent_cpp)}"')
        lines.append(f'')
        lines.append(f'#include "{class_name}.generated.h"')
        lines.append(f'')
        lines.append(f'UCLASS()')
        lines.append(f'class {class_name} : public {parent_cpp}')
        lines.append(f'{{')
        lines.append(f'\tGENERATED_BODY()')
        lines.append(f'')
        lines.append(f'public:')

        for export in ir.exports:
            for prop in export.properties:
                cpp_type = self._property_to_cpp_type(prop.type, prop.value)
                lines.append(f'\tUPROPERTY()')
                lines.append(f'\t{cpp_type} {prop.name};')

        lines.append(f'}};')
        return "\n".join(lines)

    def _ue_to_cpp_class(self, ue_class: str) -> str:
        base = ue_class.split("/")[-1] if "/" in ue_class else ue_class
        return base if base.startswith("A") or base.startswith("U") else f"U{base}"

    def _header_for_class(self, cpp_class: str) -> str:
        return f"{cpp_class.rstrip('_C')}.h"

    def _property_to_cpp_type(self, prop_type: str, value) -> str:
        type_map = {
            "IntProperty": "int32",
            "FloatProperty": "float",
            "BoolProperty": "bool",
            "StrProperty": "FString",
            "NameProperty": "FName",
            "TextProperty": "FText",
            "ObjectProperty": "UObject*",
            "ClassProperty": "UClass*",
        }
        return type_map.get(prop_type, "UObject*")

    @property
    def format_name(self) -> str:
        return "cpp_skeleton"


# Auto-registration
register_renderer("cpp_skeleton", CppSkeletonRenderer)
```

- [ ] **Step 6: 更新渲染器测试**

```python
# 在 tests/test_renderers.py 中追加：

class TestJsonRenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/Test", package_class="Test_C",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        renderer = get_renderer("json")
        output = renderer.render(ir, RenderOptions())

        import json
        data = json.loads(output)
        assert data["status"]["status"] == "success"
        assert data["summary"]["package_name"] == "/Game/Test"
        assert "blueprint" not in data  # 无顶层 blueprint 字段


class TestTextRenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/Test", package_class="Test_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        renderer = get_renderer("text")
        output = renderer.render(ir, RenderOptions())

        assert "Package: /Game/Test" in output


class TestMarkdownRenderer:
    def test_render_minimal_ir(self):
        from uasset_read.renderers import get_renderer
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        from uasset_read.renderers.base import RenderOptions

        header = PackageHeaderIR(
            package_name="/Game/Test", package_class="Test_C",
            package_flags=0, total_export_count=0, total_import_count=0,
            ue_version="5.x")
        ir = PackageIR(header=header, name_map=["Test"], imports=[], exports=[], linker=None)

        renderer = get_renderer("markdown")
        output = renderer.render(ir, RenderOptions())

        assert "# /Game/Test" in output
        assert "| Class |" in output
```

- [ ] **Step 7: 运行测试验证全部通过**

Run: `python -m pytest tests/test_renderers.py -v`
Expected: ALL PASS

- [ ] **Step 8: 提交**

```bash
git add src/uasset_read/renderers/text_renderer.py src/uasset_read/renderers/markdown_renderer.py src/uasset_read/renderers/blueprint_text_renderer.py src/uasset_read/renderers/blueprint_ue_renderer.py src/uasset_read/renderers/cpp_skeleton_renderer.py tests/test_renderers.py
git commit -m "feat: 迁移全部 6 个渲染器（JSON/Text/Markdown/BlueprintText/BlueprintUE/CppSkeleton）
- 每个渲染器自动注册到 RENDERER_REGISTRY
- JSON 消除 blueprint 顶层对象
- Markdown 含 Mermaid 流程图"
```

---

## Task 7: CLI 瘦身

**Files:**
- Modify: `src/uasset_read/cli.py`

- [ ] **Step 1: 重写 cli.py**

```python
# src/uasset_read/cli.py
"""CLI 入口模块 — argparse 参数解析 + 委托 core.py。

核心逻辑与入口分离：core.py 提供纯解析函数，CLI 仅负责参数解析和输出写入。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from uasset_read.core import parse_single, parse_batch, list_formats, ParseError

# Exit code constants
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3


def create_parser() -> argparse.ArgumentParser:
    """Create argparse parser for CLI."""
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset/.umap files and output structured data'
    )

    parser.add_argument('file', nargs='?', default=None,
                        help='Path to .uasset/.umap file to parse (or directory in --batch mode)')

    # Mutually exclusive output flags
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--json-summary', action='store_true', help='Output compact JSON summary')
    group.add_argument('--text', action='store_true', help='Output YAML-style text (default)')
    group.add_argument('--text-summary', action='store_true', help='Output compact text summary')
    group.add_argument('--summary', action='store_true', help='Output compact summary')
    group.add_argument('--markdown', action='store_true', help='Output Markdown format')
    group.add_argument('--blueprint-text', action='store_true', help='Output blueprint translation reference text')
    group.add_argument('--blueprint-ue-text', action='store_true', help='Output UE-style blueprint text')
    group.add_argument('--cpp-skeleton', action='store_true', help='Output C++ class skeleton')

    # Optional flags
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file instead of stdout')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output only specific export by index')
    parser.add_argument('--schema', action='store_true', help='Include field semantic annotations')
    parser.add_argument('--function-graphs', action='store_true', help='Include function_graphs array')
    parser.add_argument('--asset-root', action='append', default=[],
                        help='Root directory to search for parent .uasset files')
    parser.add_argument('--include-parent-assets', action='store_true',
                        help='Resolve and parse parent Blueprint assets')
    parser.add_argument('--mappings', metavar='FILE', help='Load .usmap/.jmap type mappings')
    parser.add_argument('--game', metavar='NAME', help='Enable game-specific property readers')
    parser.add_argument('--tolerant', action='store_true', default=True, help='Enable tolerant mode (default)')
    parser.add_argument('--strict', action='store_true', help='Disable tolerant mode')

    # Batch and utility flags
    parser.add_argument('--list-formats', action='store_true', help='List all available export formats')
    parser.add_argument('--batch', action='store_true', help='Enable batch mode')
    parser.add_argument('--batch-dir', metavar='DIR', help='Output directory for batch mode')
    parser.add_argument('--list-package-files', action='store_true', help='List discovered package files')

    return parser


def resolve_format(args) -> str:
    """从 CLI 参数解析导出格式名。"""
    if args.blueprint_text:
        return "blueprint_text"
    if args.blueprint_ue_text:
        return "blueprint_ue_text"
    if args.cpp_skeleton:
        return "cpp_skeleton"
    if args.markdown:
        return "markdown"
    if args.summary or args.json_summary:
        return "json_summary"
    if args.json:
        return "json"
    if args.text_summary:
        return "text_summary"
    if args.text:
        return "text"
    return "text"


def _write_output(output_str: str, output_path: str | None) -> None:
    """统一输出写入。"""
    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Output written to {output_path}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        print(output_str)


def main():
    """Main CLI entry point."""
    parser = create_parser()

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code == 0:
            sys.exit(EXIT_SUCCESS)
        sys.exit(EXIT_ARGUMENT_ERROR)

    # --list-formats
    if args.list_formats:
        formats = list_formats()
        print("Available export formats:")
        for fmt in formats:
            print(f"  --{fmt.replace('_', '-')}")
        sys.exit(EXIT_SUCCESS)

    # Batch mode
    if args.batch:
        _handle_batch(args)
        return

    # Validate positional arg
    if args.file is None:
        print("Error: file argument is required", file=sys.stderr)
        sys.exit(EXIT_ARGUMENT_ERROR)

    file_path = Path(args.file)
    if not file_path.is_file():
        if file_path.is_dir():
            print(f"Error: Not a file: {args.file}", file=sys.stderr)
        else:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    fmt = resolve_format(args)
    tolerant = not args.strict

    # --list-package-files
    if args.list_package_files:
        _handle_list_package_files(args.file, tolerant)
        return

    try:
        output_str = parse_single(
            str(file_path),
            format=fmt,
            tolerant=tolerant,
            verbose=args.verbose,
            include_schema=args.schema or args.verbose,
            include_function_graphs=args.function_graphs,
            include_parent_assets=args.include_parent_assets,
            asset_roots=list(args.asset_root or []),
            mappings_path=args.mappings,
            game=args.game,
        )
    except ParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)
    except Exception as e:
        print(f"Error: Unexpected parse failure: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    _write_output(output_str, args.output)
    sys.exit(EXIT_SUCCESS)


def _handle_batch(args):
    """处理批量导出模式。"""
    input_dir = Path(args.file)
    if not input_dir.is_dir():
        print(f"Error: Not a directory: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    output_dir = args.batch_dir or str(input_dir / "output")

    try:
        result = parse_batch(
            str(input_dir),
            format=resolve_format(args),
            output_dir=output_dir,
            tolerant=not args.strict,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    print(f"Batch export complete: {result.total} files", file=sys.stderr)
    print(f"  Success: {len(result.success)}", file=sys.stderr)
    if result.skipped:
        print(f"  Skipped: {len(result.skipped)}", file=sys.stderr)
    if result.failed:
        print(f"  Failed: {len(result.failed)}", file=sys.stderr)
        for path, error in result.failed:
            print(f"    - {Path(path).name}: {error}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    sys.exit(EXIT_SUCCESS)


def _handle_list_package_files(file_path: str, tolerant: bool) -> None:
    """列出发现的 package 文件。"""
    import json
    from uasset_read.package import open_package_bundle
    try:
        bundle = open_package_bundle(file_path, tolerant=tolerant)
    except Exception as e:
        print(f"Error: Package discovery failed: {e}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)
    print(json.dumps({
        "package_kind": bundle.package_kind,
        "container": bundle.container,
        "files": bundle.package_files,
    }, indent=2, ensure_ascii=False))
    sys.exit(EXIT_SUCCESS)
```

- [ ] **Step 2: 更新 __main__.py**

```python
# src/uasset_read/__main__.py
"""支持 python -m uasset_read 直接运行。"""
from uasset_read.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 更新 __init__.py**

在 `src/uasset_read/__init__.py` 中删除对 exporter/n2c/agent 的引用，添加 core 导出：

```python
# 删除所有 from .exporter 导入
# 添加：
from .core import parse_single, parse_batch, list_formats

# 更新 __all__，添加 core API，删除 exporter 相关
__all__ = [
    # ... existing ...
    "parse_single",
    "parse_batch",
    "list_formats",
]
```

- [ ] **Step 4: 更新 pyproject.toml 入口**

修改 `[project.scripts]`:
```toml
[project.scripts]
uasset-read = "uasset_read.cli:main"
```
（保持不变，因为 cli.py 仍然有 main()）

- [ ] **Step 5: 运行 CLI 测试**

Run: `python -m pytest tests/test_api_cleanup.py -v --tb=short 2>&1 | head -40`

Expected: 测试引用旧 exporter 的会 FAIL，需要更新

- [ ] **Step 6: 更新 test_api_cleanup.py**

注意：删除以下已不存在功能的测试：
- `test_build_export_options_keeps_linker_json_flags`（`_build_export_options` 已删除）
- `test_graph_mode_json_summary_uses_summary_formatter`（`_handle_graph_mode` 已删除）
- `test_graph_mode_summary_alias_uses_json_summary`（同上）
- `test_graph_mode_text_summary_uses_text_summary`（同上）
- `test_batch_exporter_passes_parse_options`（BatchExporter 已删除）
- `test_batch_options_from_cli_include_parse_flags`（同上）
- `test_strict_property_parse_error_is_fatal`（导出器已删除）
- `test_blueprint_metadata_from_archive_error_is_actionable`（BlueprintMetadata.from_archive 已变为 NotImplementedError）

保留的测试：
- `test_format_graphs_json_minimal_graph_does_not_crash`（graph 模块仍存在）
- `test_format_node_dict_comment_fields`（graph 模块仍存在）
- `test_listed_cli_formats_are_parseable`（改用 `list_formats()` 替代 `ExporterRegistry.list_formats()`）
- `test_parse_uasset_with_linker_uses_provider`
- `test_parse_package_rejects_unused_aes_key`
- `test_filesystem_provider_supports_root_relative_paths`
- `test_source_files_do_not_have_utf8_bom`
- `test_root_parse_uasset_name_shadows_module_compatibly`
- `test_iostore_directory_index_list_files_is_stable_when_unparsed`

```python
# tests/test_api_cleanup.py — 更新引用新 API
from __future__ import annotations

from pathlib import Path
import importlib
import json

import pytest

from uasset_read.cli import create_parser
from uasset_read.core import parse_single, list_formats, ParseError
from uasset_read.graph.flow_builder import format_graphs_json, format_node_dict
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.models.blueprint import BlueprintMetadata
from uasset_read.models.core import FEdGraphPinType, UEdGraph, UEdGraphNode, UEdGraphPin
from uasset_read.models.result import ParseResult
from uasset_read.package import FileSystemPackageProvider
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker


def test_format_graphs_json_minimal_graph_does_not_crash():
    graph = UEdGraph(
        graph_name="EventGraph",
        graph_class="EdGraph",
        nodes=[UEdGraphNode(node_guid="node-1", class_name="K2Node_Event")],
    )

    payload = format_graphs_json([graph])

    assert payload[0]["graph_name"] == "EventGraph"
    assert payload[0]["nodes"][0]["node_name"] == "K2Node_Event_0"


def test_format_node_dict_comment_fields():
    node = UEdGraphNode(
        node_guid="comment-1",
        class_name="EdGraphNode_Comment",
        node_comment="Note",
        node_data={"node_width": 300, "node_height": 120, "font_size": 18},
    )

    payload = format_node_dict(node, 2)

    assert payload["comment"] == {
        "text": "Note",
        "width": 300,
        "height": 120,
        "font_size": 18,
    }


def test_listed_cli_formats_are_parseable():
    parser = create_parser()

    for fmt in list_formats():
        parser.parse_args([f"--{fmt.replace('_', '-')}", "Asset.uasset"])


class _Archive:
    _byte_swapping = False

    def get_mmap_info(self):
        return {"used": False, "warning": None}

    def close(self):
        pass


class _Bundle:
    package_kind = "asset"
    package_files = {".uasset": "<test>"}
    container = "test"

    def open_archive(self, tolerant: bool = False):
        return _Archive()


class _Provider:
    def open_package_bundle(self, path: str, tolerant: bool = False):
        return _Bundle()


def test_parse_uasset_with_linker_uses_provider():
    from unittest.mock import patch
    with patch("uasset_read.parse_uasset.open_package_bundle") as mock_open:
        mock_open.return_value = _Bundle()
        result = parse_uasset_with_linker("Game/A.uasset", provider=_Provider())
        assert mock_open.called
        assert not result.is_success


def test_parse_package_rejects_unused_aes_key():
    result = parse_package("Game/A.uasset", aes_key=b"0" * 16)

    assert not result.is_success
    assert "Unsupported argument: aes_key" in result.errors[0]


def test_filesystem_provider_supports_root_relative_paths(tmp_path: Path):
    asset_dir = tmp_path / "Game"
    asset_dir.mkdir()
    asset = asset_dir / "A.uasset"
    asset.write_bytes(b"asset")

    bundle = FileSystemPackageProvider(tmp_path).open_package_bundle("Game/A.uasset")

    assert bundle.main_path == str(asset)


def test_source_files_do_not_have_utf8_bom():
    root = Path(__file__).resolve().parents[1] / "src" / "uasset_read"
    offenders = [
        str(path.relative_to(root.parent.parent))
        for path in root.rglob("*.py")
        if path.read_bytes().startswith(b"\xef\xbb\xbf")
    ]

    assert offenders == []
```

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/cli.py src/uasset_read/__main__.py src/uasset_read/__init__.py tests/test_api_cleanup.py pyproject.toml
git commit -m "refactor: CLI 瘦身 — 委托 core.py 核心 API
- cli.py 仅保留 argparse + 输出写入
- 核心逻辑在 core.parse_single/parse_batch
- 删除 exporter 相关引用
- 更新 test_api_cleanup.py"
```

---

## Task 8: 创建 diag.py 和 simple.py

**Files:**
- Create: `diag.py`
- Create: `src/uasset_read/simple.py`

- [ ] **Step 1: 创建 diag.py**

```python
#!/usr/bin/env python
"""快捷诊断入口：python diag.py <path.uasset> [--format FORMAT]"""
import sys
from uasset_read.core import parse_single

if len(sys.argv) < 2:
    print("用法: python diag.py <path.uasset> [--format FORMAT]")
    sys.exit(1)

path = sys.argv[1]
fmt = "text"
if len(sys.argv) >= 4 and sys.argv[2] == "--format":
    fmt = sys.argv[3]

try:
    print(parse_single(path, format=fmt))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 2: 创建 simple.py**

```python
# src/uasset_read/simple.py
"""快速诊断脚本：python -m uasset_read.simple <path.uasset>"""
import sys
from uasset_read.core import parse_single

if len(sys.argv) < 2:
    print("用法: python -m uasset_read.simple <path.uasset> [--format FORMAT]")
    sys.exit(1)

path = sys.argv[1]
fmt = "text"
if len(sys.argv) >= 4 and sys.argv[2] == "--format":
    fmt = sys.argv[3]

try:
    print(parse_single(path, format=fmt))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 3: 测试 diag.py**

```bash
# 使用一个已知资产测试
python diag.py "E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Blueprints\BP_FirstPersonCharacter.uasset" --format json 2>&1 | head -20
```

Expected: 输出有效 JSON

- [ ] **Step 4: 测试 simple.py**

```bash
python -m uasset_read.simple "E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Blueprints\BP_FirstPersonCharacter.uasset" --format text 2>&1 | head -20
```

Expected: 输出 YAML 风格文本

- [ ] **Step 5: 提交**

```bash
git add diag.py src/uasset_read/simple.py
git commit -m "feat: 添加快捷诊断脚本 diag.py 和 simple.py
- python diag.py <path> 直接解析
- python -m uasset_read.simple <path> 模块入口"
```

---

## Task 9: 完整测试套件验证

- [ ] **Step 1: 运行所有单元测试**

Run: `python -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: 所有测试通过（xfail 除外）

- [ ] **Step 2: 运行集成测试**

Run: `python -m pytest tests/ -v -m integration --tb=short 2>&1 | tail -30`
Expected: 所有集成测试通过

- [ ] **Step 3: CLI 回归测试**

```bash
# JSON 输出
python -c "from uasset_read.core import parse_single; print(parse_single('test.uasset', format='json')[:100])"

# 列出格式
python -c "from uasset_read.core import list_formats; print(list_formats())"
```

- [ ] **Step 4: 提交最终状态**

```bash
git add -A
git commit -m "chore: IR 迁移完成 — 所有测试通过
- 旧 exporter/n2c/agent 已删除
- IR + renderers 架构替换
- CLI 委托 core.py
- diag.py/simple.py 快捷入口"
```

---

## 验证清单

完成所有 Task 后，验证以下内容：

1. **无 blueprint 顶层对象** — JSON 输出中不存在 `"blueprint"` 键
2. **GUID 统一** — 所有 Node/Pin GUID 为 32 位小写 hex
3. **无 output_version 字段** — JSON 输出中不存在 `"output_version"`
4. **6 个渲染器全部注册** — `list_formats()` 返回 json/text/markdown/blueprint_text/blueprint_ue_text/cpp_skeleton
5. **CLI 等价输出** — `--json` 输出关键字段与旧输出一致
6. **diag.py 可用** — `python diag.py <path>` 正确输出
7. **无 exporter/n2c/agent 引用** — 代码库中无残留 import
8. **测试 ≥ 200 单元 + ≥ 40 集成** — 通过率 100%（xfail 除外）

---

## 风险和回退

| 风险 | 影响 | 回退方案 |
|------|------|----------|
| IR 构建丢失字段 | 输出不完整 | 对比旧 JSON 输出逐一验证 |
| 渲染器格式变化 | CLI 输出不同 | 保留旧 JSON 关键结构等价 |
| 集成测试破坏 | 无法合并 | Task 9 全量验证 |
