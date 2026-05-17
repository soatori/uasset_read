# Phase 54: 数据流追踪 - Research

**Researched:** 2026-05-17
**Domain:** Blueprint data flow tracing, pure function return value to CallFunction parameter input
**Confidence:** HIGH

## Summary

Phase 54 构建数据流追踪能力，实现从 Pure 函数返回值到 CallFunction 参数输入的双向追踪。核心挑战在于当前 `build_data_flows()` 仅输出扁平的 `{source, target}` 连接记录，缺乏语义化的数据来源标注（如 `data_providers`、`data_sources`）。参考文件 `蓝图节点文本参考.md` 显示 Move 函数中存在典型的数据流路径：FunctionEntry 输出参数通过 Knot 链传递到 CallFunction 输入，Pure 函数（GetActorForwardVector/GetActorRightVector）的 ReturnValue 直接连接到 CallFunction 的 WorldDirection 参数。

**Primary recommendation:** 双向追踪策略实现 —— 在 CallFunction 节点的 `parameters.input_params` 中添加 `data_source` 字段（反向追踪），在 Pure 函数节点的输出参数中添加 `data_providers` 字段（正向追踪）。Knot 节点透明穿透使用 `_resolve_knot_chain()` 函数，图边界检测通过 `is_boundary_node()` 判断（FunctionEntry 输出 pin、本地变量、self 引用等）。SubPin 展开限于第一级字段（`sub_pins` 数组扁平化）。不重构现有 `build_data_flows()`，而是在 `build_execution_flows()` 的 `_trace_execution_from_event` 中增强 CallFunction 和 Pure 函数节点的数据标注。

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 数据流反向追踪（data_sources） | Graph/Flow Builder | — | `_trace_execution_from_event` 在处理 CallFunction 时需反向追踪输入参数的数据来源 |
| 数据流正向标注（data_providers） | Graph/Flow Builder | — | Pure 函数节点（无 exec pin）需要在输出参数中标注数据去向 |
| Knot 透明穿透 | Graph/Flow Builder | — | `_resolve_knot_chain` 递归追踪 Knot 链直到到达非 Knot 节点 |
| 图边界检测 | Graph/Flow Builder | — | `is_boundary_node` 判断追踪终点（FunctionEntry、self、本地变量） |
| SubPin 字段展开 | Graph/Flow Builder | Serializer | 第一级 `sub_pins` 数组扁平化，Serializer 提供类型信息（struct/composite） |
| 数据标注输出 | Formatters | Graph/Flow Builder | `_extract_call_function_parameters` 增强 `data_source` 字段输出 |

## User Constraints

> Phase 54 上下文来自 STATE.md（2026-05-17 Phase 54 Context 已捕获）。无 CONTEXT.md 文件。

### STATE.md 已捕获约束
- **双向追踪策略：** 正向 data_providers + 反向 data_sources
- **Knot 透明穿透：** 数据流中 Knot 需透明穿透（与执行流不同，数据流中 Knot 有 InputPin/OutputPin）
- **图边界停止：** FunctionEntry 输出 pin、本地变量、self 引用等作为追踪终点
- **SubPin 字段级展开：** 第一级展开，不递归
- **仅非 exec pin：** 聚焦 Pure 函数输出和 CallFunction 输入参数

### Deferred Ideas (OUT OF SCOPE)
- 递归 SubPin 展开（struct 字段的字段） — v2 scope
- 跨图数据流追踪（函数调用的参数来源在其他图） — 不在 v9.0 范围内
- 数据流可视化输出（Mermaid/Graphviz） — Phase 55 scope
- 数据依赖图构建（dependency graph） — 未来阶段

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | 能追踪数据流从纯函数返回值 → 调用节点输入参数 | 双向追踪策略（反向 data_sources） |
| DATA-02 | 能处理 Knot 节点的数据传递（中继连接） | `_resolve_knot_chain` 递归穿透 |
| DATA-03 | 能处理 SubPin 展开的结构体字段级数据流 | 第一级 `sub_pins` 数组扁平化 |

## Standard Stack

### Core (Internal Modules)

| Module | Purpose | Changes Needed |
|--------|---------|----------------|
| `graph/flow_builder.py` | 数据流追踪核心 | `_resolve_knot_chain`, `is_boundary_node`, `_trace_data_source`, 增强 `_trace_execution_from_event` |
| `models/core.py` | Pin 数据结构 | `UEdGraphPin.sub_pins` 已存在，无需修改 |
| `models/node_types.py` | Knot 类型判断 | `K2NodeKnot` dataclass 已存在，无需修改 |
| `formatters/json_formatter.py` | 参数格式化 | `_extract_call_function_parameters` 增强 `data_source` 字段 |
| `constants.py` | 边界节点类型 | 新增 `DATA_BOUNDARY_NODES` frozenset |

### Version verification

所有模块为内部代码，无版本检查需求。

## Package Legitimacy Audit

无外部包安装需求。本阶段为纯内部代码修改。

## Architecture Patterns

### 数据流追踪架构

```
build_execution_flows(graph)
  ↓
_trace_execution_from_event(start_node, pin_lookup, node_lookup)
  ↓
  [for each CallFunction node:]
    _extract_call_function_parameters(node) → {"input_params": [...], "output_params": [...]}
      ↓
      [for each input_param:]
        _trace_data_source(pin, pin_lookup, node_lookup)
          ↓
          _resolve_knot_chain(target_pin_guid) → terminal_pin_guid
            ↓
            is_boundary_node(terminal_node) → True/False
              ↓
              if True: {"source_type": "boundary", "source": {...}}
              if False: {"source_type": "pure_function", "source": {...}}
```

### 双向追踪策略对比

| 方向 | 起点 | 终点 | 输出字段 | 实现位置 |
|------|------|------|----------|----------|
| **反向追踪** | CallFunction input pin | 数据源节点 | `data_sources` 数组（每个 input_param 内） | `_trace_execution_from_event` CallFunction 处理 |
| **正向标注** | Pure function output pin | 数据去向节点 | `data_providers` 数组（Pure 函数节点内） | `_trace_execution_from_event` Pure 函数检测 |

**为什么选择双向而非单向：**
- 反向追踪提供 CallFunction 的参数来源语义（"这个 WorldDirection 来自 GetActorForwardVector"）
- 正向标注提供 Pure 函数的数据去向语义（"GetActorForwardVector 的 ReturnValue 去往 AddMovementInput.WorldDirection"）
- 双向互补，避免单一方向遗漏（如 Knot 链两端）

### Knot 透明穿透（数据流）

Knot 在数据流中的行为与执行流不同：

| Aspect | Execution Flow | Data Flow |
|--------|---------------|-----------|
| Knot pins | 无 exec pins | 有 InputPin + OutputPin（数据 pin） |
| Traversal | 自然排除（无 exec） | 需显式穿透（InputPin → OutputPin） |
| Chain | 不存在 | 可能多级串联（Knot_2 → Knot_1） |

**Knot 链穿透算法：**
```python
def _resolve_knot_chain(pin_guid: str, pin_lookup: Dict, node_lookup: Dict, max_depth: int = 20) -> Tuple[str, bool]:
    """递归穿透 Knot 链直到到达非 Knot 节点。

    Returns: (terminal_pin_guid, success)
    - success=True: 找到终端节点
    - success=False: 链断裂或超过深度限制
    """
    visited = set()
    current_pin_guid = pin_guid

    for _ in range(max_depth):
        if current_pin_guid in visited:
            return (current_pin_guid, False)  # 循环检测

        visited.add(current_pin_guid)

        # Get target node
        target_node_guid, _ = pin_lookup.get(current_pin_guid, (None, None))
        if not target_node_guid:
            return (current_pin_guid, False)  # Pin 不存在

        target_node = node_lookup.get(target_node_guid)
        if not target_node:
            return (current_pin_guid, False)  # Node 不存在

        # Check if Knot
        if target_node.class_name != "K2Node_Knot":
            return (current_pin_guid, True)  # 到达非 Knot 节点

        # Knot: Find OutputPin
        for pin in target_node.pins:
            if pin.pin_name == "OutputPin" and pin.direction == 1:  # Output
                # OutputPin 的 linked_to_raw 是下一个 pin
                for linked_ref in (pin.linked_to_raw or []):
                    next_pin_guid = linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref
                    current_pin_guid = next_pin_guid
                    break
                break

    return (current_pin_guid, False)  # 超过深度限制
```

### 图边界检测

**边界节点类型（停止追踪）：**

| Boundary Type | Node Type | Example | Reason |
|---------------|-----------|---------|--------|
| **FunctionEntry 输出** | K2Node_FunctionEntry | FunctionEntry_0 "Left / Right" pin | 函数参数是数据起点 |
| **Self 引用** | K2Node_CallFunction | "self" pin（Target self） | self 引用无需进一步追踪 |
| **本地变量** | K2Node_VariableSet/Get | VariableGet "Speed" | 本地变量在图内定义，Phase 53 不追踪 |
| **默认值** | 无连接的 pin | pin.default_value != None | 参数有默认值，无外部数据源 |
| **跨图引用** | K2Node_CallFunction（调用其他图） | CallFunction to other blueprint | 不在 v9.0 范围内 |

**边界检测实现：**
```python
DATA_BOUNDARY_NODES = frozenset({
    "K2Node_FunctionEntry",
    "K2Node_VariableSet",
    "K2Node_VariableGet",
    # Self 引用通过 pin_name == "self" 判断
})

def is_boundary_node(node: UEdGraphNode, pin_name: str) -> bool:
    """判断是否为数据流边界节点。"""
    if node.class_name in DATA_BOUNDARY_NODES:
        return True
    # Self 引用
    if pin_name.lower() == "self":
        return True
    return False
```

### SubPin 字段级展开（第一级）

SubPin 是 UE 中 struct/composite pin 的字段级子 pin（如 Vector pin 有 X/Y/Z sub_pins）。

**SubPin 结构（UEdGraphPin）：**
```python
@dataclass
class UEdGraphPin:
    ...
    sub_pins: List[dict] = field(default_factory=list)  # [{pin_id, pin_name, ...}]
    parent_pin: Optional[dict] = None  # 父 pin 引用
```

**第一级展开策略：**
- 仅展开直接 sub_pins，不递归 sub_pins 的 sub_pins
- 展开后每个 sub_pin 作为独立数据流项（如 Vector.X → float）
- 输出格式：`{"parent_pin": "Vector", "field": "X", "source": ...}`

**展开时机：**
- 当追踪到 struct pin 时，检查 `sub_pins` 非空
- 若 sub_pins 存在，为每个 sub_pin 单独标注数据来源
- 若 sub_pins 为空，整体标注（如 struct 来自另一个函数）

### Recommended Project Structure

```
src/uasset_read/graph/
├── flow_builder.py          # 数据流追踪核心（修改）
├── data_flow_helpers.py     # 新增辅助函数（可选，或内嵌在 flow_builder）
└── __init__.py              # 导出更新（可选）

tests/
├── test_output_formatting.py  # 新增数据流追踪测试
└── fixtures/                   # 测试 fixture（FunctionEntry + Knot + Pure）
```

### Anti-Patterns to Avoid

1. **重构 `build_data_flows()` 为语义化输出** — STATE.md 明确不重构，而是在 execution flow 中增强数据标注
2. **递归 SubPin 展开** — 仅第一级，递归会增加复杂度和 token 消耗
3. **跨图数据流追踪** — v9.0 scope 不包含，会导致递归膨胀
4. **将 Knot 作为独立数据流节点** — Knot 应透明穿透，不应出现在最终输出中

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pin 连接查找 | 新 lookup 结构 | `pin_lookup` + `node_lookup`（已有） | Phase 53 已在 `_trace_execution_from_event` 中建立 |
| Knot 检测 | 字符串匹配 class_name | `node.class_name == "K2Node_Knot"` | 与 Phase 53 执行流一致 |
| Pure 函数检测 | 重新检测 exec pins | `not has_exec_pin`（已有） | Phase 53 已实现检测逻辑 |
| 参数提取 | 新解析函数 | `_extract_call_function_parameters`（已有） | Phase 49 已实现，仅需增强 data_source 字段 |

**Key insight:** Phase 54 是数据标注增强，不是数据流重构。大部分基础设施已在 Phase 53 完成。

## Runtime State Inventory

N/A — 本阶段非 rename/refactor/migration phase。

## Common Pitfalls

### Pitfall 1: Knot 链无限循环
**What goes wrong:** Knot 链形成循环（A → B → A），递归穿透无限循环。
**Why it happens:** UE 蓝图中 Knot 通常不循环，但恶意构造或解析错误可能产生循环。
**How to avoid:** `_resolve_knot_chain` 添加 `visited` set 和 `max_depth` 限制（20 级）。
**Warning signs:** 超过 20 级 Knot 深度返回 `success=False`。

### Pitfall 2: SubPin 过度展开导致输出膨胀
**What goes wrong:** struct pin 有 10+ 字段，展开后产生 10+ 数据流记录，JSON 输出膨胀。
**Why it happens:** UE 中部分 struct 有多字段（如 Transform 有 Location/Rotation/Scale，每个又有 X/Y/Z）。
**How to avoid:** 仅第一级展开，不递归。若字段数超过阈值（如 5），标记为 `"sub_pins_summary": "5 fields"` 而不全部展开。
**Warning signs:** 单个 CallFunction 节点的 data_sources 数组超过 20 项。

### Pitfall 3: 图边界误判导致追踪中断
**What goes wrong:** 将非边界节点误判为边界（如 VariableGet 本应是数据源，但误判为边界停止）。
**Why it happens:** `DATA_BOUNDARY_NODES` 定义过宽，或 `is_boundary_node` 逻辑错误。
**How to avoid:** 精准定义边界：FunctionEntry 输出、self、本地变量定义（VariableSet）、默认值。VariableGet 是数据读取，非定义，应继续追踪。
**Warning signs:** data_sources 缺失预期来源（如 Move 函数 ScaleValue 缺失 FunctionEntry 来源）。

### Pitfall 4: Pure 函数正向标注遗漏
**What goes wrong:** 仅反向追踪（CallFunction input → data_source），遗漏 Pure 函数的 data_providers 标注。
**Why it happens:** 双向追踪不对称实现，只实现反向。
**How to avoid:** 双向同时实现：CallFunction input 反向追踪 + Pure 函数 output 正向标注。正向标注需要在 `_trace_execution_from_event` 的 Pure 函数检测处添加。
**Warning signs:** Pure 函数节点（GetActorForwardVector）无 data_providers 字段。

### Pitfall 5: linked_to_raw 解析不一致
**What goes wrong:** `linked_to_raw` 有 dict 和 str 两种格式，解析时遗漏 dict 格式。
**Why it happens:** Phase 18 引入 dict 格式 `{"pin_guid": str, "owning_node": str}`，但部分解析代码假设为 str。
**How to avoid:** 使用统一解析：`linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref`（与 Phase 53 一致）。
**Warning signs:** `KeyError: 'pin_guid'` 或 AttributeError in linked_to_raw parsing。

## Code Examples

### 现有 build_data_flows 实现（需理解但不修改）

```python
# Source: src/uasset_read/graph/flow_builder.py L498-533
def build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]:
    """构建数据流图（D-19-06~09, LINK-03）。

    从非exec pins提取数据传递关系，构建data_flows数组。
    输出为扁平 {source, target} 连接记录。
    """
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    node_name_lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    data_flows: List[Dict] = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category != "exec":
                for linked_pin_ref in (pin.linked_to_raw or []):
                    target_pin_guid = linked_pin_ref.get("pin_guid") if isinstance(linked_pin_ref, dict) else linked_pin_ref
                    if target_pin_guid in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                        data_flows.append({
                            "source": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "target": format_pin_ref(target_node_guid, target_pin_name, node_name_lookup, mode)
                        })

    return data_flows
```

**不修改原因：** STATE.md 明确 "不重构现有 `build_data_flows()`"。数据标注在 execution flow 中增强。

### 现有 _trace_execution_from_event CallFunction 处理（需增强）

```python
# Source: src/uasset_read/graph/flow_builder.py L338-356
if current_node.class_name == "K2Node_CallFunction":
    nd = current_node.node_data
    if nd:
        fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
        if fr:
            node_info["function_name"] = getattr(fr, 'member_name', None)
    # Phase 49: simplified params for execution flow
    node_info["params"] = [
        {"name": pin.pin_name, "type": pin.pin_type.pin_category if pin.pin_type else ""}
        for pin in current_node.pins
        if pin.pin_type and pin.pin_type.pin_category != "exec" and pin.direction == 0
    ]
    # Phase 53: mark pure functions with "pure": true in flow
    has_exec_pin = any(pin.pin_type and pin.pin_type.pin_category == "exec" for pin in current_node.pins)
    if not has_exec_pin:
        node_info["pure"] = True
    elif nd and hasattr(nd, 'b_defaults_to_pure') and nd.b_defaults_to_pure:
        node_info["pure"] = True
```

**需要增强：** 在 `node_info["params"]` 中为每个参数添加 `data_source` 字段。

### 现有 _extract_call_function_parameters（需增强）

```python
# Source: src/uasset_read/formatters/json_formatter.py L474-503
def _extract_call_function_parameters(node: Any) -> Dict[str, List[Dict]]:
    """从 K2Node_CallFunction 节点的 pins 中提取函数参数（Phase 49）。

    过滤 exec pins，将输入/输出参数分离为结构化数组。
    """
    input_params: List[Dict] = []
    output_params: List[Dict] = []

    for pin in node.pins:
        if pin.pin_type and pin.pin_type.pin_category == "exec":
            continue

        param: Dict[str, Any] = {
            "name": pin.pin_name,
            "pin_category": pin.pin_type.pin_category if pin.pin_type else "",
        }
        if pin.pin_type:
            if pin.pin_type.pin_subcategory:
                param["pin_subcategory"] = pin.pin_type.pin_subcategory
            if pin.pin_type.is_reference:
                param["is_reference"] = True
        if pin.default_value is not None and pin.default_value != "":
            param["default_value"] = pin.default_value

        if pin.direction == 0:
            input_params.append(param)
        else:
            output_params.append(param)

    return {"input_params": input_params, "output_params": output_params}
```

**需要增强：** 为 input_params 中每个 param 添加 `data_source` 字段（通过 `_trace_data_source` 函数）。

### 新增 _resolve_knot_chain 函数（需实现）

```python
def _resolve_knot_chain(
    pin_guid: str,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    max_depth: int = 20
) -> Tuple[str, bool]:
    """递归穿透 Knot 链直到到达非 Knot 节点。

    Args:
        pin_guid: 起始 pin GUID
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        max_depth: 最大穿透深度（防止无限循环）

    Returns:
        Tuple[str, bool]: (terminal_pin_guid, success)
        - success=True: 找到非 Knot 终端节点
        - success=False: 链断裂或循环检测
    """
    visited: Set[str] = set()
    current_pin_guid = pin_guid

    for _ in range(max_depth):
        if current_pin_guid in visited:
            return (current_pin_guid, False)  # 循环检测

        visited.add(current_pin_guid)

        # Get target node
        target_node_guid, _ = pin_lookup.get(current_pin_guid, (None, None))
        if not target_node_guid:
            return (current_pin_guid, False)  # Pin 不存在

        target_node = node_lookup.get(target_node_guid)
        if not target_node:
            return (current_pin_guid, False)  # Node 不存在

        # Check if Knot
        if target_node.class_name != "K2Node_Knot":
            return (current_pin_guid, True)  # 到达非 Knot 节点

        # Knot: Find OutputPin
        for pin in target_node.pins:
            if pin.pin_name == "OutputPin" and pin.direction == 1:  # Output
                # OutputPin 的 linked_to_raw 是下一个 pin
                for linked_ref in (pin.linked_to_raw or []):
                    next_pin_guid = linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref
                    current_pin_guid = next_pin_guid
                    break
                break

    return (current_pin_guid, False)  # 超过深度限制
```

### 新增 is_boundary_node 函数（需实现）

```python
DATA_BOUNDARY_NODES = frozenset({
    "K2Node_FunctionEntry",
    "K2Node_VariableSet",  # 本地变量定义
})

def is_boundary_node(node: UEdGraphNode, pin_name: str) -> bool:
    """判断是否为数据流边界节点。

    Args:
        node: 目标节点
        pin_name: pin 名称（用于 self 检测）

    Returns:
        bool: True=边界（停止追踪），False=继续追踪
    """
    if node.class_name in DATA_BOUNDARY_NODES:
        return True

    # Self 引用（Target self）
    if pin_name.lower() == "self":
        return True

    return False
```

### 新增 _trace_data_source 函数（需实现）

```python
def _trace_data_source(
    pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str]
) -> Optional[Dict]:
    """追踪单个参数的数据来源。

    Args:
        pin: 目标 pin（CallFunction input pin）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        node_name_lookup: node_guid → node_name 查找表

    Returns:
        Optional[Dict]: 数据来源标注，或 None（默认值/无连接）
    """
    # 检查是否有连接
    if not pin.linked_to_raw:
        # 默认值
        if pin.default_value is not None and pin.default_value != "":
            return {"source_type": "default_value", "value": pin.default_value}
        return None  # 无数据源

    # 遍历连接（可能有多个，但通常只有一个）
    sources: List[Dict] = []
    for linked_ref in pin.linked_to_raw:
        target_pin_guid = linked_ref.get("pin_guid") if isinstance(linked_ref, dict) else linked_ref

        # Knot 穿透
        terminal_pin_guid, success = _resolve_knot_chain(target_pin_guid, pin_lookup, node_lookup)
        if not success:
            sources.append({"source_type": "knot_chain_broken", "pin_guid": terminal_pin_guid})
            continue

        # 获取终端节点
        terminal_node_guid, terminal_pin_name = pin_lookup.get(terminal_pin_guid, (None, None))
        if not terminal_node_guid:
            sources.append({"source_type": "pin_not_found", "pin_guid": terminal_pin_guid})
            continue

        terminal_node = node_lookup.get(terminal_node_guid)
        if not terminal_node:
            sources.append({"source_type": "node_not_found", "node_guid": terminal_node_guid})
            continue

        # 边界检测
        if is_boundary_node(terminal_node, terminal_pin_name):
            # FunctionEntry 参数或 self
            if terminal_node.class_name == "K2Node_FunctionEntry":
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "function_parameter",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
            elif terminal_pin_name.lower() == "self":
                sources.append({"source_type": "self_reference"})
            else:
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "boundary",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
        else:
            # Pure function output
            if terminal_node.class_name == "K2Node_CallFunction":
                # 检查是否为 Pure
                has_exec_pin = any(p.pin_type and p.pin_type.pin_category == "exec" for p in terminal_node.pins)
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)

                # 获取函数名
                func_name = None
                nd = terminal_node.node_data
                if nd:
                    fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
                    if fr:
                        func_name = getattr(fr, 'member_name', None)

                sources.append({
                    "source_type": "pure_function" if not has_exec_pin else "function_output",
                    "node": node_name,
                    "function_name": func_name,
                    "pin": terminal_pin_name
                })

    # 通常只有一个数据源，但返回数组以支持合并情况
    return {"data_sources": sources} if sources else None
```

### Move 函数数据流示例（参考文件）

```
FunctionEntry_0 (Move)
  ↓
  "Left / Right" (double) → Knot_2 → Knot_1 → CallFunction_7445 "ScaleValue" (float)
  "Forward / Backward" (double) → Knot_3 → Knot_4 → CallFunction_7346 "ScaleValue" (float)

CallFunction_8029 (GetActorForwardVector) [pure]
  ↓
  "ReturnValue" (Vector) → CallFunction_7346 "WorldDirection" (Vector)

CallFunction_8520 (GetActorRightVector) [pure]
  ↓
  "ReturnValue" (Vector) → CallFunction_7445 "WorldDirection" (Vector)
```

**预期输出（data_sources 增强）：**
```json
{
  "node_type": "K2Node_CallFunction",
  "function_name": "AddMovementInput",
  "params": [
    {
      "name": "WorldDirection",
      "pin_category": "struct",
      "data_sources": [
        {
          "source_type": "pure_function",
          "node": "K2Node_CallFunction_8029",
          "function_name": "GetActorForwardVector",
          "pin": "ReturnValue"
        }
      ]
    },
    {
      "name": "ScaleValue",
      "pin_category": "real",
      "pin_subcategory": "float",
      "data_sources": [
        {
          "source_type": "function_parameter",
          "node": "K2Node_FunctionEntry_0",
          "pin": "Forward / Backward"
        }
      ]
    }
  ]
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 扁平 data_flows 数组（无语义） | 增强 execution_flow 中 CallFunction data_source 字段 | Phase 54 | 数据来源可追溯，支持 C++ 翻译 |
| Knot 作为独立数据流节点 | Knot 透明穿透 | Phase 54 | 输出更简洁，数据链更清晰 |
| 无 Pure 函数数据去向标注 | Pure 函数 data_providers 字段 | Phase 54 | 数据依赖完整性 |

**Deprecated/outdated:**
- None — Phase 54 是增强，非废弃。

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Knot 链最大深度 20 级足够 | Knot 透明穿透 | 若实际有更长链，返回 `success=False`，用户可调整 `max_depth` |
| A2 | SubPin 仅第一级展开足够 | SubPin 展开 | 若用户需要深度字段追踪，v2 scope 可递归展开 |
| A3 | VariableGet 非边界节点（应继续追踪） | 图边界检测 | 若 VariableGet 应作为边界，需调整 `DATA_BOUNDARY_NODES` |
| A4 | linked_to_raw 通常只有一个连接 | _trace_data_source | 若有多个连接（合并），返回 `data_sources` 数组支持 |

## Open Questions

1. **VariableGet 是否为边界节点**
   - What we know: VariableSet 是本地变量定义（边界），VariableGet 是读取
   - What's unclear: VariableGet 是否应继续追踪到 VariableSet，还是作为边界
   - Recommendation: 不作为边界，继续追踪（VariableGet → VariableSet）。但 v9.0 scope 不包含变量追踪，Phase 54 先标记为 `source_type: "local_variable"`（简化）。

2. **data_providers 字段位置**
   - What we know: Pure 函数需要在输出参数中标注数据去向
   - What's unclear: 字段放在 execution_flow 的节点级，还是 params.output_params 内
   - Recommendation: 放在节点级 `"data_providers": [...]`（与 data_sources 对称，便于反向查询）。

3. **Knot 链断裂处理**
   - What we know: Knot 链可能断裂（最后一个 Knot 的 OutputPin 无连接）
   - What's unclear: 断裂时返回什么
   - Recommendation: 返回 `{"source_type": "knot_chain_broken", "last_pin_guid": ...}`，便于调试。

## Environment Availability

无外部依赖 — 纯 Python 代码修改。

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None（pytest auto-discovery） |
| Quick run command | `python -m pytest tests/test_output_formatting.py -x -k "data_flow"` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | CallFunction input param data_source 追踪 | unit | `pytest tests/test_output_formatting.py -x -k "data_source"` | Wave 0 — 需创建 |
| DATA-02 | Knot 链透明穿透 | unit | `pytest tests/test_output_formatting.py -x -k "knot_chain"` | Wave 0 — 需创建 |
| DATA-03 | SubPin 第一级展开 | unit | `pytest tests/test_output_formatting.py -x -k "sub_pin"` | Wave 0 — 需创建 |
| DATA-01 | Pure function data_providers 标注 | unit | `pytest tests/test_output_formatting.py -x -k "data_provider"` | Wave 0 — 需创建 |
| DATA-01 | FunctionEntry 参数作为边界 | unit | `pytest tests/test_output_formatting.py -x -k "boundary"` | Wave 0 — 需创建 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_output_formatting.py -x -k "data_flow"`（相关测试）
- **Per wave merge:** `python -m pytest tests/ -x`（全量）
- **Phase gate:** 全量测试绿色 + Move 函数数据流验证（集成测试）

### Wave 0 Gaps
- [ ] `tests/test_output_formatting.py` — 需要 `sample_function_graph_with_data_flow` fixture（FunctionEntry + Knot + Pure + CallFunction）
- [ ] `tests/test_output_formatting.py` — 需要 `test_trace_data_source_knot_chain` 测试
- [ ] `tests/test_output_formatting.py` — 需要 `test_trace_data_source_function_entry` 测试
- [ ] `tests/test_output_formatting.py` — 需要 `test_trace_data_source_pure_function` 测试
- [ ] `tests/test_output_formatting.py` — 需要 `test_sub_pin_first_level_expand` 测试
- [ ] `tests/test_output_formatting.py` — 需要 `test_data_providers_pure_function` 测试

**Wave 0 需创建 6 个测试 + 1 个 fixture。**

## Security Domain

N/A — 本阶段无外部依赖、无网络 I/O、无用户输入处理。纯图遍历和数据标注。

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/uasset_read/graph/flow_builder.py` — 全文件读取
- Codebase inspection: `src/uasset_read/models/core.py` — UEdGraphPin + FEdGraphPinType 结构
- Codebase inspection: `src/uasset_read/models/node_types.py` — K2NodeKnot dataclass
- Codebase inspection: `src/uasset_read/formatters/json_formatter.py` — `_extract_call_function_parameters` 函数
- Codebase inspection: `src/uasset_read/constants.py` — CONTROL_FLOW_NODES, START_EVENT_TYPES
- Reference file: `reference/蓝图节点文本参考.md` L228-340 — Move 函数图结构（FunctionEntry + Knot + Pure + CallFunction）

### Secondary (MEDIUM confidence)
- Phase 53 RESEARCH.md — 执行流追踪基础，Pure 函数标记，Knot 排除
- Phase 53 PLAN: `.planning/phases/53-function-execution-flow/53-01-PLAN.md` — `_trace_execution_from_event` 修改点
- STATE.md: `.planning/STATE.md` — Phase 54 context 捕获

### Tertiary (LOW confidence)
- UE C++ source patterns for K2Node_Knot data flow — 未验证实际行为

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 全部内部模块，已验证现有实现
- Architecture: HIGH — 数据流追踪架构基于现有代码 + 参考文件推导
- Pitfalls: MEDIUM — 基于分析推导，未验证实际 Knot 循环场景
- Knot 穿透: MEDIUM — 算法设计基于 UE 文本格式，未验证实际二进制解析

**Research date:** 2026-05-17
**Valid until:** 2026-06-17（30 天 — 稳定内部代码库）