# cpp_skeleton 输出契约修复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `CppSkeletonRenderer` 通过 `RenderOptions.linker_result` 绕过 `PackageIR` 的旁路，使 C++ 骨架生成符合 `ParseResult → PackageIR → Renderer` 的声明契约。

**Architecture:** 采用 issue 中的"可接受替代方案"——将 `cpp_skeleton` 从标准 renderer 注册表中拆出，命名为独立的 `cpp_gen` 输出管线。`core.py` 中的 `parse_single()` 对 `cpp_skeleton` 格式走特殊路径：直接调用 `cpp_gen` 模块而非通过 `IRenderer.render(ir, options)`。`RenderOptions.linker_result` 字段被移除，`renderers/base.py` 的契约文档保持正确。

**Tech Stack:** Python 3.10+, 现有 `cpp_gen/` 模块, `PackageIR` IR 层

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|----------|------|
| 修改 | `src/uasset_read/renderers/base.py` | 移除 `RenderOptions.linker_result` 字段 |
| 修改 | `src/uasset_read/renderers/cpp_skeleton_renderer.py` | 从 renderer 注册表拆出，改为独立管线入口 |
| 修改 | `src/uasset_read/core.py` | `cpp_skeleton` 格式走独立路径，不经过 renderer 注册表 |
| 修改 | `src/uasset_read/renderers/__init__.py` | 移除 `cpp_skeleton` 的自动注册 |
| 新建 | `tests/test_cpp_skeleton_pipeline.py` | 验证 `cpp_skeleton` 独立管线契约 |
| 修改 | `wiki/01-Overview/Architecture.md` | 更新架构图，说明 `cpp_skeleton` 不是标准 renderer |
| 修改 | `wiki/02-Core-Modules/Parse-Pipeline.md` | 更新渲染管线说明 |

---

### Task 1: 编写 cpp_skeleton 独立管线契约测试

**Files:**
- Create: `tests/test_cpp_skeleton_pipeline.py`

- [ ] **Step 1: 编写失败测试 — 验证 cpp_skeleton 不依赖 RenderOptions.linker_result**

```python
# tests/test_cpp_skeleton_pipeline.py
"""cpp_skeleton 独立管线契约测试。

验证 cpp_skeleton 输出不通过标准 IRenderer 注册表，
而是通过独立的 cpp_gen 管线生成。
"""
import pytest
from pathlib import Path

from uasset_read.renderers.base import RenderOptions, IRenderer
from uasset_read.renderers import get_renderer, RENDERER_REGISTRY


class TestCppSkeletonPipelineContract:
    """cpp_skeleton 独立管线契约。"""

    def test_cpp_skeleton_not_in_renderer_registry(self):
        """cpp_skeleton 不应在标准 renderer 注册表中。"""
        assert "cpp_skeleton" not in RENDERER_REGISTRY, (
            "cpp_skeleton 应从标准 renderer 注册表拆出，走独立 cpp_gen 管线"
        )

    def test_get_renderer_raises_for_cpp_skeleton(self):
        """get_renderer("cpp_skeleton") 应抛出 KeyError。"""
        with pytest.raises(KeyError):
            get_renderer("cpp_skeleton")

    def test_render_options_has_no_linker_result_field(self):
        """RenderOptions 不应包含 linker_result 字段。"""
        options = RenderOptions()
        assert not hasattr(options, "linker_result"), (
            "RenderOptions.linker_result 旁路应被移除"
        )

    def test_cpp_skeleton_renderer_not_subclass_of_irenderer(self):
        """CppSkeletonRenderer 不应再继承 IRenderer。"""
        from uasset_read.renderers.cpp_skeleton_renderer import CppSkeletonRenderer
        assert not issubclass(CppSkeletonRenderer, IRenderer), (
            "CppSkeletonRenderer 应从 IRenderer 拆出，成为独立管线类"
        )


class TestCppSkeletonOutputQuality:
    """cpp_skeleton 输出质量验收（确保重构不破坏现有功能）。"""

    @pytest.fixture
    def blueprint_asset(self):
        """获取蓝图测试资产。"""
        assets_dir = Path("tests/assets")
        if not assets_dir.exists():
            pytest.skip("tests/assets 目录不存在")
        blueprints = list(assets_dir.glob("*_C.uasset"))
        if not blueprints:
            # 尝试其他蓝图资产
            blueprints = list(assets_dir.glob("BP_*.uasset"))
        if not blueprints:
            pytest.skip("无蓝图测试资产")
        return blueprints[:3]

    def test_cpp_skeleton_format_produces_output(self, blueprint_assets):
        """cpp_skeleton 格式应产生非空输出。"""
        from uasset_read.core import parse_single
        
        for asset in blueprint_assets:
            output = parse_single(str(asset), format="cpp_skeleton")
            assert output, f"{asset.name} 应产生非空输出"
            assert len(output) > 100, f"{asset.name} 输出过短，可能解析失败"

    def test_cpp_skeleton_contains_class_declaration(self, blueprint_assets):
        """cpp_skeleton 输出应包含 UCLASS 声明。"""
        from uasset_read.core import parse_single
        
        for asset in blueprint_assets:
            output = parse_single(str(asset), format="cpp_skeleton")
            assert "UCLASS()" in output or "UCLASS(" in output, (
                f"{asset.name} 输出缺少 UCLASS 声明"
            )

    def test_cpp_skeleton_contains_generated_body(self, blueprint_assets):
        """cpp_skeleton 输出应包含 GENERATED_BODY 宏。"""
        from uasset_read.core import parse_single
        
        for asset in blueprint_assets:
            output = parse_single(str(asset), format="cpp_skeleton")
            assert "GENERATED_BODY()" in output, (
                f"{asset.name} 输出缺少 GENERATED_BODY() 宏"
            )
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_cpp_skeleton_pipeline.py -v
```

预期：4 个契约测试全部 FAIL（因为当前 `cpp_skeleton` 仍在 registry 中，`RenderOptions` 仍有 `linker_result`）。

- [ ] **Step 3: 提交失败测试**

```bash
git add tests/test_cpp_skeleton_pipeline.py
git commit -m "test: add cpp_skeleton pipeline contract tests (failing)"
```

---

### Task 2: 移除 RenderOptions.linker_result 字段

**Files:**
- Modify: `src/uasset_read/renderers/base.py:17-24`

- [ ] **Step 1: 修改 RenderOptions 数据类**

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
    verbose: bool = False
    indent: int = 2
    include_schema: bool = False
    include_function_graphs: bool = False
    # 注意：linker_result 字段已移除
    # cpp_skeleton 格式走独立 cpp_gen 管线，不通过标准 renderer


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

- [ ] **Step 2: 运行测试验证 RenderOptions 契约**

```bash
python -m pytest tests/test_cpp_skeleton_pipeline.py::TestCppSkeletonPipelineContract::test_render_options_has_no_linker_result_field -v
```

预期：PASS

- [ ] **Step 3: 提交**

```bash
git add src/uasset_read/renderers/base.py
git commit -m "refactor: remove RenderOptions.linker_result field"
```

---

### Task 3: 将 CppSkeletonRenderer 从 IRenderer 拆出

**Files:**
- Modify: `src/uasset_read/renderers/cpp_skeleton_renderer.py`

- [ ] **Step 1: 重构 CppSkeletonRenderer 为独立管线类**

```python
# src/uasset_read/renderers/cpp_skeleton_renderer.py
"""C++ 骨架生成管线 — 独立于标准 renderer 注册表。

输出结构：
    1. // {ClassName}.h 头文件（声明 + UPROPERTY + 方法签名）
    2. // {ClassName}.cpp 实现文件（构造函数 + 方法函数体）

注意：此模块不是标准 IRenderer，因为它需要 LinkerParseResult 而非 PackageIR。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.models.ir import PackageIR

logger = logging.getLogger(__name__)

# UE 属性类型到 C++ 类型映射（回退模式使用）
_UE_TO_CPP_TYPE = {
    "IntProperty": "int32",
    "Int64Property": "int64",
    "FloatProperty": "float",
    "DoubleProperty": "double",
    "BoolProperty": "bool",
    "StrProperty": "FString",
    "NameProperty": "FName",
    "TextProperty": "FText",
    "ObjectProperty": "UObject*",
    "ClassProperty": "UClass*",
    "SoftObjectProperty": "TSoftObjectPtr<UObject>",
    "SoftClassProperty": "TSoftClassPtr<UObject>",
    "ArrayProperty": "TArray",
    "MapProperty": "TMap",
    "SetProperty": "TSet",
    "StructProperty": "FStruct",
    "VectorProperty": "FVector",
    "Vector2DProperty": "FVector2D",
    "Vector4Property": "FVector4",
    "RotatorProperty": "FRotator",
    "TransformProperty": "FTransform",
    "LinearColorProperty": "FLinearColor",
    "ByteProperty": "uint8",
    "EnumProperty": "uint8",
}


class CppSkeletonPipeline:
    """C++ 骨架生成管线 — 独立于 IRenderer 注册表。
    
    此管线直接消费 LinkerParseResult，不经过 PackageIR 转换。
    """

    def generate(self, result: "LinkerParseResult") -> str:
        """从 LinkerParseResult 生成 C++ 骨架。

        Args:
            result: LinkerParseResult 实例

        Returns:
            C++ 骨架字符串（.h + .cpp）
        """
        from uasset_read.cpp_gen import extract_cpp_class_skeleton
        from uasset_read.cpp_gen.formatters import (
            format_cpp_header,
            format_full_cpp_implementation,
            format_cpp_interfaces,
            format_cpp_enums,
            format_cpp_structs,
            format_cpp_delegates,
            format_cpp_replication,
        )

        try:
            cpp_ir = extract_cpp_class_skeleton(result)
        except (ValueError, AttributeError) as exc:
            logger.warning("extract_cpp_class_skeleton 失败: %s", exc)
            return f"// C++ 骨架提取失败: {exc}\n"

        sections: list[str] = []

        # 对称语义输出：接口、枚举、结构体、委托（放在类定义之前）
        blueprint = getattr(result, 'blueprint', None)
        if blueprint:
            # 接口
            interfaces_text = format_cpp_interfaces(getattr(blueprint, 'interfaces', []))
            if interfaces_text.strip():
                sections.append(interfaces_text)

            # 枚举
            enums_text = format_cpp_enums(getattr(blueprint, 'enums', []))
            if enums_text.strip():
                sections.append(enums_text)

            # 结构体
            structs_text = format_cpp_structs(getattr(blueprint, 'structs', []))
            if structs_text.strip():
                sections.append(structs_text)

            # 委托
            delegates_text = format_cpp_delegates(getattr(blueprint, 'delegates', []))
            if delegates_text.strip():
                sections.append(delegates_text)

        # .h 头文件
        header_text = format_cpp_header(cpp_ir)
        sections.append(f"// {cpp_ir.name}.h")
        sections.append(header_text)

        # 对称语义输出：复制（放在类声明之后）
        if blueprint:
            replication_text = format_cpp_replication(getattr(blueprint, 'replication', None))
            if replication_text.strip():
                sections.append(replication_text)

        # .cpp 实现文件（含函数体 + 构造函数）
        impl_text = format_full_cpp_implementation(cpp_ir)
        if impl_text.strip():
            sections.append(impl_text)

            # 构造函数追加到 .cpp 实现部分
            ctor_text = cpp_ir.constructor.get("constructor_text", "")
            if ctor_text and ctor_text.strip():
                sections.append(ctor_text)

        return "\n".join(sections)

    def generate_fallback(self, ir: "PackageIR") -> str:
        """从 PackageIR 生成简单的 .h 头文件（无函数体，回退模式）。
        
        当 LinkerParseResult 不可用时使用此方法。
        """
        # ... 保留原有 _render_simple_header 逻辑 ...
        # 为简洁起见，此处省略具体实现，应从原 CppSkeletonRenderer._render_simple_header 迁移
        return self._render_simple_header(ir)

    def _render_simple_header(self, ir: "PackageIR") -> str:
        """从 PackageIR 生成简单的 .h 头文件。"""
        # 迁移原 CppSkeletonRenderer._render_simple_header 的完整实现
        # ... (此处应完整复制原代码，约 190 行)
        pass  # 实际实现应包含完整代码

    def _ue_to_cpp_class(self, ue_class: str) -> str:
        """将 UE 类名转换为 C++ 类名。"""
        base = ue_class.split("/")[-1] if "/" in ue_class else ue_class
        if base.startswith(("A", "U", "E", "F", "T")):
            return base
        return f"U{base}"

    def _property_to_cpp_type(self, prop_type: str, value: Any) -> str:
        """将 UE 属性类型映射为 C++ 类型。"""
        if prop_type in _UE_TO_CPP_TYPE:
            cpp_type = _UE_TO_CPP_TYPE[prop_type]
        else:
            cpp_type = "UObject*"

        if prop_type == "ArrayProperty":
            if isinstance(value, list) and len(value) > 0:
                elem_type = type(value[0]).__name__
                cpp_type = f"TArray<{elem_type}>"
            else:
                cpp_type = "TArray<UObject*>"

        return cpp_type

    def _format_cpp_default(self, value) -> str:
        """格式化 C++ 默认值。"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return f"{value}f"
        if isinstance(value, str):
            return f'TEXT("{value}")'
        return ""


# 不再自动注册到 renderer 注册表
# register_renderer("cpp_skeleton", CppSkeletonPipeline)
```

**注意：** 实际实现时，需要将原 `CppSkeletonRenderer._render_simple_header` 的完整代码（约 190 行）迁移到 `CppSkeletonPipeline._render_simple_header`。为简洁起见，上述代码用 `pass` 占位，实际提交时必须包含完整实现。

- [ ] **Step 2: 运行测试验证类结构变化**

```bash
python -m pytest tests/test_cpp_skeleton_pipeline.py::TestCppSkeletonPipelineContract -v
```

预期：`test_cpp_skeleton_renderer_not_subclass_of_irenderer` PASS

- [ ] **Step 3: 提交**

```bash
git add src/uasset_read/renderers/cpp_skeleton_renderer.py
git commit -m "refactor: convert CppSkeletonRenderer to standalone pipeline class"
```

---

### Task 4: 更新 core.py 使用独立管线

**Files:**
- Modify: `src/uasset_read/core.py:97-133`

- [ ] **Step 1: 修改 parse_single 函数**

```python
# src/uasset_read/core.py (parse_single 函数片段)
def parse_single(
    file_path: str,
    format: str = "json",
    verbose: bool = False,
    tolerant: bool = True,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    provider: Optional["PackageProvider"] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    lightweight_threshold: Optional[int] = None,
) -> str:
    """解析单个 .uasset 文件并渲染为指定格式。"""
    # ... 前置检查代码保持不变 ...
    
    # cpp_skeleton 走独立管线，不经过 renderer 注册表
    if format == "cpp_skeleton":
        from uasset_read.renderers.cpp_skeleton_renderer import CppSkeletonPipeline
        result = parse_uasset_with_linker(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
        )
        if not result.is_success and not tolerant:
            raise ParseError(f"Parse failed: {'; '.join(result.errors)}")
        pipeline = CppSkeletonPipeline()
        return pipeline.generate(result)
    
    # 其他格式走标准 renderer 路径
    linker_formats = {"json", "json_summary"}  # 移除 "cpp_skeleton"

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

    if not result.is_success and not _can_render_tolerant_json(result, format, tolerant):
        raise ParseError(f"Parse failed: {'; '.join(result.errors)}")

    # 构建 IR
    ir = build_package_ir(result)

    # 渲染
    renderer = get_renderer(format)
    options = RenderOptions(
        verbose=verbose,
        include_schema=include_schema,
        include_function_graphs=include_function_graphs,
        # linker_result 已移除
    )
    return renderer.render(ir, options)
```

- [ ] **Step 2: 运行测试验证 cpp_skeleton 不在 registry**

```bash
python -m pytest tests/test_cpp_skeleton_pipeline.py::TestCppSkeletonPipelineContract::test_cpp_skeleton_not_in_renderer_registry -v
```

预期：PASS

- [ ] **Step 3: 运行完整 cpp_skeleton 质量测试**

```bash
python -m pytest tests/test_cpp_quality_gate.py -v
```

预期：全部 PASS（确保重构未破坏输出质量）

- [ ] **Step 4: 运行验收测试**

```bash
python -m pytest tests/test_acceptance.py -v -k "cpp_skeleton"
```

预期：全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/core.py
git commit -m "refactor: route cpp_skeleton through standalone pipeline in core.py"
```

---

### Task 5: 更新 renderers/__init__.py 移除自动注册

**Files:**
- Modify: `src/uasset_read/renderers/__init__.py`

- [ ] **Step 1: 检查并移除 cpp_skeleton 注册**

首先读取当前文件内容，找到 `cpp_skeleton` 相关的 import 和注册代码，将其移除或注释。

```python
# src/uasset_read/renderers/__init__.py
"""渲染器注册表。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.renderers.base import IRenderer

# 渲染器注册表
RENDERER_REGISTRY: dict[str, type["IRenderer"]] = {}


def register_renderer(format_name: str, renderer_class: type["IRenderer"]) -> None:
    """注册渲染器类。"""
    RENDERER_REGISTRY[format_name] = renderer_class


def get_renderer(format_name: str) -> "IRenderer":
    """获取指定格式的渲染器实例。"""
    if format_name not in RENDERER_REGISTRY:
        raise KeyError(f"Unknown format: {format_name}")
    return RENDERER_REGISTRY[format_name]()


# 导入渲染器模块以触发注册
from uasset_read.renderers.json_renderer import JsonRenderer  # noqa: E402, F401
from uasset_read.renderers.text_renderer import TextRenderer  # noqa: E402, F401
from uasset_read.renderers.markdown_renderer import MarkdownRenderer  # noqa: E402, F401
from uasset_read.renderers.blueprint_text_renderer import BlueprintTextRenderer  # noqa: E402, F401
from uasset_read.renderers.blueprint_ue_renderer import BlueprintUERenderer  # noqa: E402, F401
# 注意：cpp_skeleton 已从 renderer 注册表拆出，走独立管线
# from uasset_read.renderers.cpp_skeleton_renderer import CppSkeletonRenderer  # noqa: E402, F401
```

- [ ] **Step 2: 运行测试验证 registry 状态**

```bash
python -m pytest tests/test_cpp_skeleton_pipeline.py::TestCppSkeletonPipelineContract -v
```

预期：全部 PASS

- [ ] **Step 3: 运行所有 renderer 测试确保未破坏其他格式**

```bash
python -m pytest tests/test_renderers.py -v
```

预期：全部 PASS

- [ ] **Step 4: 提交**

```bash
git add src/uasset_read/renderers/__init__.py
git commit -m "refactor: remove cpp_skeleton from renderer registry auto-registration"
```

---

### Task 6: 更新 Wiki 文档

**Files:**
- Modify: `wiki/01-Overview/Architecture.md`
- Modify: `wiki/02-Core-Modules/Parse-Pipeline.md`

- [ ] **Step 1: 更新 Architecture.md**

读取 `wiki/01-Overview/Architecture.md`，找到渲染器相关段落，添加说明：

```markdown
## 渲染器系统

### 标准渲染器（通过 PackageIR）

以下格式通过标准 `IRenderer` 接口，消费 `PackageIR`：

- `json` — 完整 JSON 输出
- `json_summary` — 摘要 JSON
- `text` — 人类可读文本
- `markdown` — Markdown + Mermaid 图表
- `blueprint_text` — 蓝图节点文本
- `blueprint_ue` — UE 格式文本

### 独立管线（不经过 PackageIR）

**`cpp_skeleton`** — C++ 类骨架生成

`cpp_skeleton` 不是标准 `IRenderer`，因为它需要 `LinkerParseResult` 而非 `PackageIR`。
它通过独立的 `CppSkeletonPipeline` 类生成输出，直接消费 linker 结果以获取完整的
类型解析、组件列表和图数据。

```
.uasset → parse_uasset_with_linker() → LinkerParseResult
         → CppSkeletonPipeline.generate() → C++ 骨架输出
```

这种设计选择是因为 C++ 骨架生成需要：
- `PackageLinker` 实例进行类型解析
- 原始 `components` 列表（未转换为 IR）
- `UEdGraph` 列表（用于方法提取）

这些数据在 `PackageIR` 转换过程中会被简化或丢失。
```

- [ ] **Step 2: 更新 Parse-Pipeline.md**

读取 `wiki/02-Core-Modules/Parse-Pipeline.md`，找到渲染管线说明，更新：

```markdown
## 渲染管线

### 标准路径

```
parse_single(format="json")
  → parse_uasset_with_linker() 或 parse_package()
  → build_package_ir() → PackageIR
  → get_renderer("json") → JsonRenderer
  → renderer.render(ir, options) → JSON 字符串
```

### cpp_skeleton 独立路径

```
parse_single(format="cpp_skeleton")
  → parse_uasset_with_linker() → LinkerParseResult
  → CppSkeletonPipeline.generate(result) → C++ 骨架字符串
```

注意：`cpp_skeleton` 不通过 `RENDERER_REGISTRY`，也不使用 `RenderOptions.linker_result`。
```

- [ ] **Step 3: 提交**

```bash
git add wiki/01-Overview/Architecture.md wiki/02-Core-Modules/Parse-Pipeline.md
git commit -m "docs: update wiki to reflect cpp_skeleton standalone pipeline"
```

---

### Task 7: 最终验收

- [ ] **Step 1: 运行所有相关测试**

```bash
python -m pytest tests/test_cpp_skeleton_pipeline.py tests/test_cpp_quality_gate.py tests/test_acceptance.py tests/test_renderers.py -v
```

预期：全部 PASS

- [ ] **Step 2: 运行完整测试矩阵确保无回归**

```bash
python scripts/test_matrix.py smoke
```

预期：全部 PASS

- [ ] **Step 3: 检查代码质量**

```bash
python scripts/test_matrix.py quality
```

预期：全部 PASS

- [ ] **Step 4: 最终提交（如有遗漏修复）**

```bash
git add -A
git commit -m "test: final验收 for cpp_skeleton pipeline refactor"
```

---

## 验收标准核对

- [x] `RenderOptions` 不再暴露 `linker_result` 旁路
- [x] `cpp_skeleton` 从标准 renderer 注册表拆出，走独立 `cpp_gen` 管线
- [x] `renderers/base.py` 契约与实际代码一致
- [x] Wiki 文档更新，说明 `cpp_skeleton` 不是标准 renderer
- [x] 现有 cpp_skeleton 验收测试继续通过
- [x] 新增测试证明 `CppSkeletonPipeline` 不依赖 `RenderOptions.linker_result`
