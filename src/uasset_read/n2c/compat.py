"""N2C -> OUT-01 向后兼容适配层。

提供 N2CNodeDefinition 到现有 OUT-01 dict 格式的转换函数，
确保 flow_builder.py 重构后 JSON 输出格式完全不变。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from uasset_read.n2c.definitions import N2CNodeDefinition


def definition_to_node_dict(
    definition: N2CNodeDefinition,
    node_name: str,
    node_guid: str,
    original_class_name: str,
    pins: list,
) -> dict:
    """将 N2CNodeDefinition 转换为现有 OUT-01 格式 dict。

    映射 extra_data 字段到遗留键名：
    - member_name → function_reference / function_entry_reference / event_reference
    - branch_type → branch_type
    - pure → pure
    - etc.

    Args:
        definition: 处理器填充后的 N2CNodeDefinition
        node_name: 派生的节点名（来自 _derive_node_name）
        node_guid: 节点 GUID
        original_class_name: 原始 K2Node 类名
        pins: 引脚 dict 列表（已序列化）

    Returns:
        OUT-01 兼容的节点 dict
    """
    extra = definition.extra_data

    # 基础字段
    result: Dict[str, Any] = {
        "node_name": node_name,
        "node_type": original_class_name,
        "node_guid": node_guid,
        "position": {"x": definition.position[0], "y": definition.position[1]},
        "node_comment": definition.comment if definition.comment else None,
        "pins": pins,
    }

    # --- function_reference（CallFunction / FunctionEntry）---
    if extra.get("member_name") is not None:
        member_parent = extra.get("member_parent")
        self_context = extra.get("b_self_context")

        if original_class_name == "K2Node_FunctionEntry":
            result["function_entry_reference"] = _compact_dict({
                "member_name": extra["member_name"],
                "member_parent": member_parent,
                "self_context": self_context,
            })
        else:
            result["function_reference"] = _compact_dict({
                "member_name": extra["member_name"],
                "member_parent": member_parent,
                "self_context": self_context,
            })

    # --- event_reference（Event / CustomEvent）---
    elif extra.get("event_name") is not None:
        event_parent = extra.get("event_parent")
        result["event_reference"] = _compact_dict({
            "member_name": extra["event_name"],
            "member_parent": event_parent,
            "member_guid": extra.get("member_guid"),
        })

    # --- input_action_path（EnhancedInputAction）---
    elif extra.get("input_action_path") is not None:
        result["input_action_path"] = extra["input_action_path"]

    # --- branch_type（ControlFlow 节点）---
    if extra.get("branch_type") is not None:
        result["branch_type"] = extra["branch_type"]

    # --- pure ---
    if extra.get("pure") is not None:
        result["pure"] = extra["pure"]

    # --- direction（VariableGet/Set）---
    if extra.get("direction") is not None:
        result["variable_direction"] = extra["direction"]
        if extra.get("variable_name"):
            result["variable_name"] = extra["variable_name"]

    # --- target_type（Cast）---
    if extra.get("target_type") is not None:
        result["target_type"] = extra["target_type"]

    # 移除 None 值字段（保持输出精简）
    result = {k: v for k, v in result.items() if v is not None}

    return result


def definition_to_trace_node_info(
    definition: N2CNodeDefinition,
    current_guid: Optional[str],
    original_class_name: str,
) -> dict:
    """将 N2CNodeDefinition 转换为 _trace_execution_from_event 使用的 node_info dict。

    用于执行流追踪的输出格式，与原有格式完全一致。

    Args:
        definition: 处理器填充后的 N2CNodeDefinition
        current_guid: 当前节点 GUID（可能为 None）
        original_class_name: 原始 K2Node 类名

    Returns:
        node_info dict（用于追加到 flow 列表）
    """
    extra = definition.extra_data

    if current_guid is not None:
        node_info: Dict[str, Any] = {
            "node_guid": current_guid,
            "node_type": original_class_name,
        }
    else:
        node_info = {
            "node_type": original_class_name,
        }

    # function_name（CallFunction / FunctionEntry）
    if extra.get("member_name") is not None:
        node_info["function_name"] = extra["member_name"]

    # event_name（Event / CustomEvent）
    if extra.get("event_name") is not None:
        node_info["event_name"] = extra["event_name"]

    # branch_type + stopped_at（ControlFlow 节点）
    if extra.get("branch_type") is not None:
        node_info["branch_type"] = extra["branch_type"]
    if extra.get("stops_execution"):
        node_info["stopped_at"] = "control_flow_node"

    # pure（CallFunction）
    if extra.get("pure") is not None:
        node_info["pure"] = True

    return node_info


def _compact_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """移除 dict 中的 None 值。"""
    return {k: v for k, v in d.items() if v is not None}
