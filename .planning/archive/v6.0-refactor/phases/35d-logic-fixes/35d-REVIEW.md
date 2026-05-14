---
phase: 35d-logic-fixes
reviewed: 2026-05-13T08:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - src/uasset_read/parsers/property_types.py
  - src/uasset_read/blueprint/variable_extractor.py
  - src/uasset_read/models/blueprint.py
  - src/uasset_read/models/properties.py
  - src/uasset_read/formatters/json_formatter.py
  - src/uasset_read/formatters/markdown_formatter.py
  - src/uasset_read/blueprint/transform_parser.py
  - src/uasset_read/graph/flow_builder.py
  - src/uasset_read/constants.py
  - src/uasset_read/parsers/property_parser.py
  - src/uasset_read/__init__.py
  - tests/test_phase35d_variable_extractor_fixes.py
  - tests/test_phase35d_model_class_fixes.py
  - tests/test_phase35d_formatter_transform_fixes.py
  - tests/test_phase26_blueprint_metadata_enhancement.py
  - tests/test_phase13_transform.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 35d: 代码审查逻辑与质量修复 — Review Report

**Reviewed:** 2026-05-13T08:00:00Z
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

本次审查覆盖 Phase 35d 涉及的 16 个源文件（11 个源模块 + 5 个测试文件）。发现 3 个 BLOCKER（包含属性标志映射不一致、标签生成错误、PackageIndex 0 被错误丢弃），4 个 WARNING（包含 None GUID 键冲突、Mermaid 特殊字符未转义、未知数组类型静默回退、执行流追踪遗漏），以及 2 个 INFO 问题。

## Critical Issues

### CR-01: `_map_property_flags` 错误地将 `CPF_Edit` 映射为 `is_edit_anywhere`，与 `read_blueprint_variable` 路径不一致

**File:** `src/uasset_read/blueprint/variable_extractor.py:56`

**Issue:**
`_map_property_flags` 第 56 行使用 `CPF_Edit`（0x0000000000000001）作为 `is_edit_anywhere` 的判断依据。但同一模块的 `read_blueprint_variable` 函数（第 519 行）正确地使用 `CPF_EditAnywhere`（0x02000000）。

由于 `CPF_Edit` 是所有可编辑属性的基础标志位（包括 EditAnywhere、EditInstanceOnly、EditDefaultsOnly），使用它作为 `is_edit_anywhere` 的判断条件会导致：

| 属性声明 | 实际 UE 标志位 | `_map_property_flags` 结果 | `read_blueprint_variable` 结果 |
|----------|----------------|---------------------------|-------------------------------|
| EditAnywhere | CPF_Edit + CPF_EditAnywhere | is_edit_anywhere=True | is_edit_anywhere=True (一致) |
| EditInstanceOnly | CPF_Edit + CPF_EditInstanceOnly | **is_edit_anywhere=True** | is_edit_anywhere=False (不一致) |
| EditDefaultsOnly | CPF_Edit | **is_edit_anywhere=True** | is_edit_anywhere=False (不一致) |

对于 `EditInstanceOnly` 属性，`_map_property_flags` 会同时设置 `is_edit_anywhere=True` 和 `is_edit_instance_only=True`，产生语义矛盾。

**Fix:**
将第 56 行从 `CPF_Edit` 改为 `CPF_EditAnywhere`，与 `read_blueprint_variable` 保持一致：

```python
def _map_property_flags(flags: int) -> Dict[str, bool]:
    return {
        "is_edit_anywhere": bool(flags & CPF_EditAnywhere),  # CR-01: 改为 CPF_EditAnywhere
        "is_edit_instance_only": bool(flags & CPF_EditInstanceOnly),
        "is_blueprint_readable": bool(flags & CPF_BlueprintVisible),
        "is_blueprint_read_only": bool(flags & CPF_BlueprintReadOnly),
        "is_net": bool(flags & CPF_Net),
        "is_replicated": bool(flags & CPF_Replicated),
        "is_transient": bool(flags & CPF_Transient),
        "is_blueprint_assignable": bool(flags & CPF_BlueprintAssignable),
        "is_rep_notify": bool(flags & CPF_RepNotify),
        "is_save_game": bool(flags & CPF_SaveGame),
    }
```

### CR-02: `parse_property_flags_to_labels` 和 `_flags_to_labels` 编辑标志标签生成错误

**File:** `src/uasset_read/blueprint/variable_extractor.py:72, 414-418`

**Issue:**
两个标签函数存在相同的逻辑缺陷：

1. `_flags_to_labels`（第 72 行）对 `CPF_Edit` 无条件添加 "EditAnywhere"，不检查 `CPF_EditConst`、`CPF_EditAnywhere`、`CPF_EditInstanceOnly`。
2. `parse_property_flags_to_labels`（第 414-418 行）仅用 `CPF_Edit` 作为 `EditAnywhere` 的判断条件，当 `CPF_Edit | CPF_EditInstanceOnly` 时错误地产生 "EditAnywhere" 而非 "EditInstanceOnly"。

具体错误的场景：
- `flags = CPF_Edit | CPF_EditInstanceOnly` → 当前输出 `["EditAnywhere"]`，应为 `["EditInstanceOnly"]`
- `flags = CPF_Edit` (EditDefaultsOnly) → 当前输出 `["EditAnywhere"]`，应为 `[]`（没有对应的编辑标签）
- `flags = CPF_EditAnywhere`（不含 CPF_Edit） → 当前不输出任何编辑标签，应输出 `["EditAnywhere"]`

`test_phase26_blueprint_metadata_enhancement.py` 第 74-76 行也错误地断言 `CPF_Edit | CPF_EditInstanceOnly` 应包含 "EditAnywhere"，需要同步修正。

**Fix for `parse_property_flags_to_labels`（第 414-418 行）：**

```python
    # Edit 标志（互斥模式）
    if flags & CPF_EditAnywhere:
        labels.append("EditAnywhere")
    elif flags & CPF_EditInstanceOnly:
        labels.append("EditInstanceOnly")
    elif flags & CPF_Edit:
        labels.append("EditDefaultsOnly")
    if flags & CPF_EditConst:
        labels.append("EditConst")
```

**Fix for `_flags_to_labels`（第 72-76 行）：**

```python
    if flags & CPF_EditAnywhere:
        labels.append("EditAnywhere")
    elif flags & CPF_EditInstanceOnly:
        labels.append("EditInstanceOnly")
    elif flags & CPF_Edit and not (flags & CPF_EditConst):
        labels.append("EditDefaultsOnly")
    if flags & CPF_EditConst:
        labels.append("EditConst")
```

**Fix for test** (`test_phase26_blueprint_metadata_enhancement.py` 第 74-76 行)：将 `CPF_Edit | CPF_EditInstanceOnly` 的断言从 `"EditAnywhere"` 改为 `"EditInstanceOnly"`。

### CR-03: `extract_blueprint_metadata` 中 `or` 链式取值导致 PackageIndex 0 被错误丢弃

**File:** `src/uasset_read/blueprint/variable_extractor.py:383`

**Issue:**
第 383 行使用 `or` 进行链式回退：
```python
parent_class = prop.value.get('raw_index') or prop.value.get('resolved') or prop.value
```

当 `raw_index` 为 0 时（PackageIndex 0 在 UE 中表示引用 package 自身的根节点，是有效值），Python 的 `0 or X` 表达式返回 `X`，导致合法的 `raw_index = 0` 被丢弃并回退到 `resolved` 字段。

由于 `prop.value.get('raw_index')` 返回 0 时是合法的引用（对应 PackageIndex 的根对象），不应被隐式替换。

**Fix:**
使用 `is None` 检查替代 `or` 链式回退：

```python
            if prop.value and isinstance(prop.value, dict):
                raw = prop.value.get('raw_index')
                if raw is not None:
                    parent_class = raw
                else:
                    parent_class = prop.value.get('resolved') or prop.value
```

## Warnings

### WR-01: `node_lookup` 中 None GUID 引发字典键冲突

**File:** `src/uasset_read/graph/flow_builder.py:372`

**Issue:**
第 372 行 `node_lookup[node.node_guid] = node` 使用 `node.node_guid` 作为键。当 `node_guid` 为 None 时，所有 GUID 为 None 的节点共享同一个键 `None`，后处理的节点覆盖前者，导致连接映射丢失。

该函数内第 233 行已通过 `if current_guid is None` 分支处理 None 情况，但 `build_execution_flows` 和 `build_connections_map` 的 `node_lookup` 构建并没有相应的防护。

**Fix:**
在 `build_execution_flows` 和 `build_connections_map` 的 `node_lookup` 构建中加入 GUID 为 None 的防护，使用 index 派生键作为 fallback：

```python
    for idx, node in enumerate(graph.nodes):
        guid = node.node_guid if node.node_guid is not None else f"__node_{idx}__"
        node_lookup[guid] = node
```

或者直接跳过 GUID 为 None 的节点（记录 warning），具体取决于业务需求。

### WR-02: Mermaid 节点名未转义特殊字符

**File:** `src/uasset_read/formatters/markdown_formatter.py:109-168`

**Issue:**
`_build_mermaid_flowchart` 函数直接使用事件名（如 `start_event`）和函数名作为 Mermaid 节点 ID，未对以下字符进行转义：

- 括号 `()[]{}` — 在 Mermaid 中有语法含义
- `-->` 箭头符号 — 若出现在节点名中会被解释为连接
- 点号 `.` 和斜杠 `/` — 出现在 `class_name.pin_name` 格式的事件名中（第 385 行）
- 引号 `"` — 若节点名包含引号会破坏 Mermaid 语法

例如 `start_event = "K2Node_EnhancedInputAction.Started"` 包含点号，在 Mermaid 中`Node.Started`会被解释为 `Node` 对象的 `.Started` 属性访问，导致渲染错误。

**Fix:**
在 `_build_mermaid_flowchart` 中添加转义函数，对节点名中特殊字符进行替换或引用：

```python
def _sanitize_mermaid_node_id(name: str) -> str:
    """Escape special characters for Mermaid node IDs."""
    # Replace special characters that break Mermaid syntax
    sanitized = name.replace('"', "'").replace('(', '_').replace(')', '_')
    sanitized = sanitized.replace('[', '_').replace(']', '_')
    sanitized = sanitized.replace('{', '_').replace('}', '_')
    sanitized = sanitized.replace('.', '_')
    # Wrap in quotes if contains spaces or special chars
    if not sanitized.isidentifier() or '/' in name:
        return f'"{sanitized}"'
    return sanitized
```

### WR-03: `_get_inner_type` 对未知数组类型静默返回 "IntProperty"

**File:** `src/uasset_read/parsers/property_types.py:301`

**Issue:**
`_get_inner_type` 函数第 301 行在未匹配到已知映射时默认返回 `"IntProperty"`，而非抛出异常或记录 warning。当遇到未知或不支持的数组元素类型时，解析器会以 IntProperty 方式读取数据，产生无提示的静默数据损坏。

以下类型未被映射：
- `ArrayProperty_InterfaceProperty`
- `ArrayProperty_DelegateProperty`
- `ArrayProperty_MapProperty`
- `ArrayProperty_SetProperty`
- UE5 中使用 Angular brackets 格式的类型名

**Fix:**
返回 `None` 让调用方处理未知类型，或至少记录 warning：

```python
    # Default for unknown types: log warning and return None
    import logging
    logging.getLogger(__name__).warning(
        f"Unknown array element type: {array_type}, returning None"
    )
    return None  # Caller must handle None
```

对应的 `parse_array_property` 调用点（第 124-125 行）需要添加 `inner_type` 为 None 的处理。

### WR-04: `_trace_execution_from_pin` 对单引脚多连接场景只追踪第一个

**File:** `src/uasset_read/graph/flow_builder.py:295-301`

**Issue:**
`_trace_execution_from_pin` 函数在第 295 行的 `for linked_pin_id in ...` 循环中使用 `return` 退出，意味着该引脚上第一个有效的 `linked_to` 匹配后立即返回，后续的连接被忽略。

虽然在 Exec 引脚上多连接不常见（典型的执行流是线性的），但 `K2Node_EnhancedInputAction` 的 Started/Ongoing/Completed 等各引脚各自沿分支执行，每条分支后续可能出现分支合流场景，此时单引脚多 `linked_to` 会成为实际需求。

**Fix:**
将 `return` 改为 `yield` 或收集所有追踪结果：

```python
def _trace_execution_from_pin(
    start_node: UEdGraphNode,
    start_pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> List[Dict]:
    results = []
    for linked_pin_id in (start_pin.linked_to_raw or []):
        target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id
        if target_pin_guid in pin_lookup:
            target_node_guid, _ = pin_lookup[target_pin_guid]
            next_node = node_lookup.get(target_node_guid)
            if next_node:
                results.extend(
                    _trace_execution_from_event(next_node, pin_lookup, node_lookup)
                )
    return results
```

## Info

### IN-01: `extract_blueprint_metadata` 函数缺少类型注解

**File:** `src/uasset_read/blueprint/variable_extractor.py:332-340`

**Issue:**
`extract_blueprint_metadata` 函数的参数和返回值均缺少类型注解，与该模块中其他函数（如 `extract_blueprint_variables`、`read_blueprint_variable`）的风格不一致。建议添加完整类型注解以便 IDE 类型检查和自动补全。

**Fix:**
```python
def extract_blueprint_metadata(
    export: Any,
    archive: FArchive,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    name_map: List[str],
    summary: PackageFileSummary,
) -> Tuple[Optional[BlueprintMetadata], Optional[str]]:
```

### IN-02: `serialize_property_value` 使用 `hasattr` 进行类型分派，无法处理 dict 嵌套高级属性值

**File:** `src/uasset_read/formatters/json_formatter.py:154-191`

**Issue:**
`serialize_property_value` 使用 `hasattr(value, "struct_type")` 等方式进行 duck typing 分派。如果 `value` 恰好是一个包含相同键的 `dict`，会被误识别。此外，第 151 行对 `dict` 类型直接返回不递归处理，若 dict 内部嵌套了高级属性值 dataclass，这部分数据不会被序列化。

**Fix（可选）：**
使用 `isinstance` 替代 `hasattr` 进行精确类型检查。如果代码结构允许直接导入数据类：

```python
    if isinstance(value, StructValue):
        ...
    elif isinstance(value, MapValue):
        ...
```

---

_Reviewed: 2026-05-13T08:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
