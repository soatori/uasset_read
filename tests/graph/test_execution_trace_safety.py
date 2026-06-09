"""Graph 执行流追踪安全防护测试"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from uasset_read.graph.flow_builder import _trace_execution_from_event


@dataclass
class FakePinType:
    pin_category: str = ""


@dataclass
class FakePin:
    pin_id: str = ""
    pin_name: str = ""
    direction: int = 0  # 0=input, 1=output
    pin_type: Optional[FakePinType] = None
    linked_to_raw: List[str] = field(default_factory=list)


@dataclass
class FakeNodeData:
    b_defaults_to_pure: bool = False


@dataclass
class FakeNode:
    node_guid: Optional[str] = None
    class_name: str = "K2Node_CallFunction"
    pins: List[FakePin] = field(default_factory=list)
    node_data: Optional[FakeNodeData] = None


# _pin_ref_guid 会把 ref 转成大写 hex，所以 pin_lookup 的 key 和 linked_to_raw 的值
# 都需要用大写格式才能匹配。这里用简短的 hex id 模拟。

def test_no_guid_self_loop_terminates():
    """单个无 GUID 节点（无出边）应立即终止。"""
    node = FakeNode(node_guid=None, class_name="K2Node_CallFunction")
    flow = _trace_execution_from_event(
        node, pin_lookup={}, node_lookup={}, node_name_lookup={},
        asset_context={},
    )
    assert len(flow) >= 1
    assert flow[0].get("warning") == "missing node_guid"


def test_no_guid_repeated_node_stops():
    """同一个无 GUID 节点自环应 cycle_detected 终止。"""
    # _pin_ref_guid("AA") → "AA"，pin_lookup["AA"] → (None, "exec")
    # node_lookup[None] → node，_find_next_exec_node 返回 node 自身
    pin_in = FakePin(
        pin_id="AA", pin_name="exec",
        direction=0, pin_type=FakePinType("exec"),
    )
    pin_out = FakePin(
        pin_id="BB", pin_name="then",
        direction=1, pin_type=FakePinType("exec"),
        linked_to_raw=["AA"],  # output → input（自环）
    )
    node = FakeNode(node_guid=None, class_name="K2Node_CallFunction", pins=[pin_out, pin_in])

    pin_lookup = {"AA": (None, "exec")}
    node_lookup = {None: node}

    flow = _trace_execution_from_event(
        node, pin_lookup, node_lookup, node_name_lookup={},
        asset_context={},
    )
    assert any(f.get("cycle_detected") for f in flow), f"Expected cycle_detected in flow: {flow}"


def test_guid_node_cycle_detected():
    """有 GUID 节点自环应 cycle_detected 终止。"""
    pin_in = FakePin(
        pin_id="AA", pin_name="exec",
        direction=0, pin_type=FakePinType("exec"),
    )
    pin_out = FakePin(
        pin_id="BB", pin_name="then",
        direction=1, pin_type=FakePinType("exec"),
        linked_to_raw=["AA"],  # 自环：output → input
    )
    node = FakeNode(
        node_guid="guid-self",
        class_name="K2Node_CallFunction",
        pins=[pin_out, pin_in],
    )
    pin_lookup = {"AA": ("guid-self", "exec")}
    node_lookup = {"guid-self": node}

    flow = _trace_execution_from_event(
        node, pin_lookup, node_lookup, node_name_lookup={"guid-self": "Self"},
        asset_context={},
    )
    assert any(f.get("cycle_detected") for f in flow), f"Expected cycle_detected in flow: {flow}"


def test_max_steps_exceeded():
    """超过最大步数应 stopped_at max_steps_exceeded。"""
    # 构造 502 个节点串联，每个 exec_out 的 linked_to_raw 指向下一个的 exec_in
    nodes = []
    for i in range(502):
        pin_in = FakePin(
            pin_id=f"IN{i:04d}", pin_name="exec",
            direction=0, pin_type=FakePinType("exec"),
        )
        pin_out = FakePin(
            pin_id=f"OUT{i:04d}", pin_name="then",
            direction=1, pin_type=FakePinType("exec"),
        )
        if i < 501:
            pin_out.linked_to_raw = [f"IN{i+1:04d}"]  # 指向下一个节点
        node = FakeNode(
            node_guid=f"guid-{i:04d}",
            class_name="K2Node_CallFunction",
            pins=[pin_out, pin_in],
        )
        nodes.append(node)

    pin_lookup = {}
    node_lookup = {}
    node_name_lookup = {}
    for i in range(501):
        pin_lookup[f"IN{i+1:04d}"] = (f"guid-{i+1:04d}", "exec")
        node_lookup[f"guid-{i:04d}"] = nodes[i]
        node_name_lookup[f"guid-{i:04d}"] = f"Node{i}"
    node_lookup["guid-501"] = nodes[501]

    flow = _trace_execution_from_event(
        nodes[0], pin_lookup, node_lookup, node_name_lookup,
        asset_context={},
    )
    assert any(f.get("stopped_at") == "max_steps_exceeded" for f in flow), \
        f"Expected max_steps_exceeded in flow"
