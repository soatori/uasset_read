# Phase 29: 核心数据模型 - Research

**Researched:** 2026-05-11
**Domain:** Python dataclass design for UE blueprint core data models (UEdGraph, UEdGraphNode, UEdGraphPin, ParseResult)
**Confidence:** HIGH

## Summary

Phase 29 extracts core blueprint data models from `uasset_read.py` lines 1878-2074 into a new `src/uasset_read/models/` package. This includes UEdGraphPin, UEdGraphNode (with 5 specific node type subclasses), UEdGraph, FMemberReference, ParseResult, and StatusInfo. The migration is NOT a 1:1 copy — CONTEXT.md decisions D-01 through D-14 establish a new architecture with proper inheritance, strict typing, and separated serialization.

Key finding: The old codebase uses `@dataclass` on all model classes but has inconsistencies (e.g., `any` instead of `Any` in `UEdGraphNode.node_data`, mixed `Optional` vs raw types, no `Self` typing). The new design must fix these while maintaining binary-compatible JSON output.

**Primary recommendation:** Create `models/` package with 3 files (`core.py`, `node_types.py`, `result.py`), use strict Python 3.10+ typing, `@dataclass` on all classes, `from_archive` classmethods for binary reading, and flat exports via `__init__.py`.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (命名风格):** 保持 UE 源码命名 — UEdGraph、UEdGraphNode、UEdGraphPin、FMemberReference 等
- **D-02 (目录结构):** `models/core.py` — UEdGraphPin、UEdGraphNode 基类、UEdGraph、FMemberReference；`models/node_types.py` — 5 种节点子类；`models/result.py` — ParseResult、StatusInfo
- **D-03 (扁平导入):** 所有模型类通过 `models/__init__.py` 统一导出，`from uasset_read.models import UEdGraph`
- **D-04 (节点继承):** UEdGraphNode 作为基类，具体节点类型作为子类继承
- **D-05 (类型识别):** 子类通过 class_name 字段或 isinstance()/match/case 分派
- **D-06 (独立序列化):** 数据类只定义字段，序列化逻辑在独立函数/模块中
- **D-07 (空值过滤):** 序列化函数默认跳过 None 值和空字符串/空列表
- **D-08 (EditorOnly 处理):** EditorOnly 字段标记为 exclude，序列化时默认跳过
- **D-09 (嵌套结构):** 序列化函数处理嵌套结构转换，不在数据类中硬编码
- **D-10 (严格类型):** Python 3.10+ 严格类型提示，包括 Generic、TypeVar、Union，子类方法返回 Self
- **D-11 (节点多态):** node_data 字段在基类中声明为 `Optional[UEdGraphNode]`（多态）
- **D-12 (模型自带解析):** 每个数据类附带 `from_archive(archive: FArchive) -> Self` 静态方法
- **D-13 (UEdGraphPin 解析):** from_archive 按 UE 源码 EdGraphPin.cpp L1838-1964 序列化顺序读取
- **D-14 (UEdGraphNode 解析):** 基类 from_archive 读公共字段后由子类扩展

### Claude's Discretion
- 具体字段顺序和默认值由规划阶段确定
- 序列化函数命名（to_dict / format_xxx 等）由规划阶段确定
- 是否需要基类 Model 或 Serializable mixin 由规划阶段确定

### Deferred Ideas (OUT OF SCOPE)
- 蓝图变量完整元数据增强 — 属于 Phase 29b 或 Phase 30
- PropertyTag/PropertyValue 数据模型 — 属于 Phase 29b
- 图连接数据结构 (ExecutionFlow/DataFlow) — 属于 Phase 29b
- MCP Server 封装 — 延后至 v4.x
- JSON Schema 生成 — 延后至 v9.0

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| UEdGraphPin (data model) | API / Backend | — | Pure dataclass, no I/O |
| UEdGraphNode (data model) | API / Backend | — | Pure dataclass with inheritance |
| UEdGraph (container) | API / Backend | — | Holds nodes, no rendering |
| ParseResult / StatusInfo | API / Backend | — | Result aggregation |
| from_archive (reading) | API / Backend | FArchive | Binary deserialization |
| JSON serialization | Output Formatter | — | D-06/D-09: separate module |
| FEdGraphPinType | API / Backend | — | Type metadata struct |
| Node type subclasses | API / Backend | — | D-04: inherit from UEdGraphNode |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `dataclasses` (stdlib) | Python 3.10+ | @dataclass decorator, field(), asdict() | Already used in all existing serializers (package_summary.py, object_resources.py) [VERIFIED: codebase] |
| `typing` (stdlib) | Python 3.10+ | Optional, List, Dict, Any, TYPE_CHECKING, Self | Project uses Python 3.14.3 [VERIFIED: `python --version`] |
| `__future__.annotations` | Python 3.10+ | `from __future__ import annotations` for forward refs | Prevents circular import issues with Self/UEdGraphNode forward refs |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| No external dependencies | — | Project policy is zero runtime deps | Always — pyproject.toml has `dependencies = []` [VERIFIED: pyproject.toml] |

**Installation:** No new packages needed — all modules are Python stdlib.

**Version verification:** Python 3.14.3 confirmed on target machine. `Self` type is available via `typing.Self` (Python 3.11+) or `typing_extensions.Self` for 3.10 compat. Since the project runs on 3.14, `typing.Self` is directly available.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│  uasset_read.py (legacy entry)                          │
│  parse_uasset() calls serializers + models + formatters │
└────────────┬────────────────────────────────────────────┘
             │ (currently imports from single file)
             ▼
┌─────────────────────────────────────────────────────────┐
│  FArchive (archive.py) ──────────────────► Binary I/O  │
│       │                                                    │
│       ▼                                                    │
│  Serializers (serializers/) ─────────────► Summary/Maps │
│       │                                                    │
│       ▼                                                    │
│  Models (models/) ◄── Phase 29 ─────────► Data Classes │
│  ├── core.py      (Pin, Node, Graph, MemberRef)        │
│  ├── node_types.py (5 subclasses)                        │
│  └── result.py   (ParseResult, StatusInfo)              │
│       │                                                    │
│       ▼                                                    │
│  Parsers (parsers/) ◄── Phase 30+ ─────► Property/Graph│
│       │                                                    │
│       ▼                                                    │
│  Output (formatters/) ◄── Phase 32+ ───► JSON/Text/MD  │
└─────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/uasset_read/
├── __init__.py               # Updated: add models exports
├── archive.py                # Phase 28: FArchive
├── constants.py              # Phase 27
├── exceptions.py             # Phase 27
├── serializers/              # Phase 28
│   ├── __init__.py
│   ├── package_summary.py
│   └── object_resources.py
├── models/                   # NEW — Phase 29
│   ├── __init__.py           # Flat exports (D-03)
│   ├── core.py               # UEdGraphPin, UEdGraphNode, UEdGraph, FMemberReference, FEdGraphPinType
│   ├── node_types.py         # K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction
│   └── result.py             # ParseResult, StatusInfo
```

### Pattern: Established dataclass + from_archive

From `src/uasset_read/serializers/package_summary.py` [VERIFIED: codebase]:

```python
@dataclass
class GenerationInfo:
    """FGenerationInfo 版本世代信息。"""
    export_count: int = 0
    name_count: int = 0

@dataclass
class PackageFileSummary:
    """PackageFileSummary 文件头。"""
    tag: int
    legacy_file_version: int
    file_version_ue4: int
    # ... many more fields with defaults
```

Key patterns observed:
1. **`@dataclass` on every model class** — stdlib only, no attrs/pydantic
2. **Required fields first, optional with defaults after** — Python dataclass rules
3. **`field(default_factory=list)` for mutable defaults** — avoids shared state
4. **`Optional[type] = None` for version-dependent fields** — e.g., `b_import_optional: Optional[bool] = None`
5. **No `from_archive` on dataclasses** — standalone functions like `read_package_summary(archive) -> PackageFileSummary`
6. **Type hints use `List`, `Dict`, `Optional`, `Any`** from `typing`

**Deviation for Phase 29:** D-12 requires `from_archive` as a method on dataclasses (unlike current serializer pattern which uses standalone functions). This is a deliberate architectural shift.

### Pattern 1: Node Inheritance (D-04)

**What:** UEdGraphNode as abstract-ish base, 5 specific subclasses with `super()` pattern for from_archive.

**When to use:** Always — this is a locked decision.

```python
# Example pattern for Phase 29
from dataclasses import dataclass, field
from typing import Optional, List, Self, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

@dataclass
class UEdGraphNode:
    """基类 — 所有节点共字段。"""
    node_guid: str
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_comment: str = ""
    pins: List["UEdGraphPin"] = field(default_factory=list)
    class_name: str = ""
    node_data: Optional["UEdGraphNode"] = None  # D-11: 多态声明
```

### Pattern 2: Flat Export (D-03)

**What:** `models/__init__.py` re-exports all classes, callers import from `uasset_read.models`.

```python
# models/__init__.py
from .core import UEdGraphPin, UEdGraphNode, UEdGraph, FMemberReference, FEdGraphPinType
from .node_types import (
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot,
    EdGraphNodeComment, K2NodeEnhancedInputAction,
)
from .result import ParseResult, StatusInfo

__all__ = [
    "UEdGraphPin", "UEdGraphNode", "UEdGraph", "FMemberReference", "FEdGraphPinType",
    "K2NodeCallFunction", "K2NodeEvent", "K2NodeKnot",
    "EdGraphNodeComment", "K2NodeEnhancedInputAction",
    "ParseResult", "StatusInfo",
]
```

### Anti-Patterns to Avoid

- **1:1 copy of old dataclass definitions** — The old code uses `any` (lowercase) instead of `Any`, inconsistent `Optional` usage, and `node_data: Optional[any]` which should be `Optional[UEdGraphNode]` [VERIFIED: uasset_read.py:1938]
- **Putting serialization logic in dataclasses** — D-06 explicitly forbids this. The old code does not have from_archive on dataclasses either — it uses standalone functions. Keep parsing separate.
- **Circular imports between models and serializers** — Use `TYPE_CHECKING` guards and string annotations for forward refs (e.g., `"UEdGraphPin"` in UEdGraphNode)
- **Not preserving `asdict()` compatibility** — The `format_node_to_dict()` function at uasset_read.py:6640-6682 uses `asdict(pin)` and `asdict(node_data)`. New dataclass field names and nesting must produce identical dict output.
- **Inheriting dataclass with `@dataclass` on subclass without care** — Python dataclass inheritance requires `@dataclass` on each subclass to inherit field ordering. Without it, the subclass won't be treated as a dataclass.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dataclass boilerplate | Manual `__init__`, `__repr__` | `@dataclass` from stdlib | Already established pattern, `asdict()` support critical for JSON output |
| Mutable default lists | `field: list = []` | `field(default_factory=list)` | Shared mutable default bug [VERIFIED: existing code uses this correctly] |
| Forward reference types | Runtime import of UEdGraphPin in UEdGraphNode | `TYPE_CHECKING` + string annotations | Circular import between core.py classes |
| Node type dispatch | String matching in multiple places | Single `match/case` with class_name (D-05) | Already established in uasset_read.py:4273-4294 |
| GUID formatting | Manual hex formatting logic | `bytes.hex()` method | Consistent with existing code [VERIFIED: uasset_read.py:3922] |

**Key insight:** The deceptively complex problem is maintaining `asdict()` output compatibility. The `format_node_to_dict()` function (uasset_read.py:6640-6682) calls `asdict(pin)` and `asdict(node.node_data)` directly. If field names or nesting changes, JSON output breaks. This is the primary risk area.

## Runtime State Inventory

> SKIPPED — This is a greenfield extraction phase, not a rename/refactor/migration. No runtime state (databases, caches, OS registrations) contains references to these data model classes that need updating. The classes exist only in `uasset_read.py` source code and test mocks.

## Common Pitfalls

### Pitfall 1: `asdict()` Output Incompatibility
**What goes wrong:** New dataclass field names, types, or ordering produce different `asdict()` output, breaking JSON serialization and failing tests.
**Why it happens:** `dataclasses.asdict()` recursively converts ALL fields. If `UEdGraphPin` has a field named `linked_to_raw` that was previously a different structure, the JSON diff fails.
**How to avoid:** Compare `asdict(old_instance)` vs `asdict(new_instance)` for each model type using test fixtures. Keep field names identical to old code.
**Warning signs:** `test_output_formatting.py` and `test_phase14_output_formats.py` failures after migration.

### Pitfall 2: Circular Import Between core.py Classes
**What goes wrong:** `core.py` defines `UEdGraphPin` and `UEdGraphNode`, but `UEdGraphNode.pins` is `List[UEdGraphPin]` and `UEdGraph.nodes` is `List[UEdGraphNode]`. Import ordering matters.
**Why it happens:** Python evaluates module top-to-bottom. If `UEdGraphNode` references `UEdGraphPin` before it's defined, NameError.
**How to avoid:** Use string annotations (`List["UEdGraphPin"]`) with `from __future__ import annotations` at top of file. This defers type evaluation.
**Warning signs:** `ImportError` or `NameError` on module load.

### Pitfall 3: FEdGraphPinType Placement
**What goes wrong:** `FEdGraphPinType` is currently defined at uasset_read.py:1634 (before the graph dataclasses) but used by `UEdGraphPin.pin_type`. It must be in `core.py` before `UEdGraphPin`.
**Why it happens:** FEdGraphPinType is not explicitly mentioned in the Phase 29 scope but is a dependency of UEdGraphPin.
**How to avoid:** Include `FEdGraphPinType` in `models/core.py` — it is a core data model referenced by UEdGraphPin. [VERIFIED: uasset_read.py:1894 `pin_type: "FEdGraphPinType"`]
**Warning signs:** `NameError: name 'FEdGraphPinType' is not defined` in `core.py`.

### Pitfall 4: `Optional[any]` vs `Optional[Any]`
**What goes wrong:** Old code uses `node_data: Optional[any] = None` (lowercase `any`). Python 3.14 treats `any` as a runtime NameError in type position (unlike earlier versions where it was silently accepted as a regular name).
**Why it happens:** `any` is a builtin function, not a typing construct. The old code was "lucky" it worked.
**How to avoid:** Use `from typing import Any` and `Optional[UEdGraphNode]` per D-11.
**Warning signs:** `TypeError` or type checker errors on module load in Python 3.14.

### Pitfall 5: `from_archive` vs Standalone Function Pattern Mismatch
**What goes wrong:** D-12 requires `from_archive` on dataclasses, but existing serializers use standalone functions (`read_package_summary`). Callers might expect the old pattern.
**Why it happens:** Inconsistency between Phase 28 serializers (standalone functions) and Phase 29 models (classmethods).
**How to avoid:** Document this clearly. The planner should note that models use `from_archive` while serializers use standalone functions. Future phases (30-32) will follow the model pattern. Consider adding a comment explaining the divergence.

## Code Examples

### UEdGraphPin (from_archive pattern — D-12, D-13)
```python
# Source: uasset_read.py:3700-3973 (read_ue_graph_pin) + EdGraphPin.cpp L1838-1964
@dataclass
class UEdGraphPin:
    pin_id: str
    pin_name: str
    pin_tooltip: str = ""
    direction: int = 0
    pin_type: Optional["FEdGraphPinType"] = None
    default_value: Optional[str] = None
    auto_default_value: Optional[str] = None
    default_object: Optional[int] = None
    default_text_value: Optional[str] = None
    linked_to_raw: List[dict] = field(default_factory=list)
    sub_pins: List[dict] = field(default_factory=list)
    parent_pin: Optional[dict] = None
    hidden: bool = False
    not_connectable: bool = False
    advanced_view: bool = False
    orphaned_pin: bool = False
    owning_node_index: int = 0
    source_index: Optional[int] = None
    persistent_guid: Optional[str] = None
    flags: int = 0
```

### FEdGraphPinType (dependency of UEdGraphPin)
```python
# Source: uasset_read.py:1634-1651
@dataclass
class FEdGraphPinType:
    pin_category: str = ""
    pin_sub_category: str = ""
    pin_sub_category_object: int = 0
    container_type: int = 0
    is_reference: bool = False
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False
```

### Node type dispatch (match/case — D-05)
```python
# Source: uasset_read.py:4273-4294
match class_name:
    case "K2Node_CallFunction":
        node_data = K2NodeCallFunction(
            function_reference=function_reference or FMemberReference(),
            b_defaults_to_pure=False
        )
    case "K2Node_Event":
        node_data = K2NodeEvent(
            event_reference=event_reference or FMemberReference(),
            b_override_function=False
        )
    case "K2Node_Knot":
        node_data = K2NodeKnot()
    case "EdGraphNode_Comment":
        node_data = read_edgraph_node_comment(archive)
    case "K2Node_EnhancedInputAction":
        node_data = read_k2node_enhanced_input(archive, name_map)
    case _:
        node_data = {"unknown_type": class_name}
```

### Old `format_node_to_dict` — the compatibility target
```python
# Source: uasset_read.py:6640-6682
# This function MUST continue to work with new dataclasses
result = {
    "node_name": node_name,
    "node_type": node.class_name,
    "node_guid": node.node_guid,
    "position": {"x": node.node_pos_x, "y": node.node_pos_y},
    "node_comment": node.node_comment,
    "pins": [asdict(pin) for pin in node.pins],
}
if node.node_data is not None:
    if isinstance(node.node_data, K2NodeCallFunction):
        fr = node.node_data.function_reference
        result["function_reference"] = { ... }
    elif isinstance(node.node_data, K2NodeEvent):
        er = node.node_data.event_reference
        result["event_reference"] = { ... }
    elif isinstance(node.node_data, dict):
        result["node_data"] = node.node_data
    elif hasattr(node.node_data, '__dataclass_fields__'):
        result["node_data"] = asdict(node.node_data)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `node_data: Optional[any]` | `node_data: Optional[UEdGraphNode]` | Phase 29 | Proper typing, Self return |
| Standalone `read_xxx()` functions | `from_archive()` classmethods on models | D-12 | Models own their parsing |
| Mixed `typing` imports | Strict `from typing import ...` with `TYPE_CHECKING` | Phase 29 | No circular imports |
| No inheritance for node types | UEdGraphNode base + 5 subclasses | D-04 | Proper OOP, isinstance works |
| `flags: int = 0` (legacy field) | Kept but documented as deprecated | Phase 29 | Backward compat, clear deprecation |

**Deprecated/outdated:**
- `flags` field on UEdGraphPin: This is a legacy uint8 bitfield that has been replaced by individual bool fields (hidden, not_connectable, etc.). Keep for serialization compatibility but mark as deprecated. [VERIFIED: uasset_read.py:1919]
- `node_data: Optional[any]` pattern: Should be `Optional[UEdGraphNode]` per D-11. The old code's use of lowercase `any` was incorrect typing.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `FEdGraphPinType` must be included in `core.py` despite not being explicitly in Phase 29 scope | Standard Stack, Code Examples | Medium — without it, `UEdGraphPin.pin_type` has no type definition; planner may need to adjust scope |
| A2 | `BlueprintVariable`, `BlueprintMetadata`, `BlueprintFunction`, `BlueprintEvent` are OUT OF SCOPE for Phase 29 (they're at uasset_read.py:1655-1874) | Deferred Ideas | Low — these are referenced in ParseResult but defined separately; Phase 29b or 30 should handle them |
| A3 | `parse_uasset` function and `format_*` functions remain in `uasset_read.py` for now (Phase 33 will move them) | Architecture Patterns | Low — Phase 29 scope is data models only, not pipeline functions |
| A4 | Python 3.14.3 on target machine means `typing.Self` is available without `typing_extensions` | Standard Stack | Low — can verify during implementation |

## Open Questions

1. **Should `FEdGraphPinType` be in `core.py` or a separate `models/types.py`?**
   - What we know: It's a simple 8-field dataclass used only by `UEdGraphPin.pin_type`
   - What's unclear: Whether future phases will have more type structs warranting a separate file
   - Recommendation: Put in `core.py` for now — it's small and directly referenced by a core model. Can extract later if needed.

2. **Should `BlueprintMetadata` and `BlueprintVariable` be extracted now or deferred?**
   - What we know: `ParseResult.blueprint: Optional[BlueprintMetadata]` references these types (uasset_read.py:2064)
   - What's unclear: Whether CONTEXT.md's "Deferred Ideas" (蓝图变量完整元数据增强) means the entire BlueprintMetadata class is deferred, or just the enhanced fields
   - Recommendation: Include minimal `BlueprintMetadata`, `BlueprintVariable`, `BlueprintFunction`, `BlueprintEvent` stubs in `models/result.py` or a separate `models/blueprint.py` to satisfy ParseResult's type annotation. These are existing classes, not new features. Clarify with user during planning.

3. **How to handle `PropertyValue` dependency?**
   - What we know: `ObjectExport.properties: List[Any]` currently uses `Any` [VERIFIED: object_resources.py:82], but `PropertyValue` is referenced in test imports
   - What's unclear: Whether `PropertyValue` is already defined somewhere in the new codebase
   - Recommendation: Not in Phase 29 scope. `ObjectExport.properties` uses `List[Any]` currently. Phase 29b/30 should define `PropertyTag`/`PropertyValue`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.14.3 | — |
| pytest | Testing | ✓ | 9.0.3 | — |
| dataclasses | Data models | ✓ | stdlib | — |
| typing | Type hints | ✓ | stdlib | — |

No external dependencies required.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | None — uses pytest defaults (discovers `tests/test_*.py`) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MOD-06 | PropertyTag extraction | unit | `python -m pytest tests/test_property_parsing.py -x` | ✅ (Phase 30 scope) |
| MOD-07 | Property parser extraction | unit | `python -m pytest tests/test_property_parsing.py -x` | ✅ (Phase 30 scope) |
| MOD-08 | Core data models defined | unit | `python -m pytest tests/test_graph_parsing.py -x` | ✅ needs import updates |

### Wave 0 Gaps
- [ ] `tests/test_models_core.py` — covers UEdGraphPin, UEdGraphNode, UEdGraph dataclass instantiation
- [ ] `tests/test_models_node_types.py` — covers 5 node type subclasses
- [ ] `tests/test_models_result.py` — covers ParseResult, StatusInfo
- [ ] Test import updates: 10 test files importing from `uasset_read` need `from uasset_read.models import ...` for model classes, OR `__init__.py` must re-export from models to maintain `from uasset_read import UEdGraph` compatibility

### Test Files Requiring Import Updates

| Test File | Current Import | Needs Update |
|-----------|---------------|--------------|
| `tests/test_graph_parsing.py` | `from uasset_read import UEdGraph, UEdGraphNode, UEdGraphPin, FMemberReference, K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction` | Yes — add `from uasset_read.models import ...` OR re-export in `__init__.py` |
| `tests/test_output_formatting.py` | `from uasset_read import UEdGraph, UEdGraphNode, UEdGraphPin, K2NodeCallFunction, K2NodeEvent, FMemberReference` | Yes |
| `tests/test_phase14_output_formats.py` | `from uasset_read import UEdGraph, UEdGraphNode, UEdGraphPin, ...` | Yes |
| `tests/test_phase21_verification.py` | `from uasset_read import parse_uasset, format_json_full` (uses models indirectly) | May need update |
| `tests/test_skill_integration.py` | `from uasset_read import parse_uasset, ...` (uses models indirectly) | May need update |
| `tests/test_partial_results.py` | `from uasset_read import ErrorContext, ParseResult` | Yes — ParseResult moves to models |
| `tests/test_uasset_read.py` | `from uasset_read import ...` | May need update |
| `tests/test_blueprint_extraction.py` | `from uasset_read import ...` | May need update |
| `tests/test_exportmap_properties.py` | `from uasset_read import ObjectExport, ...` | No change (ObjectExport stays in serializers) |
| `tests/test_phase12_blueprint_variables.py` | `from uasset_read import ...` | May need update |

**Recommendation:** Update `src/uasset_read/__init__.py` to re-export model classes from `models/` alongside existing exports. This maintains backward compatibility for all 10 test files without requiring import changes. This is cleaner than updating every test file.

## Security Domain

Not applicable — this phase involves only data model extraction (dataclass definitions). No authentication, authorization, input validation, or cryptography is involved. The models are pure data structures with no network or file I/O.

## Detailed Field Analysis

### UEdGraphPin (20 fields) [VERIFIED: uasset_read.py:1878-1920]

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| pin_id | str | (required) | FGuid hex (16 bytes) |
| pin_name | str | (required) | FName resolved |
| pin_tooltip | str | "" | FString, Phase 18 addition |
| direction | int | 0 | uint8: 0=Input, 1=Output, 2=None |
| pin_type | FEdGraphPinType | None | Complex struct, 8 sub-fields |
| default_value | Optional[str] | None | FString |
| auto_default_value | Optional[str] | None | FString |
| default_object | Optional[int] | None | FPackageIndex |
| default_text_value | Optional[str] | None | FText simplified |
| linked_to_raw | List[dict] | [] | Connection refs as dicts |
| sub_pins | List[dict] | [] | Same format as linked_to |
| parent_pin | Optional[dict] | None | Same format |
| hidden | bool | False | BitField bit 0 |
| not_connectable | bool | False | BitField bit 1 |
| advanced_view | bool | False | BitField bit 4 |
| orphaned_pin | bool | False | BitField bit 5 |
| owning_node_index | int | 0 | FPackageIndex (EditorOnly, D-08 exclude) |
| source_index | Optional[int] | None | Version-dependent (EditorOnly) |
| persistent_guid | Optional[str] | None | FGuid hex (EditorOnly) |
| flags | int | 0 | Legacy uint8 bitfield (deprecated) |

### UEdGraphNode (7 fields) [VERIFIED: uasset_read.py:1922-1938]

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| node_guid | str | (required) | FGuid hex |
| node_pos_x | int | 0 | Editor position X |
| node_pos_y | int | 0 | Editor position Y |
| node_comment | str | "" | FString comment |
| pins | List[UEdGraphPin] | [] | Child pins |
| class_name | str | "" | Type identifier |
| node_data | Optional[UEdGraphNode] | None | D-11: polymorphic, should be `Optional["UEdGraphNode"]` |

### UEdGraph (6 fields) [VERIFIED: uasset_read.py:1941-1956]

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| graph_name | str | (required) | Export ObjectName |
| graph_class | str | (required) | ClassIndex resolved (EdGraph/UberEdGraph) |
| schema | Optional[str] | None | FPackageIndex resolved |
| nodes | List[UEdGraphNode] | [] | Child nodes |
| graph_guid | Optional[str] | None | FGuid hex |
| b_editable | bool | True | uint8 |

### FMemberReference (4 fields) [VERIFIED: uasset_read.py:1959-1971]

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| member_parent | Optional[str] | None | Class path |
| member_name | str | "" | FName function/event name |
| member_guid | Optional[str] | None | FGuid hex |
| b_self_context | bool | False | uint8 self call flag |

### 5 Node Type Subclasses [VERIFIED: uasset_read.py:1978-2048]

| Class | Parent | Fields | Notes |
|-------|--------|--------|-------|
| K2NodeCallFunction | UEdGraphNode | function_reference (FMemberReference), b_defaults_to_pure (bool) | Most common node type |
| K2NodeEvent | UEdGraphNode | event_reference (FMemberReference), b_override_function (bool) | Event nodes |
| K2NodeKnot | UEdGraphNode | none (pass) | Reroute node, no extra fields |
| EdGraphNodeComment | UEdGraphNode | comment_color (Tuple[float,float,float,float]), node_width (int), node_height (int), font_size (int) | Comment box |
| K2NodeEnhancedInputAction | UEdGraphNode | input_action_path (str) | Enhanced input node |

**Note:** These subclasses currently do NOT inherit from UEdGraphNode in the old code [VERIFIED: uasset_read.py:1978-2048]. They are standalone dataclasses. D-04 requires changing this to proper inheritance. This is a significant design change that will affect how `node_data` is populated and serialized.

### ParseResult (16 fields) [VERIFIED: uasset_read.py:2051-2074]

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| summary | Optional[PackageFileSummary] | None | From serializers |
| name_map | List[str] | [] | Name table |
| import_map | List[ObjectImport] | [] | Import table |
| export_map | List[ObjectExport] | [] | Export table |
| errors | List[str] | [] | Error messages |
| blueprint | Optional[BlueprintMetadata] | None | D-02: auto-extracted |
| graphs | List[UEdGraph] | [] | Phase 7 graph data |
| is_success | bool | False | Parse success flag |
| mmap_used | bool | False | D-02: mmap tracking |
| mmap_warning | Optional[str] | None | D-03: mmap warning |
| warnings | List[str] | [] | D-13: warnings list |
| imports | List[Dict] | [] | D-10-05: dependency list |
| soft_references | List[Dict] | [] | D-10-08: soft refs |
| circular_deps | List[List[str]] | [] | D-10-13: circular deps |

### StatusInfo (3 fields) [VERIFIED: uasset_read.py:2077-2091]

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| status | str | (required) | "success" / "fail" / "error" |
| message | Optional[str] | None | Human-readable message |
| code | Optional[str] | None | Machine-readable code |

### Classes NOT in Phase 29 scope but referenced by models

| Class | Location | Referenced By | Recommendation |
|-------|----------|---------------|----------------|
| FEdGraphPinType | uasset_read.py:1634 | UEdGraphPin.pin_type | Include in core.py |
| BlueprintMetadata | uasset_read.py:1716 | ParseResult.blueprint | Include stub in result.py or defer |
| BlueprintVariable | uasset_read.py:1655 | BlueprintMetadata.variables | Include stub with BlueprintMetadata |
| BlueprintFunction | uasset_read.py:1819 | BlueprintMetadata.functions | Include stub |
| BlueprintEvent | uasset_read.py:1772 | BlueprintMetadata.events | Include stub |
| PackageFileSummary | serializers/package_summary.py | ParseResult.summary | Already in serializers, import OK |
| ObjectImport | serializers/object_resources.py | ParseResult.import_map | Already in serializers, import OK |
| ObjectExport | serializers/object_resources.py | ParseResult.export_map | Already in serializers, import OK |

## Sources

### Primary (HIGH confidence)
- Codebase: `uasset_read.py` lines 1878-2074 — All dataclass definitions [VERIFIED: direct read]
- Codebase: `uasset_read.py` lines 3700-3973 — `read_ue_graph_pin()` function [VERIFIED: direct read]
- Codebase: `uasset_read.py` lines 4240-4304 — `read_ue_graph_node()` function [VERIFIED: direct read]
- Codebase: `uasset_read.py` lines 6640-6682 — `format_node_to_dict()` serialization [VERIFIED: direct read]
- Codebase: `uasset_read.py` lines 1634-1651 — `FEdGraphPinType` definition [VERIFIED: direct read]
- Codebase: `src/uasset_read/serializers/package_summary.py` — Established dataclass pattern [VERIFIED: direct read]
- Codebase: `src/uasset_read/serializers/object_resources.py` — Established dataclass pattern [VERIFIED: direct read]
- Codebase: `src/uasset_read/archive.py` — FArchive interface [VERIFIED: direct read]
- Codebase: `src/uasset_read/__init__.py` — Current export pattern [VERIFIED: direct read]

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions D-01 through D-14 — Locked architectural choices [VERIFIED: direct read of 29-CONTEXT.md]
- ROADMAP.md Phase 29 description — Success criteria [VERIFIED: direct read]
- REQUIREMENTS.md MOD-06, MOD-07 — Requirement definitions [VERIFIED: direct read]

### Tertiary (LOW confidence)
- UE source `EdGraphPin.cpp` L1838-1964 — Referenced in code comments but not independently verified in this session. The pin reading order in `read_ue_graph_pin()` (uasset_read.py:3700-3973) was validated against actual binary data during Phase 18/22, so the field order is reliable even if the UE source line numbers may have shifted.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All stdlib, zero dependencies, confirmed Python 3.14.3
- Architecture: HIGH — Locked decisions in CONTEXT.md, patterns verified in existing codebase
- Pitfalls: HIGH — Based on direct code analysis and Phase 28a findings (UE5 serialization format changes)
- Field analysis: HIGH — Direct verification from uasset_read.py source

**Research date:** 2026-05-11
**Valid until:** 2026-06-11 (30 days — stable domain, Python stdlib does not change)
