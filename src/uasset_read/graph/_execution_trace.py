"""执行流追踪 — 从事件/宏开始沿 exec pin 追踪执行链路。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from uasset_read.constants import (
    BRANCH_TYPE_MAP,
    CONTROL_FLOW_NODES,
    START_EVENT_TYPES,
)
from uasset_read.graph.macro_expander import (
    MacroExpander, STANDARD_MACROS, STANDARD_MACRO_CPP_MAPPING,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin

from ._edge_traversal import (
    _build_normalized_edge_indexes,
    _find_next_exec_node,
    _pin_ref_guid,
)
from ._node_format import _derive_node_name, _get_start_event_name

logger = logging.getLogger(__name__)

# Latent/Async 动作节点类型集合 — 在执行流中标记为 latent=True
LATENT_NODE_TYPES = frozenset({
    "K2Node_AsyncAction",
    "K2Node_LatentGameCommand",
    "K2Node_BaseAsyncTask",
    "K2Node_Timeline",
})


def _try_expand_macro(node: UEdGraphNode, asset_context: Dict[str, Any]) -> Dict[str, Any]:
    """尝试展开宏实例。

    Args:
        node: MacroInstance 节点
        asset_context: 资产上下文，包含 graphs 等信息

    Returns:
        展开结果字典，包含 macro_name, pin_mapping, unresolved 等
    """
    node_data = node.node_data or {}
    if not isinstance(node_data, dict):
        return {"unresolved": True, "reason": "node_data is not a dict"}

    macro_ref = node_data.get("macro_graph_reference", {})

    if not macro_ref:
        return {"unresolved": True, "reason": "no macro_graph_reference"}

    graph_name = macro_ref.get("graph_name", "")

    # 检查是否为标准宏
    is_standard = graph_name in STANDARD_MACROS

    try:
        expander = MacroExpander(asset_context)
        expansion = expander.expand_macro_instance({"macro_graph_reference": macro_ref})
        return {
            "macro_name": expansion.context.macro_name,
            "macro_guid": expansion.context.macro_guid,
            "pin_mapping": expansion.pin_mapping,
            "unresolved": expansion.unresolved,
            "is_standard": is_standard or expansion.context.macro_name in STANDARD_MACROS,
            "internal_flows": expansion.internal_flows,
        }
    except Exception as e:
        return {
            "unresolved": True,
            "reason": str(e),
            "macro_name": graph_name or "Unknown",
        }


def _trace_execution_from_event(
    start_node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {},
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    asset_context: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """追踪单条执行流（D-08-07~11, D-19-13~14）。

    Args:
        start_node: K2Node_Event 起点（或其他START_EVENT_TYPES起点）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表
        node_name_lookup: node_guid → node_name 查找表

    Returns:
        List[Dict]: 节点信息序列
    """
    visited: Set[str] = set()
    flow: List[Dict] = []
    current_node = start_node
    _MAX_EXEC_STEPS = 500
    _steps = 0
    # 为无 GUID 节点使用 id 做 visited，防止无限循环
    _no_guid_visited: Set[int] = set()

    while current_node:
        _steps += 1
        if _steps > _MAX_EXEC_STEPS:
            flow.append({"stopped_at": "max_steps_exceeded", "steps": _steps})
            break

        # LOW-07: 处理 node_guid 为 None 的情况
        current_guid = current_node.node_guid
        if current_guid is None:
            node_id = id(current_node)
            if node_id in _no_guid_visited:
                flow.append({
                    "node_type": current_node.class_name,
                    "cycle_detected": True,
                    "warning": "missing node_guid"
                })
                break
            _no_guid_visited.add(node_id)
            # node_guid 缺失时仍记录节点但跳过有 GUID 的循环检测
            flow.append({
                "node_type": current_node.class_name,
                "warning": "missing node_guid"
            })
            current_node, _ = _find_next_exec_node(
                current_node, pin_lookup, node_lookup, edges_by_from_pin
            )
            continue

        if current_guid in visited:
            flow.append({
                "node_guid": current_guid,
                "node_type": current_node.class_name,
                "cycle_detected": True
            })
            break

        visited.add(current_guid)

        node_info = {
            "node_guid": current_guid,
            "node_type": current_node.class_name,
        }

        # Latent/Async 动作检测
        if current_node.class_name in LATENT_NODE_TYPES:
            node_info["latent"] = True

        # --- CallFunction 的 parameters 提取（数据流追踪）---
        if current_node.class_name == "K2Node_CallFunction":
            from uasset_read.formatters.json_formatter import _extract_call_function_parameters
            node_info["parameters"] = _extract_call_function_parameters(
                current_node, pin_lookup, node_lookup, node_name_lookup
            )

        # mark pure functions with "pure": true in flow
        has_exec_pin = any(pin.pin_type and pin.pin_type.pin_category == "exec" for pin in current_node.pins)
        if not has_exec_pin:
            node_info["pure"] = True

            # Pure 函数 data_providers 标注（正向追踪）
            data_providers: List[Dict] = []
            for pin in current_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category != "exec":
                    # 找到 output pin 的连接目标
                    if edges_by_from_pin and pin.pin_id in edges_by_from_pin:
                        for edge in edges_by_from_pin[pin.pin_id]:
                            data_providers.append({
                                "output_pin": pin.pin_name,
                                "target_node": node_name_lookup.get(edge["to_node_guid"], edge["to_node_guid"]),
                                "target_pin": edge["to_pin"],
                            })
                    else:
                        for linked_ref in (pin.linked_to_raw or []):
                            target_pin_guid = _pin_ref_guid(linked_ref)
                            if target_pin_guid in pin_lookup:
                                target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                                target_node_name = node_name_lookup.get(target_node_guid, target_node_guid)
                                data_providers.append({
                                    "output_pin": pin.pin_name,
                                    "target_node": target_node_name,
                                    "target_pin": target_pin_name
                                })

            if data_providers:
                node_info["data_providers"] = data_providers

        elif current_node.node_data and hasattr(current_node.node_data, 'b_defaults_to_pure') and current_node.node_data.b_defaults_to_pure:
            node_info["pure"] = True

        # 控制流节点处理
        if current_node.class_name in CONTROL_FLOW_NODES:
            if current_node.class_name == "K2Node_MacroInstance":
                # 宏实例：尝试展开并穿透，不终止执行链
                ctx = asset_context or {}
                expansion = _try_expand_macro(current_node, ctx)
                node_info["macro_expansion"] = expansion
                macro_name = expansion.get("macro_name", "")
                if macro_name in STANDARD_MACRO_CPP_MAPPING:
                    node_info["cpp_macro_mapping"] = STANDARD_MACRO_CPP_MAPPING[macro_name]
                if not expansion.get("is_standard") and not expansion.get("unresolved"):
                    internal_flows = expansion.get("internal_flows", [])
                    if internal_flows:
                        node_info["macro_internal_flows"] = internal_flows
            else:
                # 其他控制流节点：设置 branch_type 并终止
                if "branch_type" not in node_info:
                    branch_type = BRANCH_TYPE_MAP.get(current_node.class_name, "unknown")
                    node_info["branch_type"] = branch_type
                if "stopped_at" not in node_info:
                    node_info["stopped_at"] = "control_flow_node"
                flow.append(node_info)
                break

        flow.append(node_info)
        current_node, used_pin_name = _find_next_exec_node(
            current_node, pin_lookup, node_lookup, edges_by_from_pin
        )
        if used_pin_name is not None:
            node_info["used_exec_pin_name"] = used_pin_name

    return flow


def _trace_execution_from_pin(
    start_node: UEdGraphNode,
    start_pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode],
    node_name_lookup: Dict[str, str] = {},
    edges_by_from_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    source_edges_by_to_pin: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    asset_context: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """从特定Pin开始追踪执行流（D-19-12）。

    用于EnhancedInputAction多触发时机追踪。
    增加 node_name_lookup 参数传递。
    """
    if edges_by_from_pin and start_pin.pin_id in edges_by_from_pin:
        edge = edges_by_from_pin[start_pin.pin_id][0]
        next_node = node_lookup.get(edge["to_node_guid"])
        if next_node:
            return _trace_execution_from_event(
                next_node, pin_lookup, node_lookup, node_name_lookup,
                edges_by_from_pin, source_edges_by_to_pin, asset_context,
            )

    for linked_pin_id in (start_pin.linked_to_raw or []):
        target_pin_guid = _pin_ref_guid(linked_pin_id)
        if target_pin_guid in pin_lookup:
            target_node_guid, _ = pin_lookup[target_pin_guid]
            next_node = node_lookup.get(target_node_guid)
            if next_node:
                return _trace_execution_from_event(
                    next_node, pin_lookup, node_lookup, node_name_lookup,
                    edges_by_from_pin, source_edges_by_to_pin, asset_context,
                )

    return []
