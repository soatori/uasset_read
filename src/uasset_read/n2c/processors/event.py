"""Event 节点处理器 — 提取事件引用。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class EventProcessor(N2CNodeProcessor):
    """处理 Event 和 CustomEvent 类型节点。

    提取事件引用（event_name, event_parent）。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.Event, N2CNodeType.CustomEvent]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        ref = None
        data = node.node_data

        if isinstance(data, dict):
            # Try event_reference first, then function_reference (some events use same field)
            ref = data.get("event_reference") or data.get("function_reference")
        else:
            ref = (
                getattr(data, "event_reference", None)
                or getattr(data, "function_reference", None)
            )

        if ref is None:
            return

        if isinstance(ref, dict):
            if "member_name" in ref:
                definition.extra_data["event_name"] = ref["member_name"]
            if "member_parent" in ref:
                definition.extra_data["event_parent"] = ref["member_parent"]
        else:
            if hasattr(ref, "member_name"):
                definition.extra_data["event_name"] = ref.member_name
            if hasattr(ref, "member_parent"):
                definition.extra_data["event_parent"] = ref.member_parent
