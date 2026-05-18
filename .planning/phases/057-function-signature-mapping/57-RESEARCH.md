# Phase 57: 函数签名映射 - Research

**Researched:** 2026-05-18
**Domain:** Blueprint function graph to C++ function signature/call statement mapping
**Confidence:** HIGH

## Summary

Phase 57 builds on Phase 56's `cpp_type_mapper` and `CppClassIR` infrastructure, plus v9.0's `build_function_graphs` output. The primary task is extracting three kinds of C++ output from blueprint graph nodes: (1) function declarations from `K2Node_FunctionEntry` + `K2Node_Event`, (2) call statements from `K2Node_CallFunction`, and (3) UFUNCTION macro specifiers inferred from pin structure.

The pipeline is well-defined: blueprint graphs are already parsed into `UEdGraphNode` objects with typed pins, and the type mapper (`ue_path_to_cpp_type`) handles Blueprint-to-C++ type conversion. The main gap is the extraction logic that bridges graph nodes to `CppMethodIR` and `CppCallStatement` data models.

**Primary recommendation:** Add `CppMethodIR` and `CppCallStatement` to `cpp_json_ir.py`, implement `extract_cpp_functions()` in `cpp_gen/extract_cpp_skeleton.py` (alongside `extract_cpp_class_skeleton`), and extend `cpp_header_formatter.py` to render methods and call statements.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Function signature extraction (FunctionEntry) | API / Backend (cpp_gen) | — | Reads graph nodes, produces IR |
| Call statement extraction (CallFunction) | API / Backend (cpp_gen) | — | Reads graph nodes, produces IR |
| Event override function extraction | API / Backend (cpp_gen) | — | Reads Event nodes with bOverrideFunction |
| UFUNCTION specifier inference | API / Backend (cpp_gen) | — | Pin structure analysis |
| C++ type conversion | cpp_type_mapper (existing) | — | Reused from Phase 56 |
| C++ header rendering | cpp_header_formatter (existing) | — | Extended to render methods |

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-57-01: 函数签名提取 — 双源交叉验证**
- 优先从 `blueprint_functions`（上游 `BlueprintFunction` 模型）获取签名
- 从 `K2Node_FunctionEntry` 的 `UserDefinedPin` 提取参数作为验证
- 两者不一致时：记录 `logger.warning`，以 `blueprint_functions` 为准
- 无 `blueprint_functions` 时：Fallback 到 FunctionEntry 引脚
- FunctionEntry 引脚方向全部为 `EGPD_Output`（参数是函数的输出给内部节点），C++ 中统一为 input 参数

**D-57-02: 输出形态 — IR methods + 独立调用语句参考**
- 填充 `CppClassIR.methods`：每个蓝图函数对应一个 `CppMethodIR` 数据模型
- 独立调用语句参考：从 `K2Node_CallFunction` 节点提取 C++ 调用语句
- 新模块：`cpp_gen/extractors/cpp_call_extractor.py`（暂定名）

**D-57-03: UFUNCTION 宏推断 — 基于引脚结构**
- 有 `exec` 输入 pin + 有 `then` 输出 pin → `BlueprintCallable`
- 无 `exec` pin（仅有数据 pin）→ `BlueprintPure`
- `K2Node_Event` + `bOverrideFunction=True` → 不加 UFUNCTION（override 方法）
- `K2Node_FunctionEntry` 且 `ExtraFlags` 含 event 标志 → `BlueprintImplementableEvent`

**D-57-04: Event 覆盖函数 — 需要处理**
- `K2Node_Event` 且 `bOverrideFunction=True` 的节点
- 从 `EventReference.MemberName` 提取函数名
- 从 Event 节点的输出引脚提取参数
- 标记为 `is_override=True`，不生成 UFUNCTION 宏

**D-57-05: CallFunction 调用语句 — 不推断 Super:: 前缀**
- `FunctionReference.MemberName` → 调用方法名
- `bSelfContext=True` → `this->MethodName(Args)`
- `bSelfContext=False` → 从 self pin 推导目标变量名
- **不自动推断 `Super::` 前缀**
- 参数顺序：按引脚定义顺序，跳过 `exec`、`then`、`self` 三个特殊引脚

**D-57-06: 参数方向推断 — 从 PinType 字段**
- `PinType.bIsReference=True` + `PinType.bIsConst=True` → `const Type&`
- `PinType.bIsReference=True` + `PinType.bIsConst=False` → `Type&`
- 其余 → 值传递 `Type`

### Deferred Ideas (OUT OF SCOPE)
- 函数体逻辑翻译 (Phase 58)
- 组件初始化代码 (Phase 59)
- 纯函数内联表达式 (Phase 58)
- UFUNCTION 类别手动标注 (Phase 58+)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FUNC-01 | 每个蓝图函数图节点输出为完整的 C++ 函数声明 | FunctionEntry/Event pin analysis, cpp_type_mapper integration, CppMethodIR design |
| FUNC-02 | 函数调用节点输出为等价 C++ 调用语句格式 | CallFunction node analysis, bSelfContext handling, CallStatementIR design |
| FUNC-03 | 每个函数声明包含正确的 UFUNCTION 宏 | Pin structure analysis (exec/then presence), ExtraFlags analysis, Event override handling |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| (No new external packages) | — | Phase 57 uses existing project modules only | Builds entirely on Phase 56 infrastructure |

### Reused Project Modules
| Module | Purpose | Source |
|--------|---------|--------|
| `cpp_type_mapper.ue_path_to_cpp_type` | Blueprint pin type → C++ type | Phase 56, `src/uasset_read/cpp_gen/` |
| `cpp_json_ir.CppClassIR` | IR container with `methods: List` field | Phase 56, already has empty methods list |
| `cpp_header_formatter.format_cpp_header` | C++ header text generation | Phase 56, needs extension for methods |
| `graph.flow_builder.build_function_graphs` | Function graph extraction with signatures | v9.0, provides input data |
| `models.node_types.K2NodeFunctionEntry` | FunctionEntry node model with extra_flags | Phase 52 |
| `models.node_types.K2NodeEvent` | Event node model with b_override_function | Phase 52 |
| `models.node_types.K2NodeCallFunction` | CallFunction node model | Phase 52 |
| `models.core.FEdGraphPinType` | Pin type with bIsReference, bIsConst, PinCategory, PinSubCategory | Phase 31 |
| `models.core.FMemberReference` | Function/event reference with member_name, b_self_context | Phase 31 |
| `models.blueprint.BlueprintFunction` | Blueprint function metadata with return_type, parameters | Phase 31 |

## Architecture Patterns

### Data Flow: FunctionEntry → C++ Declaration

```
.uasset binary
  → FArchive + read_ue_graph_node()
    → UEdGraphNode(class_name="K2Node_FunctionEntry")
      → node_data["function_reference"].member_name = "Move"
      → pins: [exec "then"(Output), real "Left / Right"(Output), real "Forward / Backward"(Output)]
      → UserDefinedPin metadata in node_data/raw_properties
        ↓
  build_function_graphs(graphs, blueprint_functions)
    → function_graphs[i].signature = {"return_type": "", "parameters": [...]}
        ↓
  extract_cpp_functions(graphs, blueprint_functions)  [NEW - Phase 57]
    → CppMethodIR(name="Move", return_type="void", params=[...], specifiers=["BlueprintCallable"])
    → CppClassIR.methods.append(CppMethodIR)
        ↓
  format_cpp_header(ir)  [EXTENDED - Phase 57]
    → "    UFUNCTION(BlueprintCallable)\n    void Move(double LeftRight, double ForwardBackward);"
```

### Data Flow: CallFunction → C++ Call Statement

```
.uasset binary
  → FArchive + read_ue_graph_node()
    → UEdGraphNode(class_name="K2Node_CallFunction")
      → node_data["function_reference"] = FMemberReference(
          member_name="Jump",
          b_self_context=True,
          member_parent="/Script/CoreUObject.Class'/Script/Engine.Character'"
        )
      → pins: [exec "execute"(Input), exec "then"(Output), object "self", ...data pins...]
        ↓
  extract_cpp_call_statements(graphs)  [NEW - Phase 57]
    → CppCallStatement(method_name="Jump", target="this", args=[], is_self_context=True)
        ↓
  format_cpp_call_statement(stmt)  [NEW - Phase 57]
    → "this->Jump();"
```

### System Architecture Diagram

```
                    ┌──────────────────────────────────────┐
                    │        .uasset binary file           │
                    └──────────────┬───────────────────────┘
                                   │ FArchive
                                   ▼
                    ┌──────────────────────────────────────┐
                    │    read_ue_graph_node() [existing]   │
                    │  → UEdGraphNode typed nodes          │
                    └──────┬───────────────┬───────────────┘
                           │               │
              ┌────────────▼────┐  ┌───────▼──────────────┐
              │ FunctionEntry / │  │  CallFunction nodes  │
              │   Event nodes   │  │  (all in graphs[])   │
              └────────┬────────┘  └───────┬──────────────┘
                       │                   │
              ┌────────▼───────────────────▼──────────────┐
              │     extract_cpp_functions()  [NEW Phase57]│
              │  - FunctionEntry → CppMethodIR            │
              │  - Event(bOverride) → CppMethodIR         │
              │  - CallFunction → CppCallStatement        │
              │  - Pin structure → UFUNCTION specifiers   │
              │  - PinType → C++ type + direction         │
              └────────┬──────────────────┬───────────────┘
                       │                  │
              ┌────────▼──────┐  ┌────────▼──────────────┐
              │ CppClassIR    │  │ List[CppCallStatement]│
              │ .methods[]    │  │ (separate output)     │
              └───────┬───────┘  └────────┬──────────────┘
                      │                   │
              ┌───────▼───────────────────▼───────────────┐
              │     format_cpp_header() [EXTENDED Phase57]│
              │  - Renders methods into .h text           │
              │  - Renders call statements as .cpp ref    │
              └────────────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │   .h header text + .cpp call ref    │
                    └─────────────────────────────────────┘
```

### Recommended Project Structure

```
src/uasset_read/cpp_gen/
├── __init__.py                    # Extended exports (add CppMethodIR, CppCallStatement)
├── cpp_type_mapper.py             # EXISTING - reused
├── cpp_uproperty_mapper.py        # EXISTING - reused
├── extract_cpp_skeleton.py        # EXTENDED - add extract_cpp_functions()
└── formatters/
    ├── __init__.py                # Extended exports
    ├── cpp_json_ir.py             # EXTENDED - add CppMethodIR, CppCallParameter, CppCallStatement
    ├── cpp_header_formatter.py    # EXTENDED - render methods + call statements
    └── extractors/
        ├── cpp_function_signature_extractor.py  # NEW - FunctionEntry/Event → MethodIR
        └── cpp_call_extractor.py                # NEW - CallFunction → CallStatement
```

**Note on module placement:** The CONTEXT.md suggests a new `extractors/` subdirectory. However, given the small scope of Phase 57 (single extraction function for both signatures and calls), placing the extraction logic directly in `extract_cpp_skeleton.py` as `extract_cpp_functions()` alongside `extract_cpp_class_skeleton()` is simpler and consistent with the existing pattern. A separate `extractors/` directory can be created in Phase 58 when body translation requires more complex module organization. The data models (`CppMethodIR`, `CppCallStatement`) should be added to `cpp_json_ir.py`.

### Pattern 1: Signature Extraction from FunctionEntry Pins

**What:** Extract function signature (name, parameters, return type) from `K2Node_FunctionEntry` nodes.

**When to use:** Primary extraction path when `blueprint_functions` is not available.

**Implementation:**
```python
# Pseudocode structure based on existing patterns:
def _extract_signature_from_function_entry(fe_node: UEdGraphNode) -> Dict:
    """从 FunctionEntry 节点引脚提取签名。"""
    # 1. Get function name from node_data["function_reference"]
    nd = fe_node.node_data
    fr = nd.get("function_reference") if isinstance(nd, dict) else None
    func_name = fr.member_name if fr else "Unknown"

    # 2. Extract parameters from pins (EGPD_Output pins that are NOT exec)
    params = []
    for pin in fe_node.pins:
        if pin.pin_type.pin_category == "exec":
            continue  # Skip exec pins
        if pin.direction != 1:
            continue  # Skip non-output pins (FunctionEntry pins are all Output)
        # UserDefinedPin provides canonical name and type
        cpp_type = ue_path_to_cpp_type(pin.pin_type.pin_subcategory or pin.pin_type.pin_category)
        params.append({
            "name": _sanitize_pin_name(pin.pin_name),  # "Left / Right" → "LeftRight"
            "cpp_type": cpp_type,
        })

    return {"name": func_name, "parameters": params}
```

### Pattern 2: UFUNCTION Specifier Inference from Pin Structure

**What:** Determine UFUNCTION macro based on pin presence/absence.

**When to use:** Always — every blueprint function needs a specifier.

**Implementation:**
```python
def _infer_ufunction_specifiers(node: UEdGraphNode, is_event_override: bool = False) -> List[str]:
    if is_event_override:
        return []  # Override methods don't get UFUNCTION

    has_exec_input = any(
        p.pin_type.pin_category == "exec" and p.direction == 0  # Input
        for p in node.pins
    )
    has_exec_output = any(
        p.pin_type.pin_category == "exec" and p.direction == 1  # Output
        for p in node.pins
    )

    if has_exec_input and has_exec_output:
        return ["BlueprintCallable"]
    elif not has_exec_input and not has_exec_output:
        return ["BlueprintPure"]
    else:
        # Mixed: has exec output but no exec input (common for event handlers)
        return ["BlueprintCallable"]
```

### Pattern 3: Call Statement Generation

**What:** Convert `K2Node_CallFunction` to C++ call text.

**When to use:** Every CallFunction node in the event graph.

**Implementation:**
```python
def _extract_call_statement(node: UEdGraphNode) -> Dict:
    nd = node.node_data
    fr = nd.get("function_reference")
    if not fr or not fr.member_name:
        return None

    b_self = fr.b_self_context
    target = "this" if b_self else _derive_target_from_self_pin(node.pins)

    # Collect data pins (skip exec, then, self)
    args = []
    for pin in node.pins:
        cat = pin.pin_type.pin_category
        if cat == "exec":
            continue
        if pin.pin_name == "self":
            continue
        args.append(pin.pin_name)

    return {
        "method_name": fr.member_name,
        "target": target,
        "target_type": "pointer" if not b_self else "this",
        "args": args,
    }
```

### Anti-Patterns to Avoid
- **Do NOT infer Super:: prefix:** Even if `PinSubCategoryObject` points to a parent class, output `this->Jump()` not `Super::Jump()`. Per D-57-05.
- **Do NOT use ExtraFlags bit parsing for UFUNCTION inference:** The value `201457664` (0x0C020000) is stored in `raw_properties` but not passed through to `K2NodeFunctionEntry.extra_flags`. Pin structure analysis is more reliable than bit parsing for UFUNCTION inference. Per 52-RESEARCH.md A3, ExtraFlags meaning was left unresolved.
- **Do NOT skip Event nodes:** Event override functions (D-57-04) produce MethodIR entries just like FunctionEntry functions, but with `is_override=True` and no UFUNCTION specifiers.
- **Do NOT duplicate type mapping:** Always use `ue_path_to_cpp_type()` from `cpp_type_mapper` — do not create a separate type mapping table.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Blueprint type → C++ type | New type mapping dict | `cpp_type_mapper.ue_path_to_cpp_type()` | Phase 56 already has comprehensive dict (50+ entries) with heuristic fallback |
| UFUNCTION macro inference | Heuristic bit parsing of ExtraFlags | Pin structure analysis (exec pin presence) | ExtraFlags=201457664 is fixed across test assets; pin structure is direct evidence |
| C++ identifier sanitization | Manual string replace | `_sanitize_class_name()` pattern from `cpp_header_formatter.py` | Already handles illegal chars, leading digits, UE naming conventions |
| Pin name sanitization (e.g., "Left / Right" → "LeftRight") | Raw pin names in C++ output | Regex-based identifier sanitization | C++ identifiers cannot contain spaces or `/` |

**Key insight:** The pin structure approach for UFUNCTION inference is more reliable than bit-parsing ExtraFlags because the ExtraFlags value in test assets (0x0C020000) was never fully decoded, while the pin structure directly encodes the function's execution contract.

## Code Examples

### FunctionEntry Node Structure (Move function)

```python
# From reference data, this is what the parsed node looks like:
fe_node = K2NodeFunctionEntry(
    node_guid="0A89B7514654265DD7C4A0BC3D2433F9",
    class_name="K2Node_FunctionEntry",
    node_data={
        "function_reference": FMemberReference(
            member_name="Move",
            member_parent=None,  # Not set for custom functions
            b_self_context=False,
        ),
    },
    extra_flags=201457664,  # Stored in raw_properties, not yet in node_data.extra_flags
    b_is_editable=True,
    pins=[
        UEdGraphPin(pin_name="then",      pin_type=FEdGraphPinType(pin_category="exec"), direction=1),  # EGPD_Output
        UEdGraphPin(pin_name="Left / Right",  pin_type=FEdGraphPinType(pin_category="real", pin_subcategory="double"), direction=1),
        UEdGraphPin(pin_name="Forward / Backward", pin_type=FEdGraphPinType(pin_category="real", pin_subcategory="double"), direction=1),
    ],
)
# Expected C++: UFUNCTION(BlueprintCallable) void Move(double LeftRight, double ForwardBackward);
```

### CallFunction Node Structure (Jump call)

```python
call_node = K2NodeCallFunction(
    node_guid="F923268743B7B52D669FFB960CA79833",
    class_name="K2Node_CallFunction",
    node_data={
        "function_reference": FMemberReference(
            member_name="Jump",
            member_parent=None,
            b_self_context=True,
        ),
        "b_defaults_to_pure": False,
    },
    pins=[
        UEdGraphPin(pin_name="execute", pin_type=FEdGraphPinType(pin_category="exec"), direction=0, linked_to_raw=[...]),
        UEdGraphPin(pin_name="then",    pin_type=FEdGraphPinType(pin_category="exec"), direction=1),
        UEdGraphPin(pin_name="self",    pin_type=FEdGraphPinType(pin_category="object", pin_subcategory_object="/Script/CoreUObject.Class'/Script/Engine.Character'")),
        # No data pins for Jump() — zero-argument function
    ],
)
# Expected C++: this->Jump();
```

### CallFunction with Arguments (Move call)

```python
call_node = K2NodeCallFunction(
    node_guid="C8057E68458317EB785601A49208A829",
    node_data={
        "function_reference": FMemberReference(member_name="Move", b_self_context=True),
        "b_defaults_to_pure": False,
    },
    pins=[
        UEdGraphPin(pin_name="execute", pin_type=..., direction=0, linked_to_raw=[...]),
        UEdGraphPin(pin_name="then",    pin_type=..., direction=1),
        UEdGraphPin(pin_name="self",    pin_type=FEdGraphPinType(pin_category="object", pin_subcategory="self")),
        UEdGraphPin(pin_name="Left / Right",  pin_type=FEdGraphPinType(pin_category="real", pin_subcategory="double"), direction=0, linked_to_raw=[...]),
        UEdGraphPin(pin_name="Forward / Backward", pin_type=FEdGraphPinType(pin_category="real", pin_subcategory="double"), direction=0, linked_to_raw=[...]),
    ],
)
# Expected C++: this->Move(LeftRight, ForwardBackward);
```

### Event Override Node Structure (Primary Thumbstick)

```python
event_node = K2NodeEvent(
    node_guid="4C15CD904D7C99C3D86790857331A576",
    class_name="K2Node_Event",
    node_data={
        "event_reference": FMemberReference(
            member_name="Primary Thumbstick",
            member_parent="/Script/Engine.BlueprintGeneratedClass'/Game/Input/Touch/BPI_TouchInterface.BPI_TouchInterface_C'",
            b_self_context=False,
        ),
        "b_override_function": True,
    },
    pins=[
        UEdGraphPin(pin_name="OutputDelegate", pin_type=FEdGraphPinType(pin_category="delegate"), direction=1),
        UEdGraphPin(pin_name="then", pin_type=FEdGraphPinType(pin_category="exec"), direction=1),
        UEdGraphPin(pin_name="Axis", pin_type=FEdGraphPinType(pin_category="struct", pin_subcategory_object="/Script/CoreUObject.Vector2D"), direction=1,
                    sub_pins=[...]),  # Hidden parent pin
        UEdGraphPin(pin_name="Axis_X", pin_type=FEdGraphPinType(pin_category="real", pin_subcategory="double"), direction=1),  # SubPin, visible
        UEdGraphPin(pin_name="Axis_Y", pin_type=FEdGraphPinType(pin_category="real", pin_subcategory="double"), direction=1),  # SubPin, visible
    ],
)
# Expected C++: void PrimaryThumbstick(double Axis_X, double Axis_Y);  (override, no UFUNCTION)
```

### Pin Direction and Reference Mapping (D-57-06)

```python
# Pin type → C++ type + direction mapping:
_pin_direction_map = {
    # (bIsReference, bIsConst) → C++ parameter modifier
    (False, False): lambda t: t,              # Value: "double"
    (True,  False): lambda t: f"{t}&",        # Mutable ref: "double&"
    (True,  True):  lambda t: f"const {t}&",  # Const ref: "const double&"
    # (False, True) is unusual but possible — treat as value
    (False, True):  lambda t: t,
}
```

### Blueprint Pin Category → C++ Type Mapping (Cross-Reference)

From `cpp_type_mapper.py` (verified by reading `src/uasset_read/cpp_gen/cpp_type_mapper.py`):

| PinCategory | PinSubCategory | C++ Type | Source |
|-------------|---------------|----------|--------|
| `real` | `double` | `double` | `UE_TO_CPP_TYPE_MAP["double"]` |
| `real` | `float` | `float` | `UE_TO_CPP_TYPE_MAP["float"]` |
| `bool` | — | `bool` | `UE_TO_CPP_TYPE_MAP["bool"]` |
| `object` | `/Script/Engine.XXX` | `UXXX*`/`AXXX*` | `ue_path_to_cpp_type()` |
| `struct` | `/Script/CoreUObject.Vector` | `FVector` | `ue_path_to_cpp_type()` |
| `struct` | `/Script/CoreUObject.Vector2D` | `FVector2D` | `ue_path_to_cpp_type()` |
| `exec` | — | (skip) | N/A |
| `delegate` | — | (skip, Event only) | N/A |
| `string` | — | `FString` | `UE_TO_CPP_TYPE_MAP["string"]` |
| `name` | — | `FName` | `UE_TO_CPP_TYPE_MAP["name"]` |
| `text` | — | `FText` | `UE_TO_CPP_TYPE_MAP["text"]` |
| `byte` | — | `uint8` | `UE_TO_CPP_TYPE_MAP["byte"]` |
| `int` | — | `int32` | `UE_TO_CPP_TYPE_MAP["int"]` |

**Important note on `PinSubCategory` vs `PinSubCategoryObject`:**
- `PinSubCategory` is a string (e.g., `"double"`, `"float"`) used for primitive types
- `PinSubCategoryObject` is a `FPackageIndex` (int32) that resolves to a class/struct path (e.g., `/Script/CoreUObject.Class'/Script/Engine.Character'`)
- For `object` pins: use `PinSubCategoryObject` resolved path, NOT `PinSubCategory`
- For `struct` pins: similarly use `PinSubCategoryObject` for named structs like Vector2D

The `ue_path_to_cpp_type()` function handles both string types and path types. For PinSubCategoryObject, the path must first be resolved via linker (if available) or taken from the raw text reference.

## Gap Analysis

### What Already Exists (No Work Needed)

| Capability | Status | Location |
|-----------|--------|----------|
| Blueprint type → C++ type | ✅ Complete | `cpp_type_mapper.py` |
| CppClassIR with empty methods list | ✅ Complete | `cpp_json_ir.py` |
| K2Node_FunctionEntry parsing | ✅ Complete | Phase 52, `node_types.py` + `graph.py` |
| K2Node_Event parsing (with b_override_function) | ✅ Complete | Phase 52 |
| K2Node_CallFunction parsing | ✅ Complete | Phase 52 |
| FEdGraphPinType with bIsReference/bIsConst | ✅ Complete | `models/core.py` |
| FMemberReference with member_name/b_self_context | ✅ Complete | `models/core.py` |
| BlueprintFunction model with return_type/parameters | ✅ Complete | `models/blueprint.py` |
| build_function_graphs() with signature dict | ✅ Complete | `flow_builder.py:844` |
| cpp_header_formatter for properties | ✅ Complete | `cpp_header_formatter.py` |
| Test infrastructure (pytest + fixtures) | ✅ Complete | `tests/test_output_formatting.py` |

### What Phase 57 Must Build

| Component | Effort | Description |
|-----------|--------|-------------|
| `CppMethodIR` dataclass | Low | Method declaration IR (name, return_type, parameters, specifiers, is_override) |
| `CppCallParameter` dataclass | Low | Single parameter in a method/call |
| `CppCallStatement` dataclass | Low | Call statement IR (method_name, target, args, is_self_context) |
| `extract_cpp_functions()` function | Medium | Iterate graphs, extract FunctionEntry/Event/CallFunction nodes, produce CppMethodIR and CppCallStatement |
| Pin name sanitization | Low | `"Left / Right"` → `"LeftRight"`, handle special chars |
| UFUNCTION specifier inference | Low | Pin structure analysis (exec input/output presence) |
| Event override extraction | Medium | Handle bOverrideFunction=True, SubPins for struct parameters |
| `cpp_header_formatter` extension | Medium | Render methods into .h, call statements into .cpp reference |
| Integration with `extract_cpp_class_skeleton` | Low | Call `extract_cpp_functions()` and populate `CppClassIR.methods` |
| Tests | Medium | Unit tests for extraction, golden-path test with BP_FirstPersonCharacter |

### Gap: ExtraFlags Not Properly Propagated

**Issue:** In `read_ue_graph_node()` (graph.py:874), `ExtraFlags` is read as `raw_properties["ExtraFlags"] = archive.read_i32()`. For `K2Node_FunctionEntry`, `create_node_from_archive` passes `raw_properties` only to the "unknown type" branch (line 744-746). For known types like `K2Node_FunctionEntry`, `read_k2node_functionentry()` only receives `function_reference` from `node_refs` — the `extra_flags` value is NOT passed to `base_node.extra_flags`.

**Impact:** The `K2NodeFunctionEntry` model has an `extra_flags: int = 0` field, but it always stays at default `0` because the serializer never populates it.

**Resolution for Phase 57:** Since D-57-03 recommends pin-based UFUNCTION inference (which does not require ExtraFlags), this gap does not block Phase 57. However, if BlueprintImplementableEvent detection via ExtraFlags is desired, the serializer needs a fix to pass ExtraFlags to the node. This can be addressed as a separate task or deferred.

### Gap: UserDefinedPin Not in node_data

**Issue:** The reference data shows `CustomProperties UserDefinedPin` entries for FunctionEntry nodes. These are not yet explicitly parsed into `node_data`. They exist as raw pin data in the `pins` list but the `UserDefinedPin` custom property metadata is not extracted.

**Impact:** Phase 57 needs parameter name/type information. Since the pins already carry `pin_type` (PinCategory, PinSubCategory), the primary source for signature extraction is the pins themselves, not UserDefinedPin. UserDefinedPin is a validation source per D-57-01 but not the primary source.

**Resolution:** Use `pins` as primary extraction source. If UserDefinedPin data is available in `raw_properties` (as parsed text), use it for cross-validation.

## Common Pitfalls

### Pitfall 1: Exec Pin Direction Confusion
**What goes wrong:** Confusing Input (direction=0) vs Output (direction=1) for exec pins when determining BlueprintCallable vs BlueprintPure.
**Why it happens:** FunctionEntry nodes have `then` (exec Output) but NO exec Input pin — yet they are still BlueprintCallable (impure).
**How to avoid:** For FunctionEntry nodes, the presence of ANY exec Output pin (`then`) means the function is impure (Callable), not Pure. Pure functions have NO exec pins at all.
**Warning signs:** A FunctionEntry with only `then` pin being classified as BlueprintPure.

### Pitfall 2: Event Override Functions Getting UFUNCTION
**What goes wrong:** Generating `UFUNCTION(BlueprintCallable)` for Event override methods.
**Why it happens:** Not checking `bOverrideFunction` before applying UFUNCTION inference.
**How to avoid:** First check: `if node.class_name == "K2Node_Event" and node.node_data.get("b_override_function")` → skip UFUNCTION, mark `is_override=True`.
**Warning signs:** `UFUNCTION()` appearing before an override function declaration.

### Pitfall 3: SubPin Parameters Duplicated
**What goes wrong:** Extracting both the parent struct pin ("Axis") AND its sub-pins ("Axis_X", "Axis_Y") as separate parameters.
**Why it happens:** Event nodes with struct parameters have both hidden parent pins and visible sub-pins.
**How to avoid:** Skip pins that are parent pins of SubPins (check `parent_pin` field) OR skip pins with `bHidden=True`. Only extract visible sub-pins.
**Warning signs:** `void PrimaryThumbstick(FVector2D Axis, double Axis_X, double Axis_Y)` — duplicated parameters.

### Pitfall 4: Pin Name Sanitization
**What goes wrong:** Using raw pin names like `"Left / Right"` as C++ parameter names.
**Why it happens:** Pin names in UE are display-friendly and contain spaces, slashes, etc.
**How to avoid:** Apply identifier sanitization: replace non-alphanumeric chars with underscore, collapse consecutive underscores, remove leading/trailing underscores. `"Left / Right"` → `"Left_Right"` or `"LeftRight"`.
**Warning signs:** Invalid C++ identifiers in output.

### Pitfall 5: Missing PinSubCategoryObject Resolution
**What goes wrong:** For `object` and `struct` type pins, using `PinSubCategory` (empty string) instead of resolving `PinSubCategoryObject` (FPackageIndex) to the actual type path.
**Why it happens:** `PinSubCategoryObject` is a PackageIndex that requires linker resolution. Without linker, it's just an integer.
**How to avoid:** For Phase 57, the text reference file provides the resolved paths (e.g., `PinSubCategoryObject="/Script/CoreUObject.Class'/Script/Engine.Character'"`). The extractor should use `ue_path_to_cpp_type()` which handles both direct strings and resolved paths. When PackageIndex resolution is available (linker mode), use it.
**Warning signs:** Empty or incorrect C++ types for object/struct parameters.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual byte reading for node data | FArchive PropertyTag-based parsing | Phase 52 | Structured, type-safe node data extraction |
| UberEdGraph detection for function graphs | FunctionEntry node presence in EdGraph | Phase 52 | More reliable function graph detection |
| No UFUNCTION inference | Pin structure-based inference | Phase 57 (new) | Automatic macro generation |
| ExtraFlags bit parsing for function type | Pin presence analysis (exec in/out) | Phase 57 (new) | More reliable, version-independent |
| Raw pin names in output | Sanitized C++ identifiers | Phase 57 (new) | Valid C++ output |

**Deprecated/outdated:**
- `ExtraFlags` bit parsing for UFUNCTION inference: Never fully decoded (0x0C020000 meaning unresolved). Pin structure is the recommended approach per D-57-03.
- `bDefaultsToPureFunc` as sole Pure indicator: The `bDefaultsToPureFunc` field on CallFunction nodes indicates default behavior, not actual purity. Pin structure is the authoritative source.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ExtraFlags=201457664` bit meaning is not needed for Phase 57 — pin structure is sufficient | UFUNCTION Specifier Inference | If pin structure inference is insufficient for some edge cases (e.g., BlueprintImplementableEvent vs BlueprintCallable), ExtraFlags parsing may be needed |
| A2 | FunctionEntry nodes always have `then` exec output pin when the function is impure | Pitfall 1 | If there exist impure functions without exec output pins, BlueprintCallable inference would incorrectly return BlueprintPure |
| A3 | The `extractors/` subdirectory can be deferred to Phase 58 | Architecture Pattern — module placement | If Phase 57 extraction logic grows complex, splitting into subdirectory earlier may be beneficial |
| A4 | `UserDefinedPin` data is not required for primary signature extraction — pins themselves are sufficient | Gap Analysis | If pins carry incomplete type information in some cases, UserDefinedPin may be needed as primary source |

## Open Questions

1. **BlueprintImplementableEvent detection:** D-57-03 mentions "ExtraFlags contains event flag" for BlueprintImplementableEvent. Since ExtraFlags is not properly propagated to the node model (Gap: ExtraFlags), how should Phase 57 detect this case?
   - What we know: Test assets have ExtraFlags=201457664 (0x0C020000) for all custom functions (Move, Aim).
   - What's unclear: Whether this value encodes BlueprintImplementableEvent, BlueprintCallable, or both.
   - Recommendation: For Phase 57, default to BlueprintCallable for all custom functions. If BlueprintImplementableEvent detection is needed, fix the serializer to propagate ExtraFlags first (can be a separate small task).

2. **Const function detection:** BlueprintFunction model has `is_const: bool`, but there's no corresponding pin indicator for const methods.
   - What we know: `BlueprintFunction` dataclass has `is_const` field.
   - What's unclear: How const is determined from the .uasset binary.
   - Recommendation: Skip const method detection for Phase 57 — add `const` suffix to method declarations in Phase 58 when function body analysis provides more context.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All code | ✓ | 3.14.3 | — |
| pytest | Tests | ✓ | Installed via dev extras | — |
| Phase 56 modules | Type mapping, IR, header formatting | ✓ | v10.0 Phase 56 complete | — |
| v9.0 function_graphs | Input data | ✓ | build_function_graphs() | — |
| BP_FirstPersonCharacter.uasset | Test asset | ✓ | UE5.7 test asset | — |

**No missing dependencies.**

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `python -m pytest tests/test_cpp_gen.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUNC-01 | FunctionEntry → C++ declaration with correct name, params, types, return type | unit | `pytest tests/test_cpp_gen.py::test_extract_cpp_functions_move -x` | ❌ Wave 0 |
| FUNC-01 | Event override → C++ declaration with is_override=True, no UFUNCTION | unit | `pytest tests/test_cpp_gen.py::test_extract_event_override -x` | ❌ Wave 0 |
| FUNC-02 | CallFunction → C++ call statement (self-context) | unit | `pytest tests/test_cpp_gen.py::test_extract_call_statement_jump -x` | ❌ Wave 0 |
| FUNC-02 | CallFunction with args → call statement with parameters | unit | `pytest tests/test_cpp_gen.py::test_extract_call_statement_move -x` | ❌ Wave 0 |
| FUNC-03 | UFUNCTION(BlueprintCallable) for impure functions | unit | `pytest tests/test_cpp_gen.py::test_ufunction_callable -x` | ❌ Wave 0 |
| FUNC-03 | UFUNCTION(BlueprintPure) for pure functions | unit | `pytest tests/test_cpp_gen.py::test_ufunction_pure -x` | ❌ Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_cpp_gen.py` — Phase 57 unit tests (can extend existing `test_cpp_gen.py` from Phase 56)
- [ ] Golden-path integration test with BP_FirstPersonCharacter function graphs
- [ ] Test fixture for mock graphs with FunctionEntry/Event/CallFunction nodes

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_cpp_gen.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Input .uasset files are binary assets from trusted source (developer's own project); no network input |
| V6 Cryptography | no | — |

**No security-sensitive operations.** Phase 57 is a code generation tool that processes local .uasset files.

## Sources

### Primary (HIGH confidence)
- Project source: `src/uasset_read/cpp_gen/cpp_type_mapper.py` — UE-to-C++ type mapping (read during research)
- Project source: `src/uasset_read/cpp_gen/formatters/cpp_json_ir.py` — CppClassIR, CppProperty models (read during research)
- Project source: `src/uasset_read/cpp_gen/formatters/cpp_header_formatter.py` — .h text generation (read during research)
- Project source: `src/uasset_read/graph/flow_builder.py` — build_function_graphs() at line 844 (read during research)
- Project source: `src/uasset_read/models/node_types.py` — K2Node* dataclass definitions (read during research)
- Project source: `src/uasset_read/models/core.py` — FEdGraphPinType, FMemberReference, UEdGraphNode (read during research)
- Project source: `src/uasset_read/models/blueprint.py` — BlueprintFunction, BlueprintEvent (read during research)
- Project source: `src/uasset_read/serializers/graph.py` — Node serialization/deserialization (read during research)
- Project reference: `reference/蓝图节点文本参考.md` — Real blueprint node text data (read during research)
- Project decision: `.planning/phases/057-function-signature-mapping/57-CONTEXT.md` — Locked decisions (read during research)

### Secondary (MEDIUM confidence)
- `.planning/phases/52-struct-offset-alignment/52-RESEARCH.md` — FunctionEntry serialization research, ExtraFlags analysis
- `.planning/ROADMAP.md` — Phase history and requirements

### Tertiary (LOW confidence)
- None — all claims verified against project source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing project modules verified by reading source code
- Architecture: HIGH — data flow traced through existing codebase
- Pitfalls: HIGH — based on actual code structure and reference data analysis
- Pin type mapping: HIGH — verified against cpp_type_mapper.py source
- UFUNCTION inference: MEDIUM — pin structure approach is logically sound but not yet tested against diverse blueprint types

**Research date:** 2026-05-18
**Valid until:** 30 days (stable domain — depends only on existing project code, not external libraries)
