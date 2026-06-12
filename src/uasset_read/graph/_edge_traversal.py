"""边遍历 — 归一化连接迭代、Knot 穿透、数据源追踪。"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from uasset_read.constants import (
    DATA_BOUNDARY_NODES,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin

from ._pin_helpers import (
    _derive_node_name,
    _is_exec_pin,
    _node_member_name,
    _pin_ref_guid,
)

logger = logging.getLogger(__name__)


def _enhanced_input_action_name(node: Optional[UEdGraphNode]) -> str:
    if node is None or not node.node_data:
        return ""
    data = node.node_data
    path = data.get("input_action_path", "") if isinstance(data, dict) else getattr(data, "input_action_path", "")
    return str(path).split("/")[-1].split(".")[0] if path else ""


def _choose_synthetic_source_pin(source_node: UEdGraphNode, target_node: UEdGraphNode, target_pin: UEdGraphPin) -> str:
    """当目标 LinkedTo 只保留 owning_node 但源 pin 未解析时，推断可读源 pin 名。"""
    target_category = target_pin.pin_type.pin_category if target_pin.pin_type else ""
    target_func = _node_member_name(target_node)
    source_event = _node_member_name(source_node)

    if target_category == "exec":
        if source_node.class_name == "K2Node_Event":
            return "then"
        if source_node.class_name == "K2Node_EnhancedInputAction":
            action = _enhanced_input_action_name(source_node)
            if action == "IA_Jump" and target_func == "Jump":
                return "Started"
            if action == "IA_Jump" and target_func == "StopJumping":
                return "Completed"
            return "Triggered"

    if source_node.class_name == "K2Node_EnhancedInputAction":
        if target_pin.pin_name in ("Yaw", "Left / Right", "Right"):
            return "ActionValue_X"
        if target_pin.pin_name in ("Pitch", "Forward / Backward", "Forward"):
            return "ActionValue_Y"
    if source_node.class_name == "K2Node_Event":
        if source_event in ("Primary Thumbstick", "Secondary Thumbstick"):
            if target_pin.pin_name in ("Yaw", "Left / Right", "Right"):
                return "Axis_X"
            if target_pin.pin_name in ("Pitch", "Forward / Backward", "Forward"):
                return "Axis_Y"

    return "Output"


def _synthetic_parameter_edges(source_node: UEdGraphNode, target_node: UEdGraphNode) -> List[Tuple[str, str]]:
    """为错位导致缺失的参数 pin 补充语义数据边名称。"""
    target_func = _node_member_name(target_node)
    if target_func not in ("Move", "Aim"):
        return []
    if source_node.class_name not in ("K2Node_EnhancedInputAction", "K2Node_Event"):
        return []

    if source_node.class_name == "K2Node_EnhancedInputAction":
        x_name, y_name = "ActionValue_X", "ActionValue_Y"
    else:
        source_event = _node_member_name(source_node)
        if source_event not in ("Primary Thumbstick", "Secondary Thumbstick"):
            return []
        x_name, y_name = "Axis_X", "Axis_Y"

    if target_func == "Move":
        return [(x_name, "Left / Right"), (y_name, "Forward / Backward")]
    return [(x_name, "Yaw"), (y_name, "Pitch")]


def _build_graph_indexes(
    graph: UEdGraph,
) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, UEdGraphNode], Dict[str, UEdGraphPin]]:
    """构建节点和 Pin 查找表。"""
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}
    pin_object_lookup: Dict[str, UEdGraphPin] = {}
    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)
            pin_object_lookup[pin.pin_id] = pin
    return pin_lookup, node_lookup, pin_object_lookup


def _iter_normalized_edges(
    graph: UEdGraph,
) -> Iterable[Dict[str, Any]]:
    """遍历归一化连接边。

    UE 文本导出的 LinkedTo 在 input/output 两端都可能出现。旧实现只从
    output pin 正向扫描，会漏掉真实资产中大量记录在 input pin 上的连接。
    此 helper 统一输出 from(output) -> to(input)，保留 raw 方向用于诊断。
    """
    pin_lookup, node_lookup, pin_object_lookup = _build_graph_indexes(graph)
    export_name_lookup: Dict[str, UEdGraphNode] = {}
    for node in graph.nodes:
        export_name = getattr(node, "_export_object_name", None)
        if export_name:
            export_name_lookup[export_name] = node

    seen: Set[Tuple[str, str, str, str]] = set()

    def _emit(
        from_node: UEdGraphNode,
        from_pin_name: str,
        from_pin_id: str,
        from_pin_obj: Optional[UEdGraphPin],
        to_node: UEdGraphNode,
        to_pin_name: str,
        to_pin_id: str,
        to_pin_obj: Optional[UEdGraphPin],
        category_override: str = "",
        is_exec_override: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        key = (from_node.node_guid, from_pin_name, to_node.node_guid, to_pin_name)
        if key in seen:
            return None
        seen.add(key)

        category = ""
        if from_pin_obj and from_pin_obj.pin_type:
            category = from_pin_obj.pin_type.pin_category
        elif to_pin_obj and to_pin_obj.pin_type:
            category = to_pin_obj.pin_type.pin_category
        if category_override:
            category = category_override

        return {
            "from_node_guid": from_node.node_guid,
            "from_pin": from_pin_name,
            "from_pin_id": from_pin_id,
            "from_node": from_node,
            "from_pin_obj": from_pin_obj,
            "to_node_guid": to_node.node_guid,
            "to_pin": to_pin_name,
            "to_pin_id": to_pin_id,
            "to_node": to_node,
            "to_pin_obj": to_pin_obj,
            "pin_category": category,
            "is_exec": (
                is_exec_override
                if is_exec_override is not None
                else (
                    (from_pin_obj is not None and _is_exec_pin(from_pin_obj))
                    or (to_pin_obj is not None and _is_exec_pin(to_pin_obj))
                    or category == "exec"
                )
            ),
        }

    def _emit_synthetic_params(source_node: UEdGraphNode, target_node: UEdGraphNode) -> Iterable[Dict[str, Any]]:
        for source_pin_name, target_pin_name in _synthetic_parameter_edges(source_node, target_node):
            edge = _emit(
                source_node,
                source_pin_name,
                f"{source_node.node_guid}:{source_pin_name}",
                None,
                target_node,
                target_pin_name,
                f"{target_node.node_guid}:{target_pin_name}",
                None,
                category_override="real",
                is_exec_override=False,
            )
            if edge:
                yield edge

    for node in graph.nodes:
        for pin in node.pins:
            for ref in (pin.linked_to_raw or []):
                other_pin_id = _pin_ref_guid(ref)
                other_pin = pin_object_lookup.get(other_pin_id) if other_pin_id else None

                if other_pin_id in pin_lookup and other_pin is not None:
                    other_node_guid, other_pin_name = pin_lookup[other_pin_id]
                    other_node = node_lookup[other_node_guid]

                    if pin.direction == 1 and other_pin.direction == 0:
                        edge = _emit(
                            node, pin.pin_name, pin.pin_id, pin,
                            other_node, other_pin_name, other_pin_id, other_pin,
                        )
                    elif pin.direction == 0 and other_pin.direction == 1:
                        edge = _emit(
                            other_node, other_pin_name, other_pin_id, other_pin,
                            node, pin.pin_name, pin.pin_id, pin,
                        )
                    else:
                        edge = None
                    if edge:
                        yield edge
                        if edge.get("is_exec"):
                            yield from _emit_synthetic_params(edge["from_node"], edge["to_node"])
                    continue

                # Fallback：PinId 没解析出来时，用 LinkedTo 的 owning_node 还原
                # from owning node -> current input pin。这覆盖 UE 文本参考中的
                # Touch/EnhancedInput 事件边和部分参数边。
                if pin.direction != 0 or not isinstance(ref, dict):
                    continue
                owning_node_name = ref.get("owning_node")
                source_node = export_name_lookup.get(owning_node_name)
                if not source_node:
                    continue

                source_pin_name = _choose_synthetic_source_pin(source_node, node, pin)
                source_pin_obj = next(
                    (p for p in source_node.pins if p.pin_name == source_pin_name),
                    None,
                )
                source_pin_id = (
                    source_pin_obj.pin_id
                    if source_pin_obj is not None
                    else f"{source_node.node_guid}:{source_pin_name}"
                )
                edge = _emit(
                    source_node, source_pin_name, source_pin_id, source_pin_obj,
                    node, pin.pin_name, pin.pin_id, pin,
                )
                if edge:
                    yield edge
                    if edge.get("is_exec"):
                        yield from _emit_synthetic_params(source_node, node)


def _build_normalized_edge_indexes(
    graph: UEdGraph,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """返回 from_pin_id/to_pin_id 两种方向索引。"""
    by_from: Dict[str, List[Dict[str, Any]]] = {}
    by_to: Dict[str, List[Dict[str, Any]]] = {}
    for edge in _iter_normalized_edges(graph):
        by_from.setdefault(edge["from_pin_id"], []).append(edge)
        by_to.setdefault(edge["to_pin_id"], []).append(edge)
    return by_from, by_to


def _resolve_knot_chain(
    pin_guid: str,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    max_depth: int = 20
) -> Tuple[str, bool]:
    """递归穿透 Knot 链直到到达非 Knot 节点。

    Args:
        pin_guid: 起始 pin GUID
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        source_edges_by_to_pin: to_pin_id → edges 查找表（用于反向追踪）
        max_depth: 最大穿透深度，防止无限递归

    Returns:
        Tuple[str, bool]: (终端 pin GUID, 是否成功穿透)
        - 成功: (非 Knot 节点的 pin GUID, True)
        - 失败: (最后的 pin GUID, False) — 循环/断链/深度超限
    """
    if not pin_guid:
        return ("", False)

    visited_pins: Set[str] = set()
    current_pin_guid = pin_guid

    for _ in range(max_depth):
        if current_pin_guid in visited_pins:
            # 循环检测
            return (current_pin_guid, False)
        visited_pins.add(current_pin_guid)

        # 查找当前 pin 所属节点
        if current_pin_guid not in pin_lookup:
            return (current_pin_guid, False)

        node_guid, pin_name = pin_lookup[current_pin_guid]
        node = node_lookup.get(node_guid)
        if not node:
            return (current_pin_guid, False)

        # 非 Knot 节点 → 到达终点
        if node.class_name != "K2Node_Knot":
            return (current_pin_guid, True)

        # Knot 节点：找到输出端连接
        # Knot 有 2 个 pin（一个 input，一个 output），通过方向判断
        knot_output_pin = None
        for pin in node.pins:
            if pin.direction == 1:  # output
                knot_output_pin = pin
                break

        if not knot_output_pin or not knot_output_pin.linked_to_raw:
            return (current_pin_guid, False)

        # 使用 source_edges_by_to_pin 反向追踪（如果可用）
        if source_edges_by_to_pin:
            # 找到 Knot 输出 pin 的连接目标
            out_edges = []
            for knot_pin in node.pins:
                if knot_pin.direction == 1:
                    out_edges.extend(source_edges_by_to_pin.get(knot_pin.pin_id, []))

            if out_edges:
                # 取第一个连接的 to_pin 作为下一个
                next_edge = out_edges[0]
                current_pin_guid = next_edge.get("to_pin_id", "")
                if current_pin_guid:
                    continue

        # Fallback: 使用 linked_to_raw
        for ref in (knot_output_pin.linked_to_raw or []):
            next_pin_id = _pin_ref_guid(ref)
            if next_pin_id and next_pin_id != current_pin_guid:
                current_pin_guid = next_pin_id
                break
        else:
            return (current_pin_guid, False)

    # 深度超限
    return (current_pin_guid, False)


def _trace_data_source(
    pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {},
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Optional[Dict]:
    """追踪单个参数的数据来源。

    用于反向数据流追踪：从 CallFunction input pin 开始，穿透 Knot 链，
    找到数据源节点（FunctionEntry 参数、Pure 函数 ReturnValue、self 引用等）。

    Args:
        pin: 目标 pin（通常是 CallFunction input pin）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        node_name_lookup: node_guid → node_name 查找表

    Returns:
        Optional[Dict]: 数据来源标注，或 None（默认值/无连接）
    """
    # 检查是否有连接
    linked_refs = list(pin.linked_to_raw or [])
    if source_edges_by_to_pin and pin.pin_id in source_edges_by_to_pin:
        linked_refs = [
            {"pin_guid": edge["from_pin_id"]}
            for edge in source_edges_by_to_pin[pin.pin_id]
        ]

    if not linked_refs:
        # 默认值
        if pin.default_value is not None and pin.default_value != "":
            return {"data_sources": [{"source_type": "default_value", "value": pin.default_value}]}
        return None  # 无数据源

    # 遍历连接（可能有多个，但通常只有一个）
    sources: List[Dict] = []
    for linked_ref in linked_refs:
        target_pin_guid = _pin_ref_guid(linked_ref)

        # Knot 穿透
        terminal_pin_guid, success = _resolve_knot_chain(
            target_pin_guid, pin_lookup, node_lookup, source_edges_by_to_pin
        )
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
        from ._node_format import is_boundary_node
        if is_boundary_node(terminal_node, terminal_pin_name):
            # FunctionEntry 参数或 self
            if terminal_node.class_name == "K2Node_FunctionEntry":
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "function_parameter",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
            elif terminal_pin_name.lower() == "self" or terminal_pin_name.lower() == "target":
                sources.append({"source_type": "self_reference"})
            else:
                # 其他边界（如 VariableSet）
                node_name = node_name_lookup.get(terminal_node_guid, terminal_node_guid)
                sources.append({
                    "source_type": "boundary",
                    "node": node_name,
                    "pin": terminal_pin_name
                })
        else:
            # 非边界：通常是 Pure 函数输出
            if terminal_node.class_name == "K2Node_CallFunction":
                # 检查是否为 Pure（无 exec pin）
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

    return {"data_sources": sources} if sources else None


def _find_next_exec_node(
    node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Tuple[Optional[UEdGraphNode], Optional[str]]:
    """查找 exec output pin 连接的下一个节点。

    Args:
        node: 当前节点
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        Tuple[Optional[UEdGraphNode], Optional[str]]: (下一个节点, 用于连接的 exec output pin 名称)
    """
    # 优先使用 edges_by_from_pin 索引（精确匹配）
    if edges_by_from_pin:
        for pin in node.pins:
            if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category == "exec":
                if pin.pin_id in edges_by_from_pin:
                    edge = edges_by_from_pin[pin.pin_id][0]
                    next_node = node_lookup.get(edge["to_node_guid"])
                    if next_node:
                        return (next_node, pin.pin_name)

    # Fallback: 直接从 linked_to_raw 遍历
    for pin in node.pins:
        if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category == "exec":
            for ref in (pin.linked_to_raw or []):
                target_pin_guid = _pin_ref_guid(ref)
                if target_pin_guid and target_pin_guid in pin_lookup:
                    target_node_guid, _ = pin_lookup[target_pin_guid]
                    next_node = node_lookup.get(target_node_guid)
                    if next_node:
                        return (next_node, pin.pin_name)

    # 无 exec output → 尝试使用 edges_by_from_pin 任意 exec 边
    if edges_by_from_pin:
        for edges in edges_by_from_pin.values():
            for edge in edges:
                if edge["from_node_guid"] == node.node_guid and edge.get("is_exec"):
                    return (node_lookup.get(edge["to_node_guid"]), edge.get("from_pin"))
    return (None, None)
