# Phase 31: 蓝图图解析模块 - Research

**Researched:** 2026-05-12
**Domain:** Unreal Engine Blueprint Graph serialization, FArchive binary parsing
**Confidence:** HIGH

## Summary

Phase 31 等价迁移旧版 `uasset_read.py` 中的蓝图图解析功能到模块化 `src/uasset_read/` 结构。核心任务是实现 `extract_blueprint_graphs()` 入口、图/节点/引脚三层二进制读取、5种节点类型特定读取器、以及执行流/数据流/连接映射构建函数。

旧版代码中这些函数分散在 3095-4679 行（二进制读取）和 6400-7115 行（流构建/格式化），涉及大量版本依赖逻辑（UE4 vs UE5 序列化格式差异）和安全边界检查。迁移的关键挑战在于：(1) `read_ue_graph_pin` 函数包含约 380 行高度版本依赖的 FText/PinType 序列化逻辑；(2) 节点读取需要与 Phase 30 的 `read_property_tag` 和 script_serial 解析正确协作；(3) 工厂模式（D-07/D-08）需要仔细设计以支持未来扩展。

**Primary recommendation:** 严格遵循 CONTEXT.md 中锁定的 D-01 至 D-09 决策，将二进制读取放在 `serializers/graph.py`，工厂函数放在同一文件（初始不需要独立 node_factory.py），流构建放在 `graph/flow_builder.py`。

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (目录结构):** 新建 `src/uasset_read/graph/` 目录，包含 `parser.py`, `node_reader.py`, `flow_builder.py`, `__init__.py`
- **D-02 (委托模式):** models/core.py 的 `from_archive` stub 保持为委托入口，内部调用 `serializers/graph.py` 中的独立函数
- **D-03 (serializers/graph.py):** 图底层二进制读取函数放在 `serializers/graph.py`，被 models 的 from_archive 委托调用
- **D-04 (节点类型读取器):** 5种节点类型特定读取器也放在 `serializers/graph.py`，通过 node_factory 调用
- **D-05 (归属):** build_execution_flows、build_data_flows、build_connections_map 放在 `graph/flow_builder.py`
- **D-06 (输入输出):** 这些函数消费 `List[UEdGraph]`，产出 `List[Dict]`
- **D-07 (工厂模式):** 使用 `NodeFactory.create()` 工厂模式
- **D-08 (工厂位置):** `create_node_from_archive()` 工厂函数在 `serializers/graph.py`
- **D-09 (已知类型):** 初始支持5种：K2Node_CallFunction、K2Node_Event、K2Node_Knot、EdGraphNode_Comment、K2Node_EnhancedInputAction。未知类型回退到基类

### Claude's Discretion
- 工厂函数的精确接口签名由规划阶段确定
- graph/ 目录下文件的精确划分（parser.py vs node_reader.py 的边界）由规划阶段确定
- 内部辅助函数命名由规划阶段确定

### Deferred Ideas (OUT OF SCOPE)
- UberGraph/事件分发图增强 — 属于 v8.0 (Phase 42)
- UBlueprintGeneratedClass 字节码反编译 — 属于 v8.0 (Phase 44)
- .umap/World 资产解析 — 属于 v9.0 (Phase 46)
- JSON Schema 验证 — 属于 v9.0

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| EdGraph 导出检测 | API/Backend (serializers) | — | 遍历 ExportMap，解析 FPackageIndex，属于序列化层 |
| FEdGraphPinType 读取 | API/Backend (serializers) | — | 版本依赖二进制读取 |
| UEdGraphPin 完整读取 | API/Backend (serializers) | — | FText/FPinType/FPackageIndex 复杂二进制解析 |
| UEdGraphNode 读取 | API/Backend (serializers) | — | script_serial PropertyTag 循环 + Pin 数组 |
| 5种节点类型读取器 | API/Backend (serializers) | — | FMemberReference 解析，类型特定字段 |
| 执行流/数据流构建 | API/Backend (graph) | — | 图遍历算法，不碰二进制 |
| 连接映射构建 | API/Backend (graph) | — | Pin GUID 查找和格式化 |
| 数据模型定义 | Models | — | 已有 stubs，Phase 31 实现 from_archive 委托 |

## Standard Stack

No new external libraries are needed. The project uses zero runtime dependencies — only Python standard library.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (struct, dataclasses, typing) | 3.10+ | Binary unpacking, data models, type hints | Project constraint — zero dependencies |

### Existing Internal Dependencies (VERIFIED: codebase)
| Module | Purpose |
|--------|---------|
| `uasset_read.archive.FArchive` | Binary read methods (read_i32, read_u8, read_fstring, read_name, read_bytes, read_bool, read_f32, peek_i32, seek, tell) |
| `uasset_read.constants` | MAX_PINS_PER_NODE=1000, MAX_NODES_PER_GRAPH=5000, MAX_LINKEDTO_PER_PIN=100, START_EVENT_TYPES, CONTROL_FLOW_NODES, BRANCH_TYPE_MAP, version thresholds |
| `uasset_read.exceptions.ParseError` | Error raising with context |
| `uasset_read.serializers.object_resources` | resolve_class_name, get_asset_class, PackageIndex |
| `uasset_read.serializers.property_tags` | read_property_tag |
| `uasset_read.serializers.package_summary` | PackageFileSummary (version info) |
| `uasset_read.models.core` | UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType, FMemberReference dataclasses |
| `uasset_read.models.node_types` | K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction |

## Architecture Patterns

### System Architecture Diagram

```
.uasset file
    │
    ▼
FArchive (archive.py) ─── binary read primitives
    │
    ▼
serializers/graph.py ─── graph binary parsing
    │
    ├── read_ue_graph() ──────────── reads Schema, Nodes array, GraphGuid
    │       │
    │       ├── read_ue_graph_node() ─── reads Pins[], Pos, Guid, script_serial props
    │       │       │
    │       │       ├── read_ue_graph_pin() ── reads full pin structure (18 fields)
    │       │       │       ├── read_ed_graph_pin_type()
    │       │       │       ├── read_pin_array()
    │       │       │       └── read_pin_reference()
    │       │       │
    │       │       └── read_property_tag() ─── (Phase 30, for script_serial props)
    │       │
    │       └── read_fmember_reference()
    │
    └── create_node_from_archive() ─── factory dispatch
            ├── read_k2node_call_function()
            ├── read_k2node_event()
            ├── read_k2node_knot()
            ├── read_edgraph_node_comment()
            └── read_k2node_enhanced_input()

List[UEdGraph] (models)
    │
    ▼
graph/flow_builder.py ─── graph analysis
    ├── build_execution_flows() ─── exec pin tracing from START_EVENT_TYPES
    ├── build_data_flows() ─── non-exec pin data flow extraction
    └── build_connections_map() ─── pin_id → node:pin mapping

graph/parser.py ─── entry points
    └── extract_blueprint_graphs() ─── ExportMap scan → EdGraph detection → read_ue_graph loop
```

### Recommended Project Structure

```
src/uasset_read/
├── serializers/
│   ├── graph.py              # NEW: binary read functions (read_ue_graph, read_ue_graph_node,
│   │                         #        read_ue_graph_pin, read_ed_graph_pin_type,
│   │                         #        read_fmember_reference, read_pin_array,
│   │                         #        read_pin_reference, create_node_from_archive,
│   │                         #        5 node type readers)
│   └── __init__.py           # UPDATED: export graph serializers
├── graph/
│   ├── parser.py             # NEW: extract_blueprint_graphs entry point
│   ├── flow_builder.py       # NEW: build_execution_flows, build_data_flows,
│   │                         #        build_connections_map, helpers
│   └── __init__.py           # NEW: flat export public API
├── models/
│   ├── core.py               # UPDATED: implement from_archive stubs → delegate to serializers/graph.py
│   └── node_types.py         # UPDATED: implement from_archive stubs → delegate to serializers/graph.py
└── __init__.py               # UPDATED: export graph module public API
```

### Pattern 1: Serializer Delegation (D-02/D-03)

**What:** Models define dataclass with `from_archive` stubs. Phase 31 replaces `raise NotImplementedError` with calls to `serializers/graph.py` functions.

**Example:**
```python
# models/core.py — from_archive implementation
@classmethod
def from_archive(cls, archive: FArchive, name_map: List[str], summary: PackageFileSummary,
                 export_map: List[ObjectExport], import_map: List[ObjectImport]) -> "UEdGraphPin":
    from uasset_read.serializers.graph import read_ue_graph_pin
    return read_ue_graph_pin(archive, name_map, summary, export_map, import_map)
```

### Pattern 2: Node Factory Dispatch (D-07/D-08/D-09)

**What:** `create_node_from_archive()` inspects `class_name` and dispatches to the correct reader. Unknown types fall back to base `UEdGraphNode`.

**Example:**
```python
# serializers/graph.py
def create_node_from_archive(
    archive: FArchive, name_map: List[str], summary: PackageFileSummary,
    export_map: List[ObjectExport], import_map: List[ObjectImport],
    node_export: ObjectExport, base_node: UEdGraphNode
) -> UEdGraphNode:
    class_name = base_node.class_name
    if class_name == "K2Node_CallFunction":
        node_data = read_k2node_call_function(archive, name_map, import_map, export_map)
        base_node.node_data = node_data
    elif class_name == "K2Node_Event":
        node_data = read_k2node_event(archive, name_map, import_map, export_map)
        base_node.node_data = node_data
    # ... other known types ...
    else:
        # Unknown type: keep base_node.node_data as None or dict
        pass
    return base_node
```

### Pattern 3: Script Serial Property Parsing (Phase 28a FIX)

**What:** UE5 nodes store `FunctionReference`/`EventReference`/`NodePosX`/`NodePosY`/`NodeGuid` as PropertyTags in the `script_serial` region, not as raw binary fields. The reader must loop through PropertyTags and extract relevant fields.

**Example from uasset_read.py L4037-4102:**
```python
if node_export.script_serial_size > 0:
    script_start = node_export.serial_offset + node_export.script_serial_offset
    script_end = script_start + node_export.script_serial_size
    archive.seek(script_start)

    # UE5 >= 1011: SerializationControlExtensions
    if summary.file_version_ue5 >= 1011:
        ctrl = archive.read_u8()
        if ctrl & 0x02:
            archive.read_u8()  # skip override_operation

    # Loop through PropertyTags
    while archive.tell() < script_end:
        tag = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5)
        if tag.name == "None":
            break
        if tag.name == "FunctionReference" and tag.size > 0:
            # Parse nested PropertyTags for FMemberReference struct
            value_end = archive.tell() + tag.size
            while archive.tell() < value_end:
                inner_tag = read_property_tag(...)
                # Handle MemberParent, MemberScope, MemberName, MemberGuid, bSelfContext
```

### Anti-Patterns to Avoid

- **Hardcoding serialization order:** UE version differences mean pin/graph serialization order varies. Always use version checks (`summary.file_version_ue5`, `framework_version`) before deciding field format.
- **Not validating array bounds:** Pin arrays, node arrays, and LinkedTo lists can be corrupted. Always check against MAX_PINS_PER_NODE, MAX_NODES_PER_GRAPH, MAX_LINKEDTO_PER_PIN.
- **FText parsing without fallback:** FText has 8+ history types and complex nested serialization. Use try/except with seek-back to position, as the old code does.
- **Ignoring script_serial offsets:** In UE5 assets, critical fields like FunctionReference are in script_serial PropertyTags, not in the raw node serialization. Skipping script_serial will lose these fields.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FText parsing | Custom FText parser | Existing `skip_ftext_editoronly()` pattern from uasset_read.py | FText has 8+ history types with nested FString/Map serialization; old code has 100+ lines of tested fallback logic |
| Pin array reading | Manual loop without bounds check | `read_pin_array()` with MAX_LINKEDTO_PER_PIN validation | Corrupted assets can have huge array counts causing DoS |
| PropertyTag parsing | Inline PropertyTag loop | Phase 30's `read_property_tag()` from `serializers/property_tags.py` | Already handles UE4/UE5 format switch, flags, extensions |
| Node type dispatch | if/else in read_ue_graph_node | `create_node_from_archive()` factory (D-07/D-08) | Centralized dispatch, extensible for new node types in future phases |
| FPackageIndex resolution | Manual index math | `resolve_class_name()` and `get_asset_class()` from `serializers/object_resources.py` | Already handles import/export/null cases with bounds checking |

**Key insight:** The old code's FText, PinType, and script_serial parsing logic is the result of extensive debugging against real UE5.7 assets. Replicating these patterns exactly — rather than "improving" them — is critical for migration equivalence.

## Common Pitfalls

### Pitfall 1: UE4 vs UE5 PinType Serialization Mismatch
**What goes wrong:** FEdGraphPinType has two serialization modes. UE4 assets (FileVersionUE4 >= 324) use custom serialization with FName/FString version dependency. UE5 assets use default reflection serialization (all UPROPERTY fields in declaration order). Using the wrong mode causes position offset.
**Why it happens:** `VER_UE4_EDGRAPHPINTYPE_SERIALIZATION = 324` check determines mode. UE5 assets have FileVersionUE4 = -9, so `use_custom_serialization = False` and reflection mode is used.
**How to avoid:** Use the exact version check: `ue4_version >= 324` for custom, otherwise reflection. The reflection mode reads fields in EdGraphPin.h L76-133 declaration order.
**Warning signs:** All pins after the first one are garbage or ParseError on unexpected data.

### Pitfall 2: FText EditorOnly Fields Causing Offset Drift
**What goes wrong:** PinFriendlyName (FText) and DefaultTextValue (FText) have variable-length serialization depending on history_type. Incorrectly skipping these causes all subsequent fields (Direction, PinType, DefaultValue, LinkedTo) to be misaligned.
**Why it happens:** FText history_type=255 (None) has `bHasCultureInvariantString` bool + optional FString. history_type=0 (Base) has 3 FStrings. The old code uses try/except with seek-back as a safety net.
**How to avoid:** Follow the exact FText parsing logic from uasset_read.py L3675-3728 (PinFriendlyName) and L3807-3864 (DefaultTextValue). Always have a fallback seek-back on exception.
**Warning signs:** PinType.pin_category reads as garbage string, LinkedTo array count is unreasonable.

### Pitfall 3: script_serial PropertyTag Nested Parsing
**What goes wrong:** FunctionReference and EventReference in UE5 assets are serialized as StructProperty with nested PropertyTags for each UPROPERTY field. Missing any nested field (especially MemberScope FString or bWasDeprecated bool) causes position offset.
**Why it happens:** The old code (Phase 28a FIX) discovered that MemberScope (FString) was being skipped, and bWasDeprecated (bool) was missing. Both caused subsequent field reads to fail.
**How to avoid:** Process ALL nested PropertyTags in the struct value region. Read MemberParent (i32), MemberScope (FString), MemberName (FName), MemberGuid (16 bytes), bSelfContext (bool from tag.bool_val or UBOOL), bWasDeprecated (bool).
**Warning signs:** FunctionReference member_name is garbage or empty, subsequent pin reads fail.

### Pitfall 4: Circular Import Between graph/ and serializers/
**What goes wrong:** `graph/parser.py` imports from `serializers/graph.py`, which imports from `models/core.py`, which imports from `serializers/graph.py` for `from_archive` delegation — creating a cycle.
**Why it happens:** D-02 requires models to delegate to serializers, but serializers also need models as return types.
**How to avoid:** Use `TYPE_CHECKING` guards for type hints. In model `from_archive` methods, do deferred imports: `from uasset_read.serializers.graph import read_ue_graph_pin` inside the method body, not at module level. serializers should never import from graph/.

### Pitfall 5: Node Factory Position Management
**What goes wrong:** `read_ue_graph_node` already reads base class fields (Pins, Pos, Guid, script_serial props) and positions the archive. The node type reader then expects to read additional fields from the current position. If the factory re-seeks or the base reader doesn't advance correctly, the type reader reads garbage.
**Why it happens:** In the old code, node type readers like `read_k2node_call_function` expect the archive to be positioned after base class fields. But `read_ue_graph_node` consumes all script_serial data, leaving no additional data for type readers.
**How to avoid:** For UE5 assets with script_serial, type-specific data (FunctionReference, EventReference) is ALREADY in script_serial PropertyTags. The node type readers should be called within the script_serial parsing loop, not after. The factory should extract already-parsed data from the base node and wrap it in the appropriate type subclass.

## Code Examples

### FEdGraphPinType — Reflection Serialization (UE5 assets)
```python
# Source: uasset_read.py L3234-3264 (default reflection mode)
# Per EdGraphPin.h L76-133: UPROPERTY field declaration order
pin_type = FEdGraphPinType()
pin_type.pin_category = archive.read_name(name_map)        # 1. PinCategory (FName)
pin_type.pin_sub_category = archive.read_name(name_map)    # 2. PinSubCategory (FName)
archive.read_i32()        # 3. PinSubCategoryObject (FPackageIndex)
archive.read_i32()        # 4. MemberParent (FPackageIndex)
archive.read_name(name_map)  # 5. MemberName (FName)
archive.read(16)          # 6. MemberGuid (FGuid)
archive.read_name(name_map)  # 7. TerminalCategory (FName)
archive.read_name(name_map)  # 8. TerminalSubCategory (FName)
archive.read_i32()        # 9. TerminalSubCategoryObject (FPackageIndex)
pin_type.container_type = archive.read_u8()   # 10. ContainerType (uint8)
flags_byte = archive.read_u8()  # 11. Bit flags
pin_type.is_reference = (flags_byte & 0x04) != 0
pin_type.is_const = (flags_byte & 0x08) != 0
pin_type.is_weak_pointer = (flags_byte & 0x10) != 0
pin_type.is_uobject_wrapper = (flags_byte & 0x20) != 0
```

### FMemberReference — Binary Serialization
```python
# Source: uasset_read.py L4311-4380
# Per MemberReference.h L74-95 serialization order
member_parent_index = archive.read_i32()         # 1. MemberParent (FPackageIndex)
member_scope = archive.read_fstring()            # 2. MemberScope (FString)
member_name = archive.read_name(name_map)        # 3. MemberName (FName)
member_guid = archive.read_bytes(16).hex()       # 4. MemberGuid (FGuid)
b_self_context = archive.read_bool()             # 5. bSelfContext (bool)
b_was_deprecated = archive.read_bool()           # 6. bWasDeprecated (bool)
```

### Node Factory — Unknown Type Fallback (D-09)
```python
# Source: uasset_read.py read_ue_graph_node pattern + D-09 decision
KNOWN_NODE_TYPES = frozenset({
    "K2Node_CallFunction",
    "K2Node_Event",
    "K2Node_Knot",
    "EdGraphNode_Comment",
    "K2Node_EnhancedInputAction",
})

def create_node_from_archive(archive, name_map, summary, export_map, import_map, node_export, base_node):
    class_name = base_node.class_name
    if class_name == "K2Node_CallFunction":
        base_node.node_data = read_k2node_call_function(archive, name_map, import_map, export_map)
    elif class_name == "K2Node_Event":
        base_node.node_data = read_k2node_event(archive, name_map, import_map, export_map)
    elif class_name == "K2Node_Knot":
        base_node.node_data = read_k2node_knot(archive)
    elif class_name == "EdGraphNode_Comment":
        base_node.node_data = read_edgraph_node_comment(archive)
    elif class_name == "K2Node_EnhancedInputAction":
        base_node.node_data = read_k2node_enhanced_input(archive, name_map)
    else:
        # Unknown type: base_node.node_data stays None, class_name preserved
        pass
    return base_node
```

### Execution Flow Tracing
```python
# Source: uasset_read.py L6836-6891, 6952-7013
START_EVENT_TYPES = frozenset({"K2Node_Event", "K2Node_EnhancedInputAction",
                                "K2Node_VariableSet", "K2Node_CustomEvent"})
CONTROL_FLOW_NODES = frozenset({"K2Node_IfThenElse", "K2Node_Switch", ...})

def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    pin_lookup = {}
    node_lookup = {}
    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    execution_flows = []
    start_nodes = [n for n in graph.nodes if n.class_name in START_EVENT_TYPES]
    for start_node in start_nodes:
        if start_node.class_name == "K2Node_EnhancedInputAction":
            for pin in start_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category == "exec":
                    flow = _trace_execution_from_pin(start_node, pin, pin_lookup, node_lookup)
                    execution_flows.append({"start_event": f"{start_node.class_name}.{pin.pin_name}", "nodes": flow})
        else:
            flow = _trace_execution_from_event(start_node, pin_lookup, node_lookup)
            execution_flows.append({"start_event": _get_start_event_name(start_node), "nodes": flow})
    return execution_flows
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic `uasset_read.py` (7958 lines) | Modular `serializers/graph.py` + `graph/` package | This phase | Equivalent functionality, 4-5 files instead of 1 |
| Inline FText parsing in `read_ue_graph_pin` | May extract to helper in serializers | This phase | Reusable across pin and node parsing |
| `linked_to_raw` as mixed str/dict | Phase 18 normalized to `{"pin_guid": str}` dict format | Previous phase | Flow builders must handle dict format |
| `ParseError` without context | `ParseError` with `ErrorContext` | Phase 28 | Graph errors should include export_index, node_name |

**Deprecated/outdated:**
- Direct `import sys; DEBUG_PIN_PARSING = "--debug-pin" in sys.argv`: Use `constants.DEBUG_PIN_PARSING` instead (already in constants.py L146)
- Duplicate `CONTROL_FLOW_NODES` and `START_EVENT_TYPES` definitions: Already migrated to `constants.py` L152-170. Do NOT re-define in serializers/graph.py.
- `FORMAT_CONFIG` global dict: Used by `build_connections_map` for pin reference mode. Currently in constants.py L189. Flow builders should reference from constants.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `create_node_from_archive()` should re-use data already parsed by `read_ue_graph_node()` (FunctionReference etc. from script_serial) rather than re-reading binary | Pattern 2, Pitfall 5 | If node type readers re-read binary, they'll read garbage since archive position is past script_serial data |
| A2 | `from_archive` methods in models need additional parameters beyond `archive` (name_map, summary, export_map, import_map) — the stubs only take `archive: FArchive` | Pattern 1 | The current stub signatures are incompatible with actual serializer function signatures |
| A3 | `read_pin_reference` and `read_pin_array` belong in `serializers/graph.py` (they are graph pin helpers, not standalone utilities) | Project Structure | Misplacement could cause import complexity |

## Open Questions

1. **`from_archive` signature mismatch:** The current stubs in `models/core.py` only take `archive: FArchive`. But actual serializers like `read_ue_graph_pin` need `name_map`, `summary`, `export_map`, `import_map`. Should the `from_archive` signatures be extended, or should a separate wrapper be used?
   - What we know: D-02 says "from_archive stubs call serializers/graph.py independent functions"
   - What's unclear: Whether the method signature changes are in scope for this phase
   - Recommendation: Extend `from_archive` signatures to accept the additional context parameters. This is a breaking change but necessary for the delegation pattern.

2. **`serializers/graph.py` file size:** The old code's graph functions span ~1500 lines (L3095-4679). Even with FText extraction, `serializers/graph.py` will be large.
   - What we know: D-03/D-04 lock all binary readers in `serializers/graph.py`
   - What's unclear: Whether to split into `serializers/graph.py` + `serializers/pin_serializers.py`
   - Recommendation: Keep single file per D-03/D-04 decisions. If file exceeds 600 lines, the planner can consider splitting.

3. **Test binary data synthesis:** Many tests in `test_graph_parsing.py` are skipped with "需要合成二进制数据". Should Phase 31 include synthetic binary data generation, or leave for a separate test phase?
   - What we know: TEST-01 requires all existing tests to pass. TEST-02 requires new module unit tests.
   - What's unclear: Whether the planner expects synthetic data as part of Phase 31
   - Recommendation: Synthetic data generation is out of scope for this phase. Tests should be updated to use real Lyra assets or marked as integration tests.

## Environment Availability

Step 2.6: SKIPPED (no external dependencies identified — this is a pure code migration phase with no new tools, runtimes, or services required)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (dev dependency) |
| Config file | None — standard pytest discovery |
| Quick run command | `pytest tests/test_graph_parsing.py -v --tb=short` |
| Full suite command | `pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MOD-08 | Define core data models | unit | `pytest tests/test_graph_parsing.py::TestUEdGraphBasic -v` | Yes |
| MOD-09 | Avoid circular imports | unit | `python -c "from uasset_read.graph import extract_blueprint_graphs"` | Yes (new import) |
| TEST-01 | All existing tests pass | integration | `pytest tests/ -v --tb=short` | Yes |

### Sampling Rate
- **Per task commit:** `pytest tests/test_graph_parsing.py -v --tb=short`
- **Per wave merge:** `pytest tests/ --tb=short`
- **Phase gate:** Full suite green (411+ passed) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_graph_parsing.py` — many tests skipped, need real asset paths or synthetic data
- [ ] Import path updates needed — test currently imports from `uasset_read` top-level, but graph module is new
- [ ] Graph binary reader unit tests — no synthetic data generators exist for UE graph format

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — file parser, no auth |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Safety constants (MAX_PINS_PER_NODE etc.), bounds checking, ParseError on invalid data |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for UE Binary Parsing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious array count (DoS) | Denial of Service | MAX_LINKEDTO_PER_PIN, MAX_NODES_PER_GRAPH, MAX_PINS_PER_NODE bounds checks |
| Offset manipulation (file corruption) | Tampering | FArchive.validate_offset, validate_size |
| Negative size/count fields | Tampering | Explicit < 0 checks before loops |
| Infinite PropertyTag loops | Denial of Service | "None" terminator check, MAX_PROPERTY_COUNT loop limit |

## Sources

### Primary (HIGH confidence)
- **Codebase analysis** — `uasset_read.py` L3095-4679, L6400-7115: All graph parsing and flow building functions read and analyzed
- **Codebase analysis** — `src/uasset_read/constants.py`: Safety constants, START_EVENT_TYPES, CONTROL_FLOW_NODES already present
- **Codebase analysis** — `src/uasset_read/models/core.py`: Dataclass stubs with `raise NotImplementedError("Phase 31")`
- **Codebase analysis** — `src/uasset_read/models/node_types.py`: 5 node type subclasses with stubs
- **Codebase analysis** — `tests/test_graph_parsing.py`: 527 lines of test contract, many skipped

### Secondary (MEDIUM confidence)
- **Context.md L57-95** — Canonical references to UE source files (EdGraph.cpp, EdGraphPin.cpp L1838-1964, EdGraphNode.h, K2Node.h)
- **uasset_read.py docstrings** — Serialization order documented per UE source code

### Tertiary (LOW confidence)
- UE source code references in docstrings are from training knowledge and have not been independently verified against the actual UE 5.7 source at `E:\Develop\lib\UnrealEngine\`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — No external libraries, only existing internal modules verified by reading source
- Architecture: HIGH — Locked by D-01 to D-09 decisions in CONTEXT.md, migration source thoroughly analyzed
- Pitfalls: HIGH — Based on documented FIXes in uasset_read.py (Phase 22, 28a) with real asset debugging evidence
- Migration scope: HIGH — All functions mapped by line reference, signatures understood

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (30 days — stable internal codebase, no external dependencies)
