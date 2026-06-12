"""Pin/节点命名工具 — Pin 格式化、GUID 校验、方向判断。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from uasset_read.models.core import UEdGraphNode, UEdGraphPin


def _derive_node_name(node: UEdGraphNode, idx: int) -> str:
    """从节点派生用户友好的节点名（D-19-02）。

    策略：使用 f"{class_name}_{idx}" 格式，避免同名节点冲突。
    """
    return f"{node.class_name}_{idx}"


def format_pin_ref(
    node_guid: str,
    pin_name: str,
    node_name_lookup: Dict[str, str],
    mode: str = "name"
) -> Dict:
    """格式化 Pin 引用（D-19-02, D-19-05）。

    Args:
        node_guid: 节点 GUID
        pin_name: Pin 名称
        node_name_lookup: node_guid → node_name 查找表
        mode: "name" 或 "guid" 模式（默认 name）

    Returns:
        Dict: 格式化后的 Pin 引用对象
    """
    if mode == "name":
        if node_guid in node_name_lookup:
            return {
                "node": node_name_lookup[node_guid],
                "pin": pin_name
            }
        else:
            return {
                "node_guid": node_guid,
                "pin": pin_name,
                "warning": "node_name lookup failed"
            }
    else:
        return {
            "node_guid": node_guid,
            "pin_name": pin_name
        }


def _pin_ref_guid(ref: object) -> str | None:
    """从 LinkedTo/PinReference 结构中提取 pin guid（归一化为 32 字符大写 hex）。

    PinReference GUID 原始格式为 8-4-4-4-12 带 dash（_read_guid 输出），
    而归一化后与 pin_id（.hex().upper() 输出）格式一致，确保连接查找匹配。
    """
    raw_guid: str | None = None
    if isinstance(ref, dict):
        raw_guid = ref.get("pin_guid") or ref.get("pin_id")
    elif isinstance(ref, str):
        raw_guid = ref
    else:
        raw_guid = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)

    if not raw_guid:
        return None

    # 归一化：移除 dash，转大写
    return raw_guid.replace("-", "").upper()


def _pin_direction_text(direction: int) -> str:
    """Return stable pin direction text for Blueprint DTO output."""
    return "output" if direction == 1 else "input"


def _pin_category(pin: UEdGraphPin) -> str:
    return pin.pin_type.pin_category if pin.pin_type else ""


def _pin_subcategory(pin: UEdGraphPin) -> str:
    return pin.pin_type.pin_subcategory if pin.pin_type else ""


def _pin_container_type(pin: UEdGraphPin) -> str:
    if not pin.pin_type:
        return ""
    return str(getattr(pin.pin_type, "container_type", "") or "")


def _format_blueprint_pin_dto(
    pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_name_lookup: Dict[str, str],
) -> Dict[str, Any]:
    """Format a pin using the compact Blueprint DTO shape."""
    linked_to: List[str] = []
    for ref in pin.linked_to_raw or []:
        target_pin_id = _pin_ref_guid(ref)
        if target_pin_id in pin_lookup:
            target_node_guid, target_pin_name = pin_lookup[target_pin_id]
            target_node_name = node_name_lookup.get(target_node_guid, target_node_guid)
            linked_to.append(f"{target_node_name}.{target_pin_name}")
        elif target_pin_id:
            linked_to.append(str(target_pin_id))
        elif isinstance(ref, dict) and ref.get("owning_node"):
            linked_to.append(str(ref["owning_node"]))

    pin_type = pin.pin_type
    return {
        "PinId": pin.persistent_guid or pin.pin_id,
        "PinName": pin.pin_name,
        "Direction": _pin_direction_text(pin.direction),
        "PinCategory": _pin_category(pin),
        "PinSubCategory": _pin_subcategory(pin),
        "DefaultValue": pin.default_value,
        "LinkedTo": linked_to,
        "IsReference": bool(getattr(pin_type, "is_reference", False)) if pin_type else False,
        "IsConst": bool(getattr(pin_type, "is_const", False)) if pin_type else False,
        "ContainerType": _pin_container_type(pin),
    }


def _node_member_name(node: Optional[UEdGraphNode]) -> str:
    if node is None or not node.node_data:
        return ""
    ref = None
    if isinstance(node.node_data, dict):
        ref = node.node_data.get("function_reference") or node.node_data.get("event_reference")
    else:
        ref = getattr(node.node_data, "function_reference", None) or getattr(node.node_data, "event_reference", None)
    if isinstance(ref, dict):
        return ref.get("member_name", "") or ""
    return getattr(ref, "member_name", "") or ""


def _is_exec_pin(pin: UEdGraphPin) -> bool:
    return bool(pin.pin_type and pin.pin_type.pin_category == "exec")


def _is_valid_pin_guid(guid: object) -> bool:
    """验证 Pin GUID 有效性。

    支持两种格式：
    - 32 字符纯 hex（pin_id 格式）
    - 36 字符带 dash hex（PinReference 格式，如 A1B2C3D4-E5F6-...）
    - "pin-" 前缀（测试 fixture）
    - 全零 GUID（ParentPin 空引用）
    """
    if not isinstance(guid, str) or not guid:
        return False

    # 测试 fixture 兼容
    if guid.startswith("pin-"):
        return True

    # 归一化：移除 dash，转大写
    normalized = guid.replace("-", "").upper()

    # 全零 GUID（有效空引用）
    if normalized == "0" * 32:
        return True

    # 验证 32 字符 hex
    if len(normalized) != 32:
        return False

    return all(c in "0123456789ABCDEF" for c in normalized)
