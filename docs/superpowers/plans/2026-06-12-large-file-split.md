# 大文件拆分重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 src/ 下 6 个超千行文件拆分为职责清晰的小模块，降低单文件体量，提升可维护性。

**Architecture:** 纯结构性重构——只移动代码、调整导入路径，不改变任何业务逻辑。每个 Task 拆分一个文件，拆分后运行全量测试确保零回归。导入路径变更通过 `__init__.py` 重新导出保持向后兼容。

**Tech Stack:** Python 3.10+, pytest

---

## 拆分目标总览

| 原文件 | 行数 | 拆分后 | 预估最大单文件 |
|--------|------|--------|---------------|
| `variable_extractor.py` | 1,048 | 3 个模块 | ~450 |
| `extract_cpp_skeleton.py` | 1,353 | 4 个模块 | ~400 |
| `ir_builder.py` | 1,000 | 子包 5 模块 | ~250 |
| `package_summary.py` | 1,087 | 3 个模块 | ~450 |
| `translator.py` | 1,158 | 2 个模块 | ~700 |
| `property_parser.py` | 1,010 | 2 个模块 | ~550 |

---

### Task 1: 拆分 `variable_extractor.py`（1,048 行 → 3 模块）

**分析：** `variable_extractor.py` 混合了三组不相关职责：
1. **变量提取**（核心）：`extract_blueprint_variables`、`extract_blueprint_metadata`、`read_blueprint_variable` 等
2. **FText 读取**：`read_ftext`、`_skip_ftext_args`、`_read_ftext_value` 等
3. **Transform/向量/旋转提取 + GUID 工具**：`parse_component_transform`、`_extract_vector`、`_extract_rotator`、`_format_guid_bytes` 等

**Files:**
- Create: `src/uasset_read/blueprint/_ftext.py`
- Create: `src/uasset_read/blueprint/_transform_utils.py`
- Modify: `src/uasset_read/blueprint/variable_extractor.py`
- Modify: `src/uasset_read/blueprint/__init__.py`
- Test: `tests/`

- [ ] **Step 1: 创建 `_ftext.py` — 抽取 FText 读取函数**

从 `variable_extractor.py` 移出以下函数到 `src/uasset_read/blueprint/_ftext.py`：
- `_text_or_string(value)` (L404)
- `read_ftext(archive, summary=None)` (L410)
- `_skip_ftext_args(archive)` (L484)

`_ftext.py` 内容：

```python
"""FText 读取工具 — 从 variable_extractor.py 抽取。"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary


def _text_or_string(value: Any) -> str:
    """Convert value to string, preferring text representation."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def read_ftext(archive: "FArchive", summary: "PackageFileSummary | None" = None) -> str:
    """从 FArchive 读取 FText 值。

    [原 variable_extractor.py L410-L482 完整搬入，逻辑不变]
    """
    # ... 完整搬入 read_ftext 函数体 ...

def _skip_ftext_args(archive: "FArchive") -> None:
    """跳过 FText 的变长参数段。

    [原 variable_extractor.py L484-L491 完整搬入]
    """
    # ... 完整搬入 _skip_ftext_args 函数体 ...
```

- [ ] **Step 2: 创建 `_transform_utils.py` — 抽取 Transform/向量/GUID 工具**

从 `variable_extractor.py` 移出以下函数到 `src/uasset_read/blueprint/_transform_utils.py`：
- `parse_component_transform(properties)` (L514)
- `_extract_vector(value)` (L550)
- `_extract_rotator(value)` (L569)
- `_extract_mobility(value)` (L588)
- `_extract_guid(value)` (L478, 从 variable_extractor 搬入)
- `_format_guid_bytes(data)` (L394)
- `_read_guid(archive)` (L1040)

`_transform_utils.py` 内容框架同上，完整搬入函数体。

- [ ] **Step 3: 更新 `variable_extractor.py` — 替换为导入**

在 `variable_extractor.py` 顶部添加：
```python
from uasset_read.blueprint._ftext import read_ftext, _skip_ftext_args, _text_or_string
from uasset_read.blueprint._transform_utils import (
    parse_component_transform, _extract_vector, _extract_rotator,
    _extract_mobility, _extract_guid, _format_guid_bytes, _read_guid,
)
```

删除已搬出的函数定义（保留所有变量提取核心函数）。

- [ ] **Step 4: 更新 `blueprint/__init__.py` — 确保重新导出不变**

检查 `blueprint/__init__.py` 的 `from uasset_read.blueprint.variable_extractor import ...` 是否仍能解析。由于函数仍在 `variable_extractor.py` 中（通过 re-import），**不需要修改**。

但如果有外部代码直接 `from uasset_read.blueprint.variable_extractor import read_ftext`，需在 `__init__.py` 补充从 `_ftext` 的导出。

- [ ] **Step 5: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

预期：全部通过，无导入错误。

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/blueprint/_ftext.py src/uasset_read/blueprint/_transform_utils.py src/uasset_read/blueprint/variable_extractor.py src/uasset_read/blueprint/__init__.py
git commit -m "refactor: 拆分 variable_extractor.py — FText 和 Transform 工具独立模块"
```

---

### Task 2: 拆分 `extract_cpp_skeleton.py`（1,353 行 → 4 模块）

**分析：** `extract_cpp_skeleton.py` 有 25 个模块级函数，职责混杂：
1. **类名/父类提取**：`_extract_class_name`、`_resolve_parent_class`、`_simplify_class_name`
2. **属性提取**：`_extract_component_properties`、`_create_component_property`、`_extract_variable_properties`、`_create_variable_property`、`_extract_input_action_properties`、`_build_ue_type_from_pin_type`、`_extract_cpp_type_from_pin`
3. **方法提取**：`_build_cpp_method_from_entry`、`_build_cpp_method_from_event`、`_extractFunctionFlags`、`_infer_ufunction_specifiers`、`_extract_parameters_from_pins`
4. **Pin 追踪 + 补齐 + 工具**：`_trace_pin_to_function_entry`、`_find_pins_connected_to`、`_inject_function_bodies`、`_backfill_missing_methods`、`_is_blueprint_metadata`、`_clean_component_name`、`_sanitize_identifier`、`_build_param_name_map`、`_build_decompiled_to_param_map`

**Files:**
- Create: `src/uasset_read/cpp_gen/_class_extractor.py`
- Create: `src/uasset_read/cpp_gen/_property_extractor.py`
- Create: `src/uasset_read/cpp_gen/_method_extractor.py`
- Modify: `src/uasset_read/cpp_gen/extract_cpp_skeleton.py`
- Test: `tests/`

- [ ] **Step 1: 创建 `_class_extractor.py`**

从 `extract_cpp_skeleton.py` 移出：
- `_extract_class_name(result)` (L575)
- `_resolve_parent_class(result)` (L615)
- `_simplify_class_name(raw_name)` (L268)
- `_is_blueprint_metadata(prop_name)` (L220)
- `_clean_component_name(name)` (L244)

文件头包含必要的 import（CppTypeMapper, CppHeaderMeta 等 TYPE_CHECKING 导入）。

- [ ] **Step 2: 创建 `_property_extractor.py`**

从 `extract_cpp_skeleton.py` 移出：
- `_extract_component_properties(result)` (L639)
- `_create_component_property(var)` (L698)
- `_extract_variable_properties(blueprint)` (L744)
- `_extract_input_action_properties(graphs)` (L769)
- `_create_variable_property(var)` (L822)
- `_build_ue_type_from_pin_type(pin_type)` (L852)

- [ ] **Step 3: 创建 `_method_extractor.py`**

从 `extract_cpp_skeleton.py` 移出：
- `_build_cpp_method_from_entry(...)` (L1105)
- `_build_cpp_method_from_event(event_node)` (L1181)
- `_extractFunctionFlags(flags)` (L1041)
- `_infer_ufunction_specifiers(...)` (L1069)
- `_extract_parameters_from_pins(...)` (L979)
- `_trace_pin_to_function_entry(...)` (L406)
- `_find_pins_connected_to(...)` (L488)
- `_inject_function_bodies(...)` (L528)
- `_backfill_missing_methods(...)` (L63)
- `_build_param_name_map(...)` (L303)
- `_build_decompiled_to_param_map(...)` (L334)

- [ ] **Step 4: 更新 `extract_cpp_skeleton.py` — 只保留 `extract_cpp_class_skeleton` 和 `_sanitize_identifier`**

```python
"""C++ 类骨架提取 — 主入口函数。"""
from uasset_read.cpp_gen._class_extractor import (
    _extract_class_name, _resolve_parent_class, _simplify_class_name,
    _is_blueprint_metadata, _clean_component_name,
)
from uasset_read.cpp_gen._property_extractor import (
    _extract_component_properties, _extract_variable_properties,
    _extract_input_action_properties,
)
from uasset_read.cpp_gen._method_extractor import (
    _build_cpp_method_from_entry, _build_cpp_method_from_event,
    _backfill_missing_methods, _inject_function_bodies,
)

# _sanitize_identifier 保留在此文件，因为 cpp_gen/sanitizer.py 已有同名模块
# 实际上 _sanitize_identifier 在第 927 行，而 cpp_gen/sanitizer.py 也有 sanitize_identifier
# 合并到 sanitizer.py，从 extract_cpp_skeleton.py 删除
```

注意：`_sanitize_identifier`（L927）与 `cpp_gen/sanitizer.py` 中的 `sanitize_identifier` 功能重复。检查是否为同一函数。如果是，直接使用 sanitizer 的版本；如果不是，在 sanitizer.py 中添加此变体。

- [ ] **Step 5: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/cpp_gen/
git commit -m "refactor: 拆分 extract_cpp_skeleton.py — 类/属性/方法提取独立模块"
```

---

### Task 3: 拆分 `ir_builder.py`（1,000 行 → 子包 5 模块）

**分析：** `ir_builder.py` 有 20+ 个 `build_xxx_ir` 函数，按数据域自然分组：
1. **header + imports + utils**：`build_package_ir`、`_build_header`、`_get_version_string`、`_build_imports`、`_result_status`、`_safe_str`、`_safe_int`、`_normalize_guid`
2. **exports**：`_build_exports`、`_build_export_ir`、`_build_export_raw_ir`、`_build_export_diagnostics`、`_build_property_ir`、`_resolve_package_index`、`_build_resolved_depends_map`
3. **graphs + pins + nodes**：`_build_graph_ir`、`_build_node_ir`、`_build_pin_ir`、`_build_function_graphs_safe`、`_build_function_graph_summaries`
4. **blueprint + decompiled**：`_build_blueprint_ir`、`_build_decompiled_functions_ir`、`_extract_return_type`、`_extract_parameters_from_signature`、`_extract_parameters`、`_build_execution_chains_ir`、`_build_variables_ir`、`_format_var_type`、`_bind_implementations`、`_bind_single_implementation`、`_classify_variable`
5. **linker**：`_build_linker`

**Files:**
- Create: `src/uasset_read/ir_builder/__init__.py`
- Create: `src/uasset_read/ir_builder/_exports.py`
- Create: `src/uasset_read/ir_builder/_graphs.py`
- Create: `src/uasset_read/ir_builder/_blueprint.py`
- Create: `src/uasset_read/ir_builder/_linker.py`
- Modify: `src/uasset_read/ir_builder.py` → 删除，替换为 `ir_builder/` 目录
- Test: `tests/`

- [ ] **Step 1: 创建 `ir_builder/` 目录结构**

```bash
mkdir src/uasset_read/ir_builder
```

- [ ] **Step 2: 创建 `ir_builder/__init__.py` — 主入口 + 公共工具**

`__init__.py` 包含：
- `build_package_ir()` 主函数（从原 ir_builder.py 搬入）
- `_build_header`、`_get_version_string`、`_build_imports`
- `_result_status`、`_safe_str`、`_safe_int`、`_normalize_guid`、`_extract_pin_guid`
- `_build_function_graphs_safe`、`_build_function_graph_summaries`
- 从子模块的导入（用于 build_package_ir 内部调用）

```python
"""IR 构建层 — 将 ParseResult 转换为 PackageIR。"""
from uasset_read.ir_builder._exports import (
    _build_exports, _build_export_ir, _build_export_raw_ir,
    _build_export_diagnostics, _build_property_ir,
    _resolve_package_index, _build_resolved_depends_map,
)
from uasset_read.ir_builder._graphs import (
    _build_graph_ir, _build_node_ir, _build_pin_ir,
)
from uasset_read.ir_builder._blueprint import (
    _build_blueprint_ir, _build_decompiled_functions_ir,
    _build_execution_chains_ir, _build_variables_ir,
    _bind_implementations,
)
from uasset_read.ir_builder._linker import _build_linker

# build_package_ir 主函数定义（从原文件搬入，逻辑不变）
def build_package_ir(result):
    ...
```

- [ ] **Step 3: 创建 `_exports.py`**

从原文件搬入：`_build_exports`、`_build_export_ir`、`_build_export_raw_ir`、`_build_export_diagnostics`、`_build_property_ir`、`_resolve_package_index`、`_build_resolved_depends_map`

需从 `__init__` 导入 `_safe_str`、`_safe_int`、`_normalize_guid`（或放入共享 `_utils.py`）。

- [ ] **Step 4: 创建 `_graphs.py`**

从原文件搬入：`_build_graph_ir`、`_build_node_ir`、`_build_pin_ir`

- [ ] **Step 5: 创建 `_blueprint.py`**

从原文件搬入：`_build_blueprint_ir`、`_build_decompiled_functions_ir`、`_extract_return_type`、`_extract_parameters_from_signature`、`_extract_parameters`、`_build_execution_chains_ir`、`_build_variables_ir`、`_format_var_type`、`_classify_variable`、`_bind_implementations`、`_bind_single_implementation`、`_EVENT_ALIASES`、`_get_event_name_from_node`、`_trace_execution_from_node`、`_find_next_exec_node`、`_find_node_by_pin_id`

- [ ] **Step 6: 创建 `_linker.py`**

从原文件搬入：`_build_linker`

- [ ] **Step 7: 删除原 `ir_builder.py`，确保导入路径不变**

原 `core.py` 中 `from uasset_read.ir_builder import build_package_ir` — 由于 `ir_builder/` 是包，`__init__.py` 暴露 `build_package_ir`，导入路径不变。

```bash
rm src/uasset_read/ir_builder.py
```

- [ ] **Step 8: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 9: 提交**

```bash
git add src/uasset_read/ir_builder/
git rm src/uasset_read/ir_builder.py
git commit -m "refactor: 拆分 ir_builder.py 为子包（exports/graphs/blueprint/linker）"
```

---

### Task 4: 拆分 `package_summary.py`（1,087 行 → 3 模块）

**分析：** `package_summary.py` 混合了数据类定义、UE4 读取、UE5 读取、辅助函数：
1. **数据类**：`GenerationInfo`、`EngineVersion`、`CustomVersion`、`PackageFileSummary`（~100 行）
2. **UE4 读取**：`_read_package_summary_ue4`、`_read_custom_versions_ue4`（~310 行）
3. **UE5 读取 + 公共入口**：`read_package_summary`、`_is_ue4_legacy`、`_read_package_summary_ue5` + 辅助函数（`validate_export_data_range`、`read_name_table`、`read_depends_map`、`read_soft_package_references`、`read_preload_dependencies`）（~670 行）

**Files:**
- Create: `src/uasset_read/serializers/summary_types.py`
- Create: `src/uasset_read/serializers/_summary_ue4.py`
- Modify: `src/uasset_read/serializers/package_summary.py`
- Modify: `src/uasset_read/serializers/__init__.py`
- Test: `tests/`

- [ ] **Step 1: 创建 `summary_types.py` — 数据类独立**

从 `package_summary.py` 移出：
- `GenerationInfo` (L43)
- `EngineVersion` (L50)
- `CustomVersion` (L60)
- `PackageFileSummary` (L67-L145)

```python
"""Package Summary 数据类型定义。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class GenerationInfo:
    """FGenerationInfo 版本世代信息。"""
    export_count: int = 0
    name_count: int = 0


@dataclass
class EngineVersion:
    """FEngineVersion 引擎版本信息。"""
    major: int = 0
    minor: int = 0
    patch: int = 0
    changelist: int = 0
    branch: str = ""


@dataclass
class CustomVersion:
    """自定义版本（GUID + 版本号）。"""
    guid: str
    version: int


@dataclass
class PackageFileSummary:
    # ... 完整搬入所有字段 ...
```

- [ ] **Step 2: 创建 `_summary_ue4.py` — UE4 读取逻辑**

从 `package_summary.py` 移出：
- `_read_custom_versions_ue4(archive, legacy_file_version)` (L491)
- `_read_package_summary_ue4(archive, tag, legacy_file_version)` (L221)

```python
"""UE4 格式 PackageFileSummary 读取。"""
from __future__ import annotations
import logging
from uasset_read.archive import FArchive
from uasset_read.serializers.summary_types import (
    GenerationInfo, EngineVersion, CustomVersion, PackageFileSummary,
)
# ... 其他 import ...
```

- [ ] **Step 3: 更新 `package_summary.py` — 只保留 UE5 读取 + 公共接口**

```python
"""Package Summary 序列化 — UE5 主路径 + 公共入口。"""
from uasset_read.serializers.summary_types import (
    GenerationInfo, EngineVersion, CustomVersion, PackageFileSummary,
)
from uasset_read.serializers._summary_ue4 import (
    _read_package_summary_ue4, _read_custom_versions_ue4,
)

# 保留: read_package_summary, _is_ue4_legacy, _read_package_summary_ue5,
#       validate_export_data_range, read_name_table, read_depends_map,
#       read_soft_package_references, read_preload_dependencies
```

- [ ] **Step 4: 更新 `serializers/__init__.py` — 重新导出数据类**

`serializers/__init__.py` 目前从 `package_summary` 导入数据类。需确认导入路径仍有效（因为 `package_summary.py` 会 re-export）。

如果 `__init__.py` 有 `from uasset_read.serializers.package_summary import GenerationInfo, EngineVersion, ...`，由于 `package_summary.py` 现在从 `summary_types` re-import，**路径不变**。

- [ ] **Step 5: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/serializers/
git commit -m "refactor: 拆分 package_summary.py — 数据类型和 UE4 读取独立模块"
```

---

### Task 5: 拆分 `translator.py`（1,158 行 → 2 模块）

**分析：** `translator.py` 包含 3 个类：
- `TypeRegistry`（L62-L80, ~20 行）— 小型类型注册表
- `MathFunctionCleaner`（L85-L518, ~434 行）— 纯映射表，大量 if-elif 分支
- `KismetTranslator`（L519-L1140, ~620 行）— 核心翻译器

`MathFunctionCleaner` 占 37%，且全部是静态映射逻辑，与核心翻译器职责不同。

**Files:**
- Create: `src/uasset_read/kismet/math_cleaner.py`
- Modify: `src/uasset_read/kismet/translator.py`
- Modify: `src/uasset_read/kismet/__init__.py`
- Test: `tests/`

- [ ] **Step 1: 创建 `math_cleaner.py`**

从 `translator.py` 移出 `MathFunctionCleaner` 类（L85-L518），以及模块级常量 `_UE_TO_CPP_TYPES`（如果 `TypeRegistry` 不用的话则保留在 translator.py）。

```python
"""Kismet 数学函数清理器 — 将 UKismetMathLibrary 等调用美化为人可读的 C++ 表达式。"""
from __future__ import annotations


class MathFunctionCleaner:
    """
    Static cleaner that transforms Kismet library function calls
    into idiomatic C++ operators and expressions.

    [完整搬入 MathFunctionCleaner 类，逻辑不变]
    """
    ...
```

- [ ] **Step 2: 更新 `translator.py` — 导入 MathFunctionCleaner**

```python
from uasset_read.kismet.math_cleaner import MathFunctionCleaner

# TypeRegistry 和 KismetTranslator 保留在此文件
```

- [ ] **Step 3: 更新 `kismet/__init__.py` — 确保导出不变**

当前 `__init__.py` 从 `translator` 导入 `TypeRegistry`、`KismetTranslator` 等。`MathFunctionCleaner` 如果也被导出，需补充：

```python
from uasset_read.kismet.math_cleaner import MathFunctionCleaner
```

- [ ] **Step 4: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/kismet/
git commit -m "refactor: 拆分 translator.py — MathFunctionCleaner 独立模块"
```

---

### Task 6: 拆分 `property_parser.py`（1,010 行 → 2 模块）

**分析：** `property_parser.py` 的核心逻辑围绕 `ExportPayloadContext` 类（L312-L660）展开，包含策略分发和属性循环。后半段（L662-L1010）是 `parse_properties_from_export` 入口 + unversioned 相关辅助函数。

`ExportPayloadContext` 及其策略方法（~350 行）与主解析循环耦合松散——它只被 `parse_properties_from_export` 使用。

**Files:**
- Create: `src/uasset_read/parsers/_export_context.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Test: `tests/`

- [ ] **Step 1: 创建 `_export_context.py`**

从 `property_parser.py` 移出：
- `ExportPayloadContext` 类（L312-L660）
- `_apply_class_specific_skip` (L329)
- `_apply_uclass_native_strategy` (L354)
- `_apply_serialization_control_header` (L406)
- `_apply_unversioned_properties_strategy` (L432)
- `_apply_asset_type_handler` (L483)
- `_run_tagged_property_loop` (L489)

```python
"""导出条目解析上下文 — ExportPayloadContext 及其策略方法。"""
from __future__ import annotations
import logging
from dataclasses import dataclass

# ... import ...
from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


@dataclass
class ExportPayloadContext:
    """解析导出条目属性的上下文。"""
    # ... 完整搬入所有字段和方法 ...
```

- [ ] **Step 2: 更新 `property_parser.py` — 导入 ExportPayloadContext**

```python
from uasset_read.parsers._export_context import ExportPayloadContext
```

删除已搬出的类和方法定义。保留 `_build_tag_info`、`_get_parse_functions`、`_try_asset_type_handler`、`parse_property_value`、`parse_properties_from_export` 及 unversioned 辅助函数。

- [ ] **Step 3: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 4: 提交**

```bash
git add src/uasset_read/parsers/
git commit -m "refactor: 拆分 property_parser.py — ExportPayloadContext 独立模块"
```

---

## 自检清单

### 1. 规格覆盖
- ✅ 6 个 ≥1000 行文件全部覆盖
- ⬜ 700-999 行文件未纳入（`iostore/reader.py`、`object_resources.py`、`flow_builder.py`、`linker.py`、`structs.py`、`parse_uasset.py`）— 作为 Phase 2 后续处理
- ✅ 所有拆分均保持向后兼容（通过 re-import 或 `__init__.py` 重新导出）

### 2. 占位符扫描
- ⚠️ Task 1 Step 1/2 中的函数体标记了 `[原 xxx.py Lxxx-Lyyy 完整搬入]` — 实际执行时必须完整复制函数体，不可留占位符
- ⚠️ Task 3 Step 2 中 `build_package_ir` 标记了 `...` — 实际执行时必须完整复制
- ✅ 所有文件路径、导入路径均为精确路径

### 3. 类型一致性
- ✅ 所有函数签名保持不变（纯搬移，不改参数或返回值）
- ✅ 导入路径变更通过 re-import 对冲，外部代码无需修改
- ⚠️ Task 2 中 `_sanitize_identifier` 需确认与 `sanitizer.py:sanitize_identifier` 的关系

---

## 预期结果

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| ≥1000 行文件数 | 6 | 0 |
| 最大单文件行数 | 1,353 | ~700（translator.py 的 KismetTranslator） |
| 新增模块数 | — | 11 |
| 总代码行 | ~41,768 | ~41,768（纯重组） |
