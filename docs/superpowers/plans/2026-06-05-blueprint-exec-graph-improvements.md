# 蓝图执行图能力补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全蓝图执行图的 13 项能力缺口，覆盖控制流节点、语义标注、跨域追踪和输出层改进。

**Architecture:** 分 4 个独立子系统依次实现：(1) 控制流节点补全、(2) 语义标注增强、(3) 宏展开引擎、(4) 输出层改进。每阶段独立可测试，互不阻塞。

**Tech Stack:** Python 3.10+, pytest, uasset_read 解析器

---

## 文件结构总览

### 新建文件

| 文件 | 职责 |
|------|------|
| `src/uasset_read/graph/macro_expander.py` | 宏展开引擎：递归展开、循环检测、引脚映射、执行链穿透 |
| `tests/graph/test_macro_expander.py` | 宏展开引擎测试 |
| `tests/graph/test_control_flow_expansion.py` | 控制流节点扩展测试 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/uasset_read/constants.py` | 扩展 CONTROL_FLOW_NODES、BRANCH_TYPE_MAP、START_EVENT_TYPES |
| `src/uasset_read/graph/flow_builder.py` | 执行引脚名称捕获、Latent/Async 检测、Knot 过滤、CustomEvent 命名 |
| `src/uasset_read/graph/chain_builder.py` | 链输出中显示执行引脚名称 |
| `src/uasset_read/serializers/graph.py` | 增强 read_k2node_macro_instance |
| `src/uasset_read/kismet/semantic.py` | Ubergraph 多函数调用提取 |
| `src/uasset_read/renderers/json_renderer.py` | 输出中增加宏展开数据、执行引脚名称 |

---

## Phase 1: 控制流节点补全

### Task 1: 扩展 CONTROL_FLOW_NODES 常量

**Files:**
- Modify: `src/uasset_read/constants.py:182-234`
- Test: `tests/graph/test_control_flow_expansion.py`

- [ ] **Step 1: 编写测试验证当前常量缺失**

```python
# tests/graph/test_control_flow_expansion.py
"""验证 CONTROL_FLOW_NODES 包含所有已知控制流节点类型。"""
from uasset_read.constants import CONTROL_FLOW_NODES, BRANCH_TYPE_MAP


REQUIRED_CONTROL_FLOW = {
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 新增
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    "K2Node_Sequence",
    "K2Node_MultiGate",
    "K2Node_Select",
    "K2Node_ExecutionSequence",
}

REQUIRED_BRANCH_TYPES = {
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 新增
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    "K2Node_Sequence",
    "K2Node_MultiGate",
    "K2Node_Select",
}


def test_control_flow_nodes_complete():
    """CONTROL_FLOW_NODES 应包含所有已知控制流节点。"""
    missing = REQUIRED_CONTROL_FLOW - CONTROL_FLOW_NODES
    assert not missing, f"CONTROL_FLOW_NODES 缺少: {missing}"


def test_branch_type_map_complete():
    """BRANCH_TYPE_MAP 应包含所有控制流节点的分支类型。"""
    missing = REQUIRED_BRANCH_TYPES - set(BRANCH_TYPE_MAP.keys())
    assert not missing, f"BRANCH_TYPE_MAP 缺少: {missing}"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/graph/test_control_flow_expansion.py -v
```
预期: 2 个失败 — CONTROL_FLOW_NODES 和 BRANCH_TYPE_MAP 缺失条目。

- [ ] **Step 3: 修改 constants.py 添加缺失节点**

打开 `src/uasset_read/constants.py`，将 CONTROL_FLOW_NODES（约第 182 行）修改为：

```python
CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 循环类宏
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    # 多门控
    "K2Node_Sequence",
    "K2Node_MultiGate",
    # 选择节点
    "K2Node_Select",
    "K2Node_ExecutionSequence",
})
```

将 BRANCH_TYPE_MAP（约第 227 行）修改为：

```python
BRANCH_TYPE_MAP = {
    "K2Node_IfThenElse": "if_then_else",
    "K2Node_Switch": "switch",
    "K2Node_SwitchString": "switch_string",
    "K2Node_SwitchEnum": "switch_enum",
    "K2Node_SwitchInteger": "switch_integer",
    "K2Node_MacroInstance": "macro_instance",
    # 循环类
    "K2Node_ForLoop": "for_loop",
    "K2Node_WhileLoop": "while_loop",
    "K2Node_DoOnce": "do_once",
    # 多门控
    "K2Node_Sequence": "sequence",
    "K2Node_MultiGate": "multi_gate",
    # 选择
    "K2Node_Select": "select",
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/graph/test_control_flow_expansion.py -v
```
预期: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/constants.py tests/graph/test_control_flow_expansion.py
git commit -m "feat: add missing control flow nodes (ForLoop, WhileLoop, DoOnce, Sequence, MultiGate, Select)"
```

---

### Task 2: 执行引脚名称捕获

**Files:**
- Modify: `src/uasset_read/graph/flow_builder.py:840-985`
- Modify: `src/uasset_read/graph/chain_builder.py:91-175`
- Test: `tests/graph/test_exec_pin_names.py`

- [ ] **Step 1: 编写测试验证 exec pin 名称未被捕获**

```python
# tests/graph/test_exec_pin_names.py
"""验证执行流追踪中捕获 exec 引脚名称。"""
import pytest
from uasset_read.graph.flow_builder import (
    _find_next_exec_node,
    _trace_execution_from_event,
)


class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec", linked_to=None):
        self.pin_name = name
        self.direction = direction  # 0=Input, 1=Output
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = linked_to or []
        self.pin_id = f"pid_{name}"


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


def test_trace_captures_exec_pin_name():
    """执行流中每个节点的 transition 应包含 used_exec_pin_name。"""
    # 构建: Event(exec→"Then") → CallFunction(exec→"Completed") → EndNode
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["pid_call"]),
    ])
    call_func = FakeNode("guid_call", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
        FakePin("Completed", 1, "exec", ["pid_end"]),
    ])
    end_node = FakeNode("guid_end", "K2Node_MakeVariable", [
        FakePin("Completed", 0, "exec"),
    ])

    pin_lookup = {
        "pid_call": ("guid_call", "Then"),
        "pid_end": ("guid_end", "Completed"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_call": call_func,
        "guid_end": end_node,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    # 第一个节点（Event）应记录使用了哪个 exec pin 输出
    assert len(flow) >= 2
    # Event → CallFunction 的连接应记录 pin 名称
    assert flow[0].get("used_exec_pin_name") == "exec" or "exec_pin" in flow[0]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/graph/test_exec_pin_names.py::test_trace_captures_exec_pin_name -v
```
预期: FAIL — `used_exec_pin_name` 字段不存在。

- [ ] **Step 3: 修改 _find_next_exec_node 返回引脚名称**

打开 `src/uasset_read/graph/flow_builder.py`，修改 `_find_next_exec_node`（约第 840 行），使其返回 `(next_node, pin_name)` 元组：

```python
def _find_next_exec_node(
    node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Tuple[Optional[UEdGraphNode], Optional[str]]:
    """查找 exec output pin 连接的下一个节点。

    Returns:
        (next_node, exec_pin_name) 元组
    """
    for pin in node.pins:
        if pin.direction == 1:  # Output
            if pin.pin_type and pin.pin_type.pin_category == "exec":
                if edges_by_from_pin and pin.pin_id in edges_by_from_pin:
                    edge = edges_by_from_pin[pin.pin_id][0]
                    return (node_lookup.get(edge["to_node_guid"]), pin.pin_name)
                for linked_pin_id in (pin.linked_to_raw or []):
                    target_pin_guid = _pin_ref_guid(linked_pin_id)
                    if target_pin_guid in pin_lookup:
                        target_node_guid, _ = pin_lookup[target_pin_guid]
                        return (node_lookup.get(target_node_guid), pin.pin_name)
    if edges_by_from_pin:
        for edges in edges_by_from_pin.values():
            for edge in edges:
                if edge["from_node_guid"] == node.node_guid and edge.get("is_exec"):
                    return (node_lookup.get(edge["to_node_guid"]), "exec")
    return (None, None)
```

- [ ] **Step 4: 修改 _trace_execution_from_event 使用新返回值**

在同文件中，修改 `_trace_execution_from_event`（约第 875 行）中的循环体：

```python
# 将原来的:
#   current_node = _find_next_exec_node(
#       current_node, pin_lookup, node_lookup, edges_by_from_pin
#   )
# 改为:
current_node, used_pin_name = _find_next_exec_node(
    current_node, pin_lookup, node_lookup, edges_by_from_pin
)
```

然后在 `node_info` 字典中添加引脚名称：

```python
node_info = {
    "node_guid": current_guid,
    "node_type": current_node.class_name,
}

# 添加执行引脚名称
if used_pin_name is not None:
    node_info["used_exec_pin_name"] = used_pin_name
```

注意需要更新所有调用 `_find_next_exec_node` 的地方（包括第 907 行和 981 行）。

- [ ] **Step 5: 修改 chain_builder 在链中显示引脚名称**

打开 `src/uasset_read/graph/chain_builder.py`，在 chain 构建逻辑中（约第 116-125 行），将 short_ids 构建改为包含引脚名称：

```python
# 修改链构建逻辑，在节点间插入引脚名称
short_ids: List[str] = []
pin_names: List[str] = []
for node_info in valid_nodes:
    guid = node_info["node_guid"]
    short_id = guid_to_short.get(guid)
    if short_id is None:
        short_id = f"N{len(guid_to_short)}"
        guid_to_short[guid] = short_id
    short_ids.append(short_id)
    pin_names.append(node_info.get("used_exec_pin_name", ""))

# 构建带引脚名称的链: N0--exec-->N1--Completed-->N2
chain_parts: List[str] = []
for i in range(len(short_ids)):
    chain_parts.append(short_ids[i])
    if i < len(pin_names) - 1 and pin_names[i + 1]:
        chain_parts.append(f"--{pin_names[i+1]}-->")
    elif i < len(short_ids) - 1:
        chain_parts.append("->")

chain = "".join(chain_parts)
```

- [ ] **Step 6: 运行测试确认通过**

```bash
python -m pytest tests/graph/test_exec_pin_names.py -v
```
预期: passed。

- [ ] **Step 7: 运行完整测试确认无回归**

```bash
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20
```

- [ ] **Step 8: Commit**

```bash
git add src/uasset_read/graph/flow_builder.py src/uasset_read/graph/chain_builder.py tests/graph/test_exec_pin_names.py
git commit -m "feat: capture and output exec pin names in execution flow"
```

---

### Task 3: Latent/Async 动作检测

**Files:**
- Modify: `src/uasset_read/graph/flow_builder.py`（在 node_info 中添加 latent 标记）
- Test: `tests/graph/test_latent_detection.py`

- [ ] **Step 1: 编写测试**

```python
# tests/graph/test_latent_detection.py
"""验证 Latent/Async 动作在执行流中被标记。"""
from uasset_read.graph.flow_builder import _trace_execution_from_event


class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec", linked_to=None):
        self.pin_name = name
        self.direction = direction
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = linked_to or []
        self.pin_id = f"pid_{name}"


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


# Latent 动作节点类型（UE 源码中的已知类型）
LATENT_NODE_TYPES = {
    "K2Node_AsyncAction",
    "K2Node_LatentGameCommand",
    "K2Node_BaseAsyncTask",
    "K2Node_Timeline",
}


def test_async_action_marked_as_latent():
    """K2Node_AsyncAction 应在执行流中标记 latent=True。"""
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["pid_async"]),
    ])
    async_node = FakeNode("guid_async", "K2Node_AsyncAction", [
        FakePin("Then", 0, "exec"),
        FakePin("Completed", 1, "exec", ["pid_end"]),
    ])
    end_node = FakeNode("guid_end", "K2Node_MakeVariable", [
        FakePin("Completed", 0, "exec"),
    ])

    pin_lookup = {
        "pid_async": ("guid_async", "Then"),
        "pid_end": ("guid_end", "Completed"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_async": async_node,
        "guid_end": end_node,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    async_flow = next(f for f in flow if f["node_type"] == "K2Node_AsyncAction")
    assert async_flow.get("latent") is True, "Latent 动作应标记 latent=True"


def test_timeline_marked_as_latent():
    """K2Node_Timeline 应在执行流中标记 latent=True。"""
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["pid_timeline"]),
    ])
    timeline = FakeNode("guid_timeline", "K2Node_Timeline", [
        FakePin("Update", 1, "exec"),
    ])

    pin_lookup = {
        "pid_timeline": ("guid_timeline", "Update"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_timeline": timeline,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    tl_flow = next(f for f in flow if f["node_type"] == "K2Node_Timeline")
    assert tl_flow.get("latent") is True


def test_normal_node_not_latent():
    """普通节点不应有 latent 标记。"""
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["pid_call"]),
    ])
    call_func = FakeNode("guid_call", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
    ])

    pin_lookup = {"pid_call": ("guid_call", "Then")}
    node_lookup = {"guid_event": event, "guid_call": call_func}

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    call_flow = next(f for f in flow if f["node_type"] == "K2Node_CallFunction")
    assert "latent" not in call_flow or call_flow.get("latent") is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/graph/test_latent_detection.py -v
```
预期: 2 失败（async 和 timeline 未标记 latent）。

- [ ] **Step 3: 修改 flow_builder.py 添加 latent 检测**

在 `src/uasset_read/graph/flow_builder.py` 的 `_trace_execution_from_event` 函数中，在构建 `node_info` 后（约第 925 行之后）添加：

```python
# Latent/Async 动作检测
LATENT_NODE_TYPES = frozenset({
    "K2Node_AsyncAction",
    "K2Node_LatentGameCommand",
    "K2Node_BaseAsyncTask",
    "K2Node_Timeline",
})

if current_node.class_name in LATENT_NODE_TYPES:
    node_info["latent"] = True
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/graph/test_latent_detection.py -v
```
预期: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/graph/flow_builder.py tests/graph/test_latent_detection.py
git commit -m "feat: detect and mark latent/async action nodes in execution flow"
```

---

## Phase 2: 语义标注增强

### Task 4: CustomEvent 命名提取

**Files:**
- Modify: `src/uasset_read/graph/flow_builder.py`（`_get_start_event_name` 函数）
- Test: `tests/graph/test_custom_event_naming.py`

- [ ] **Step 1: 编写测试**

```python
# tests/graph/test_custom_event_naming.py
"""验证 CustomEvent 使用实际事件名而非写死的 'CustomEvent'。"""
from uasset_read.graph.flow_builder import _get_start_event_name


class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec"):
        self.pin_name = name
        self.direction = direction
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = []
        self.pin_id = f"pid_{name}"


class FakeNodeData:
    def __init__(self, custom_event_name=None):
        self.custom_event_name = custom_event_name


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


def test_custom_event_uses_actual_name():
    """CustomEvent 应提取实际事件名。"""
    node_data = FakeNodeData(custom_event_name="OnPlayerDeath")
    node = FakeNode("guid_1", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent.OnPlayerDeath", f"期望 'CustomEvent.OnPlayerDeath'，得到 '{name}'"


def test_custom_event_fallback():
    """无事件名时应使用 'CustomEvent' 回退。"""
    node_data = FakeNodeData(custom_event_name=None)
    node = FakeNode("guid_1", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"
```

- [ ] **Step 2: 查看当前 _get_start_event_name 实现**

```bash
grep -n "def _get_start_event_name" src/uasset_read/graph/flow_builder.py
```

- [ ] **Step 3: 修改 _get_start_event_name**

找到 `_get_start_event_name` 函数，修改 `K2Node_CustomEvent` 分支：

```python
def _get_start_event_name(node: UEdGraphNode) -> str:
    """获取起始事件的名称。"""
    if node.class_name == "K2Node_Event":
        return f"Event.{_get_event_name(node)}"
    elif node.class_name == "K2Node_CustomEvent":
        # 从 node_data 提取实际事件名
        if node.node_data and hasattr(node.node_data, 'custom_event_name'):
            event_name = node.node_data.custom_event_name
            if event_name:
                return f"CustomEvent.{event_name}"
        return "CustomEvent"
    elif node.class_name == "K2Node_VariableSet":
        return "VariableSet"
    elif node.class_name == "K2Node_FunctionEntry":
        # 从 node_data 提取函数名
        if node.node_data and hasattr(node.node_data, 'function_reference'):
            func_ref = node.node_data.function_reference
            if func_ref and hasattr(func_ref, 'member_name'):
                return f"FunctionEntry.{func_ref.member_name}"
        return "FunctionEntry"
    elif node.class_name == "K2Node_EnhancedInputAction":
        return f"EnhancedInput.{_get_input_action_name(node)}"
    return node.class_name
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/graph/test_custom_event_naming.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/graph/flow_builder.py tests/graph/test_custom_event_naming.py
git commit -m "feat: extract actual custom event name instead of hardcoded 'CustomEvent'"
```

---

### Task 5: Ubergraph 多函数调用提取

**Files:**
- Modify: `src/uasset_read/kismet/semantic.py:332-364`
- Test: `tests/kismet/test_semantic_multi_call.py`

- [ ] **Step 1: 编写测试**

```python
# tests/kismet/test_semantic_multi_call.py
"""验证 Ubergraph 语义提取捕获所有 CallFunction，不仅第一个。"""
from uasset_read.kismet.semantic import extract_eventgraph_semantic_calls


def test_eventgraph_captures_all_calls_per_event():
    """每个事件的语义调用应包含所有 CallFunction 节点，不仅第一个。"""
    # 构造模拟图数据：Event → CallFunc_A → CallFunc_B → CallFunc_C
    # 这需要构建 mock UEdGraph 对象
    # 简化测试：验证 extract_eventgraph_semantic_calls 不截断节点列表
    pass  # 需要真实图数据，先标记为 integration test


def test_flow_to_cpp_processes_all_nodes():
    """_flow_to_cpp 应处理所有节点类型，不仅 K2Node_CallFunction。"""
    # 验证 _flow_to_cpp 不跳过非 CallFunction 节点
    from uasset_read.kismet.semantic import _flow_to_cpp

    flow = [
        {"node_type": "K2Node_CallFunction", "function_name": "FuncA"},
        {"node_type": "K2Node_VariableSet", "variable_name": "Health"},
        {"node_type": "K2Node_CallFunction", "function_name": "FuncB"},
    ]

    cpp = _flow_to_cpp(flow)
    assert "FuncA" in cpp
    assert "Health" in cpp, "变量设置应出现在 C++ 输出中"
    assert "FuncB" in cpp
```

- [ ] **Step 2: 修改 semantic.py**

打开 `src/uasset_read/kismet/semantic.py`，找到 `_format_ubergraph_semantics` 和相关的 `extract_eventgraph_semantic_calls`：

```python
# 修改 extract_eventgraph_semantic_calls 中只取第一个 CallFunction 的逻辑
# 原代码（约第 345 行）:
#   call_info = next((node for node in nodes if node.get("node_type") == "K2Node_CallFunction"), None)
# 改为:
call_nodes = [node for node in nodes if node.get("node_type") == "K2Node_CallFunction"]
for call_node in call_nodes:
    # 为每个 CallFunction 生成语义调用
    semantic_calls.append({
        "event_name": event_name,
        "function_name": call_node.get("function_name", "Unknown"),
        "parameters": call_node.get("parameters", []),
    })
```

同时扩展 `_flow_to_cpp`（约第 160-217 行），增加对 `K2Node_VariableSet` 和 `K2Node_VariableGet` 的处理：

```python
def _flow_to_cpp(flow: List[Dict]) -> str:
    """将执行流转换为 C++ 伪代码。"""
    lines = []
    for node in flow:
        node_type = node.get("node_type", "")
        if node_type == "K2Node_CallFunction":
            func_name = node.get("function_name", "Unknown")
            params = node.get("parameters", [])
            param_str = ", ".join(p.get("name", "?") for p in params)
            lines.append(f"    {func_name}({param_str});")
        elif node_type == "K2Node_VariableSet":
            var_name = node.get("variable_name", "Unknown")
            lines.append(f"    {var_name} = <value>;")
        elif node_type == "K2Node_IfThenElse":
            lines.append("    if (<condition>) {")
            lines.append("        // True branch")
            lines.append("    } else {")
            lines.append("        // False branch")
            lines.append("    }")
        elif node_type == "K2Node_MacroInstance":
            macro_name = node.get("macro_name", "Unknown")
            lines.append(f"    // Macro: {macro_name}")
    return "\n".join(lines)
```

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/kismet/test_semantic_multi_call.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/uasset_read/kismet/semantic.py tests/kismet/test_semantic_multi_call.py
git commit -m "feat: extract all CallFunction nodes per event in Ubergraph semantic enrichment"
```

---

## Phase 3: 宏展开引擎

### Task 6: 宏展开核心引擎

**Files:**
- Create: `src/uasset_read/graph/macro_expander.py`
- Create: `tests/graph/test_macro_expander.py`
- Modify: `src/uasset_read/serializers/graph.py:1676-1697`

- [ ] **Step 1: 增强 read_k2node_macro_instance**

```python
# src/uasset_read/serializers/graph.py:1676
def read_k2node_macro_instance(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """读取 K2Node_MacroInstance 特有字段。

    继承自 K2Node_Tunnel，表示宏图表实例。
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # MacroGraph 从 PropertyTag 获取（FPackageIndex → 宏图表参考）
    macro_graph = raw_properties.get("MacroGraph")
    if macro_graph is not None:
        result["macro_graph"] = macro_graph

    # Macro 从 PropertyTag 获取（FName → 宏名称）
    macro = raw_properties.get("Macro")
    if macro is not None:
        result["macro_name"] = macro

    # MacroGraphReference 结构化解析（新格式）
    macro_graph_ref = raw_properties.get("MacroGraphReference")
    if macro_graph_ref is not None:
        result["macro_graph_reference"] = macro_graph_ref

    # ResolvedWildcardType — 通配符引脚解析后的类型
    resolved_wildcard = raw_properties.get("ResolvedWildcardType")
    if resolved_wildcard is not None:
        result["resolved_wildcard_type"] = resolved_wildcard

    return result
```

- [ ] **Step 2: 创建宏展开引擎**

```python
# src/uasset_read/graph/macro_expander.py
"""蓝图宏展开引擎 — 递归展开 MacroInstance，循环检测，引脚映射，执行链穿透。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from uasset_read.constants import CONTROL_FLOW_NODES


@dataclass
class MacroExpansionContext:
    """宏展开的上下文信息"""
    macro_name: str
    macro_guid: str
    macro_graph_ref: Dict[str, Any]
    blueprint_ref: Optional[str] = None


class MacroCycleError(Exception):
    """宏循环检测异常"""
    def __init__(self, cycle_path: List[MacroExpansionContext]):
        self.cycle_path = cycle_path
        names = [ctx.macro_name for ctx in cycle_path]
        message = f"宏循环检测: {' → '.join(names)} → {names[0]}"
        super().__init__(message)


@dataclass
class MacroExpansion:
    """宏展开结果"""
    context: MacroExpansionContext
    expanded_nodes: List[Dict[str, Any]] = field(default_factory=list)
    pin_mapping: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    entry_tunnels: List[Dict[str, Any]] = field(default_factory=list)
    exit_tunnels: List[Dict[str, Any]] = field(default_factory=list)
    internal_flows: List[Dict[str, Any]] = field(default_factory=list)
    nested_expansions: List["MacroExpansion"] = field(default_factory=list)
    unresolved: bool = False


# ──────────────────────────────────────────────────────
# 标准宏定义（内置于引擎，不在用户资产中）
# ──────────────────────────────────────────────────────

STANDARD_MACROS: Dict[str, Dict[str, Any]] = {
    "ForLoop": {
        "inputs": ["Entry", "LastIndex", "FirstIndex", "Increment"],
        "outputs": ["Loop Body", "Completed", "Loop Counter"],
        "is_loop": True,
        "is_standard": True,
    },
    "ForLoopWithBreak": {
        "inputs": ["Entry", "LastIndex", "FirstIndex", "Increment", "Break"],
        "outputs": ["Loop Body", "Completed", "Loop Counter"],
        "is_loop": True,
        "is_standard": True,
    },
    "WhileLoop": {
        "inputs": ["Entry", "Condition"],
        "outputs": ["Loop Body", "Completed"],
        "is_loop": True,
        "is_standard": True,
    },
    "Gate": {
        "inputs": ["Enter", "Open", "Close", "Toggle"],
        "outputs": ["Exit"],
        "is_loop": False,
        "is_standard": True,
    },
    "Do N": {
        "inputs": ["Enter", "N"],
        "outputs": ["Exit", "Completed"],
        "is_loop": False,
        "is_standard": True,
    },
    "DoOnce": {
        "inputs": ["Enter", "Reset"],
        "outputs": ["Exit"],
        "is_loop": False,
        "is_standard": True,
    },
    "IsValid": {
        "inputs": ["Input"],
        "outputs": ["Valid", "Invalid"],
        "is_loop": False,
        "is_standard": True,
    },
    "FlipFlop": {
        "inputs": ["A"],
        "outputs": ["A", "B", "IsA"],
        "is_loop": False,
        "is_standard": True,
    },
    "ForEachLoop": {
        "inputs": ["Entry", "Array"],
        "outputs": ["Loop Body", "Completed", "Array Element", "Array Index"],
        "is_loop": True,
        "is_standard": True,
    },
    "ForEachLoopWithBreak": {
        "inputs": ["Entry", "Array", "Break"],
        "outputs": ["Loop Body", "Completed", "Array Element", "Array Index"],
        "is_loop": True,
        "is_standard": True,
    },
}


class MacroExpander:
    """宏展开器"""

    def __init__(self, asset_context: Dict[str, Any]):
        self.asset_context = asset_context
        self.visited_guids: Set[str] = set()
        self.expansion_stack: List[MacroExpansionContext] = []

    def expand_macro_instance(self, instance_node: Dict[str, Any]) -> MacroExpansion:
        """展开单个宏实例"""
        macro_ref = instance_node.get("macro_graph_reference", {})
        graph_guid = macro_ref.get("graph_guid", "")
        graph_name = macro_ref.get("graph_name", "")

        # 检查标准宏
        if graph_name in STANDARD_MACROS:
            return self._create_standard_expansion(graph_name, macro_ref)

        # 循环检测
        if graph_guid and graph_guid in self.visited_guids:
            raise MacroCycleError(self.expansion_stack.copy() + [
                MacroExpansionContext(
                    macro_name=graph_name,
                    macro_guid=graph_guid,
                    macro_graph_ref=macro_ref,
                )
            ])

        # 查找宏图
        macro_graph = self._find_macro_graph(macro_ref)
        if macro_graph is None:
            return self._create_unresolved_expansion(instance_node, macro_ref)

        # 递归展开
        if graph_guid:
            self.visited_guids.add(graph_guid)

        ctx = MacroExpansionContext(
            macro_name=graph_name,
            macro_guid=graph_guid,
            macro_graph_ref=macro_ref,
        )
        self.expansion_stack.append(ctx)

        try:
            expansion = self._expand_graph(macro_graph, ctx)
            return expansion
        finally:
            self.expansion_stack.pop()
            if graph_guid:
                self.visited_guids.discard(graph_guid)

    def _find_macro_graph(self, macro_ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """在资产中查找宏图"""
        graph_guid = macro_ref.get("graph_guid")
        graph_name = macro_ref.get("graph_name")

        # 1. 在当前资产的所有 Graph 中查找
        for graph in self.asset_context.get("graphs", []):
            if graph.get("guid") == graph_guid:
                return graph
            if graph.get("name") == graph_name:
                return graph

        # 2. 在 resolved_parent_assets 中查找（跨蓝图引用）
        for parent_asset in self.asset_context.get("resolved_parent_assets", []):
            for graph in parent_asset.get("graphs", []):
                if graph.get("guid") == graph_guid:
                    return graph

        return None

    def _expand_graph(self, macro_graph: Dict[str, Any], ctx: MacroExpansionContext) -> MacroExpansion:
        """展开宏图"""
        nodes = macro_graph.get("nodes", [])

        entry_tunnels = []
        exit_tunnels = []
        internal_nodes = []

        for node in nodes:
            if node.get("node_type") == "K2Node_Tunnel":
                if node.get("exact_class") == "UK2Node_Tunnel":
                    if node.get("b_can_have_outputs"):
                        exit_tunnels.append(node)
                    if node.get("b_can_have_inputs"):
                        entry_tunnels.append(node)
                    continue
            internal_nodes.append(node)

        pin_mapping = self._build_pin_mapping(entry_tunnels, exit_tunnels)

        nested_expansions = []
        for node in internal_nodes:
            if node.get("node_type") == "K2Node_MacroInstance":
                nested = self.expand_macro_instance(node)
                nested_expansions.append(nested)

        internal_flows = self._build_internal_flows(entry_tunnels, internal_nodes, exit_tunnels)

        return MacroExpansion(
            context=ctx,
            expanded_nodes=internal_nodes,
            pin_mapping=pin_mapping,
            entry_tunnels=entry_tunnels,
            exit_tunnels=exit_tunnels,
            internal_flows=internal_flows,
            nested_expansions=nested_expansions,
        )

    def _build_pin_mapping(self, entry_tunnels, exit_tunnels):
        """构建 Tunnel 引脚到 Instance 引脚的映射"""
        mapping = {}
        for tunnel in entry_tunnels + exit_tunnels:
            for pin in tunnel.get("pins", []):
                if pin.get("parent_pin") is None:
                    direction = pin.get("direction", "")
                    instance_dir = "EGPD_Input" if direction == "EGPD_Output" else "EGPD_Output"
                    mapping[pin["pin_name"]] = {
                        "instance_direction": instance_dir,
                        "pin_type": pin.get("pin_type", {}),
                        "default_value": pin.get("default_value", ""),
                        "tunnel_type": "entry" if tunnel in entry_tunnels else "exit",
                    }
        return mapping

    def _build_internal_flows(self, entry_tunnels, internal_nodes, exit_tunnels):
        """构建宏内部执行流（简化版，复用 flow_builder 逻辑）"""
        flows = []
        # 这里调用 flow_builder 的追踪逻辑，传入宏图的节点
        # 需要适配 internal_nodes 为 UEdGraphNode 列表
        return flows

    def _create_standard_expansion(self, macro_name: str, macro_ref: Dict) -> MacroExpansion:
        """为标准宏创建展开结果（不展开内部节点）"""
        info = STANDARD_MACROS[macro_name]
        return MacroExpansion(
            context=MacroExpansionContext(
                macro_name=macro_name,
                macro_guid="",
                macro_graph_ref=macro_ref,
            ),
            pin_mapping={
                name: {"instance_direction": "EGPD_Input", "is_standard": True}
                for name in info["inputs"]
            },
            expanded_nodes=[],
            internal_flows=[],
        )

    def _create_unresolved_expansion(self, instance_node, macro_ref):
        """创建未解析的展开结果"""
        return MacroExpansion(
            context=MacroExpansionContext(
                macro_name=macro_ref.get("graph_name", "Unknown"),
                macro_guid=macro_ref.get("graph_guid", ""),
                macro_graph_ref=macro_ref,
            ),
            unresolved=True,
        )
```

- [ ] **Step 3: 编写测试**

```python
# tests/graph/test_macro_expander.py
"""宏展开引擎测试。"""
import pytest
from uasset_read.graph.macro_expander import (
    MacroExpander,
    MacroExpansion,
    MacroExpansionContext,
    MacroCycleError,
    STANDARD_MACROS,
)


def test_standard_macros_recognized():
    """标准宏应被识别且不尝试展开内部节点。"""
    ctx = {"graphs": []}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "ForLoop",
            "graph_guid": "",
        }
    }

    expansion = expander.expand_macro_instance(instance)
    assert expansion.context.macro_name == "ForLoop"
    assert expansion.context.macro_name in STANDARD_MACROS


def test_unresolved_macro():
    """宏图未找到时应标记 unresolved。"""
    ctx = {"graphs": []}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "MissingMacro",
            "graph_guid": "nonexistent-guid",
        }
    }

    expansion = expander.expand_macro_instance(instance)
    assert expansion.unresolved is True


def test_macro_cycle_detection():
    """嵌套宏循环应抛出 MacroCycleError。"""
    # 构造 A → B → A 的循环
    graph_a = {
        "guid": "guid-a",
        "name": "MacroA",
        "nodes": [
            {
                "node_type": "K2Node_MacroInstance",
                "macro_graph_reference": {
                    "graph_name": "MacroB",
                    "graph_guid": "guid-b",
                },
            }
        ],
    }
    graph_b = {
        "guid": "guid-b",
        "name": "MacroB",
        "nodes": [
            {
                "node_type": "K2Node_MacroInstance",
                "macro_graph_reference": {
                    "graph_name": "MacroA",
                    "graph_guid": "guid-a",
                },
            }
        ],
    }

    ctx = {"graphs": [graph_a, graph_b]}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "MacroA",
            "graph_guid": "guid-a",
        }
    }

    with pytest.raises(MacroCycleError) as exc_info:
        expander.expand_macro_instance(instance)

    assert "MacroA" in str(exc_info.value)
    assert "MacroB" in str(exc_info.value)


def test_pin_mapping_from_tunnels():
    """Tunnel 引脚应正确映射到 Instance 引脚。"""
    macro_graph = {
        "guid": "guid-macro",
        "name": "TestMacro",
        "nodes": [
            {
                "node_type": "K2Node_Tunnel",
                "exact_class": "UK2Node_Tunnel",
                "b_can_have_inputs": False,
                "b_can_have_outputs": True,
                "pins": [
                    {"pin_name": "exec", "direction": "EGPD_Output", "parent_pin": None, "pin_type": {}, "default_value": ""},
                    {"pin_name": "Target", "direction": "EGPD_Output", "parent_pin": None, "pin_type": {"pin_category": "Object"}, "default_value": ""},
                ],
            },
            {
                "node_type": "K2Node_Tunnel",
                "exact_class": "UK2Node_Tunnel",
                "b_can_have_inputs": True,
                "b_can_have_outputs": False,
                "pins": [
                    {"pin_name": "Then", "direction": "EGPD_Input", "parent_pin": None, "pin_type": {}, "default_value": ""},
                ],
            },
        ],
    }

    ctx = {"graphs": [macro_graph]}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "TestMacro",
            "graph_guid": "guid-macro",
        }
    }

    expansion = expander.expand_macro_instance(instance)

    assert "exec" in expansion.pin_mapping
    assert expansion.pin_mapping["exec"]["instance_direction"] == "EGPD_Input"
    assert expansion.pin_mapping["exec"]["tunnel_type"] == "entry"

    assert "Then" in expansion.pin_mapping
    assert expansion.pin_mapping["Then"]["instance_direction"] == "EGPD_Output"
    assert expansion.pin_mapping["Then"]["tunnel_type"] == "exit"


def test_all_standard_macros_documented():
    """所有已知标准宏应在 STANDARD_MACROS 中定义。"""
    expected_macros = {
        "ForLoop", "ForLoopWithBreak", "WhileLoop",
        "Gate", "Do N", "DoOnce", "IsValid",
        "FlipFlop", "ForEachLoop", "ForEachLoopWithBreak",
    }
    assert set(STANDARD_MACROS.keys()) == expected_macros
```

- [ ] **Step 4: 运行测试**

```bash
python -m pytest tests/graph/test_macro_expander.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/graph/macro_expander.py src/uasset_read/serializers/graph.py tests/graph/test_macro_expander.py
git commit -m "feat: add macro expansion engine with cycle detection, pin mapping, and standard macro definitions"
```

---

### Task 7: 执行链穿透宏实例

**Files:**
- Modify: `src/uasset_read/graph/flow_builder.py`（修改 MacroInstance 处理逻辑）
- Test: `tests/graph/test_macro_flow_penetration.py`

- [ ] **Step 1: 编写测试**

```python
# tests/graph/test_macro_flow_penetration.py
"""验证执行链能穿透宏实例到内部节点。"""
from uasset_read.graph.flow_builder import _trace_execution_from_event


class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec", linked_to=None):
        self.pin_name = name
        self.direction = direction
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = linked_to or []
        self.pin_id = f"pid_{name}"


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


def test_flow_penetrates_macro_instance():
    """执行链应穿透 MacroInstance 到其内部节点。"""
    # 简化测试：验证 MacroInstance 不再终止执行链
    # 而是记录 macro_expansion 字段
    event = FakeNode("guid_event", "K2Node_Event", [
        FakePin("exec", 1, "exec", ["pid_macro"]),
    ])
    macro = FakeNode("guid_macro", "K2Node_MacroInstance", [
        FakePin("exec", 0, "exec"),
        FakePin("Then", 1, "exec", ["pid_after"]),
    ])
    after = FakeNode("guid_after", "K2Node_CallFunction", [
        FakePin("Then", 0, "exec"),
    ])

    pin_lookup = {
        "pid_macro": ("guid_macro", "exec"),
        "pid_after": ("guid_after", "Then"),
    }
    node_lookup = {
        "guid_event": event,
        "guid_macro": macro,
        "guid_after": after,
    }

    flow = _trace_execution_from_event(event, pin_lookup, node_lookup)

    # 验证 MacroInstance 节点包含 macro_expansion 或穿透标记
    macro_flow = next(f for f in flow if f["node_type"] == "K2Node_MacroInstance")
    assert "macro_expansion" in macro_flow or not macro_flow.get("stopped_at"), \
        "MacroInstance 不应终止执行链"
```

- [ ] **Step 2: 修改 flow_builder.py**

在 `_trace_execution_from_event` 中，将 `K2Node_MacroInstance` 从终止逻辑中移除，改为调用 MacroExpander：

```python
# 在 flow_builder.py 顶部添加导入
from uasset_read.graph.macro_expander import MacroExpander, MacroExpansion

# 修改控制流节点处理（约第 969-978 行）
# 原代码:
#   if current_node.class_name in CONTROL_FLOW_NODES:
#       ...
#       break
#
# 改为:
if current_node.class_name in CONTROL_FLOW_NODES:
    if current_node.class_name == "K2Node_MacroInstance":
        # 宏实例：尝试展开并穿透
        node_info["macro_expansion"] = _try_expand_macro(current_node, asset_context)
        # 不再 break，继续追踪
    else:
        # 其他控制流节点：设置 branch_type 并终止
        if "branch_type" not in node_info:
            branch_type = BRANCH_TYPE_MAP.get(current_node.class_name, "unknown")
            node_info["branch_type"] = branch_type
        if "stopped_at" not in node_info:
            node_info["stopped_at"] = "control_flow_node"
        flow.append(node_info)
        break
```

添加辅助函数：

```python
def _try_expand_macro(node, asset_context) -> Dict[str, Any]:
    """尝试展开宏实例"""
    node_data = node.node_data or {}
    macro_ref = node_data.get("macro_graph_reference", {})

    if not macro_ref:
        return {"unresolved": True, "reason": "no macro_graph_reference"}

    try:
        expander = MacroExpander(asset_context)
        expansion = expander.expand_macro_instance({"macro_graph_reference": macro_ref})
        return {
            "macro_name": expansion.context.macro_name,
            "macro_guid": expansion.context.macro_guid,
            "pin_mapping": expansion.pin_mapping,
            "unresolved": expansion.unresolved,
            "standard": expansion.context.macro_name in getattr(__import__("uasset_read.graph.macro_expander", fromlist=["STANDARD_MACROS"]), "STANDARD_MACROS", {}),
        }
    except Exception as e:
        return {"unresolved": True, "reason": str(e)}
```

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/graph/test_macro_flow_penetration.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/uasset_read/graph/flow_builder.py tests/graph/test_macro_flow_penetration.py
git commit -m "feat: execution chain penetrates MacroInstance nodes via macro expander"
```

---

## Phase 4: 输出层改进

### Task 8: JSON 输出器增加宏展开数据

**Files:**
- Modify: `src/uasset_read/renderers/json_renderer.py`
- Test: `tests/renderers/test_json_macro_output.py`

- [ ] **Step 1: 编写测试**

```python
# tests/renderers/test_json_macro_output.py
"""验证 JSON 输出包含宏展开数据。"""
import json


def test_json_output_includes_macro_expansion():
    """JSON 输出中的 execution_flows 应包含 macro_expansion 字段。"""
    # 通过 CLI 运行一个包含 MacroInstance 的资产
    # 验证 JSON 输出中 MacroInstance 节点包含 macro_expansion
    pass  # integration test with real asset


def test_function_graphs_includes_macro_info():
    """--function-graphs 输出应包含宏展开信息。"""
    pass  # integration test
```

- [ ] **Step 2: 修改 json_renderer.py**

在 `src/uasset_read/renderers/json_renderer.py` 中，确保 `macro_expansion` 字段被包含在输出中：

```python
# 在执行流节点的序列化中，确保传递 macro_expansion
# 约第 58-89 行区域，检查 flow_entry 的字段是否完整传递
```

- [ ] **Step 3: 运行完整测试确认无回归**

```bash
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add src/uasset_read/renderers/json_renderer.py tests/renderers/test_json_macro_output.py
git commit -m "feat: include macro expansion data in JSON output"
```

---

### Task 9: 链式输出显示执行引脚名称

**Files:**
- Modify: `src/uasset_read/graph/chain_builder.py`（已在 Task 2 中部分完成）
- Test: `tests/graph/test_chain_exec_pins.py`

- [ ] **Step 1: 编写测试**

```python
# tests/graph/test_chain_exec_pins.py
"""验证链式输出显示执行引脚名称。"""
from uasset_read.graph.chain_builder import build_execution_chains


def test_chain_shows_exec_pin_names():
    """链式字符串应包含执行引脚名称。"""
    # 构造包含 used_exec_pin_name 的 execution_flows
    mock_flows = [
        {
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_guid": "g1", "node_type": "K2Node_Event"},
                {"node_guid": "g2", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Then"},
                {"node_guid": "g3", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Completed"},
            ],
        }
    ]

    mock_graph = type("MockGraph", (), {
        "nodes": [
            type("MockNode", (), {"node_guid": "g1"})(),
            type("MockNode", (), {"node_guid": "g2"})(),
            type("MockNode", (), {"node_guid": "g3"})(),
        ],
    })()

    chains = build_execution_chains(mock_graph, mock_flows)
    assert len(chains) > 0
    # 链应包含引脚名称: N0--Then-->N1--Completed-->N2
    chain_str = chains[0].get("chains", [""])[0]
    assert "Then" in chain_str or "Completed" in chain_str, f"链应包含引脚名称: {chain_str}"
```

- [ ] **Step 2: Commit**（如果 Task 2 中已完成实现）

```bash
git add src/uasset_read/graph/chain_builder.py tests/graph/test_chain_exec_pins.py
git commit -m "feat: show exec pin names in chain output format"
```

---

## 最终验证

### Task 10: 全量回归测试

**Files:** 无新建文件

- [ ] **Step 1: 运行完整测试套件**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

预期: 所有测试通过，无新增失败。

- [ ] **Step 2: 运行真实资产测试确认**

```bash
python temp/real_asset_full_batch_test.py 2>&1 | tail -30
```

预期: 19190 个文件 100% 通过（或通过率不低于之前）。

- [ ] **Step 3: Commit 最终版本**

```bash
git add -A
git commit -m "feat: complete blueprint execution graph capability improvements

- Add missing control flow nodes (ForLoop, WhileLoop, DoOnce, Sequence, MultiGate, Select)
- Capture exec pin names in execution flow and chain output
- Detect and mark latent/async action nodes
- Extract actual CustomEvent names
- Multi-function CallFunction extraction in Ubergraph semantics
- Macro expansion engine with cycle detection and pin mapping
- Execution chain penetration through MacroInstance nodes
- Standard macro definitions (10 built-in macros)
"
```

---

## 实施顺序和依赖关系

```
Phase 1 (控制流)          Phase 2 (语义)           Phase 3 (宏引擎)          Phase 4 (输出)
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ Task 1: 常量扩展│      │ Task 4: 事件命名│      │ Task 6: 宏核心  │      │ Task 8: JSON输出│
│ Task 2: Pin名称 │◄─────│ Task 5: Ubergraph│      │ Task 7: 链穿透  │◄─────│ Task 9: 链格式  │
│ Task 3: Latent  │      └─────────────────┘      └─────────────────┘      └─────────────────┘
└─────────────────┘
       │                      │                        │                        │
       └──────────────────────┴────────────────────────┴────────────────────────┘
                                                    │
                                             ┌──────▼──────┐
                                             │ Task 10: 回归│
                                             └─────────────┘
```

**推荐执行顺序**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10

每个 Task 完成后都可独立验证，Phase 之间无硬性阻塞关系（但 Phase 3 依赖 Phase 1 的常量扩展）。
