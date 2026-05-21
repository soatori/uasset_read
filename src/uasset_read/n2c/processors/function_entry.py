"""FunctionEntry 节点处理器 — 提取函数入口引用。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class FunctionEntryProcessor(N2CNodeProcessor):
    """处理 FunctionEntry 类型节点。

    提取函数引用（member_name, member_parent）。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.FunctionEntry]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        ref = None
        data = node.node_data

        if isinstance(data, dict):
            ref = data.get("function_reference")
        else:
            ref = getattr(data, "function_reference", None)

        if ref is None:
            return

        if isinstance(ref, dict):
            if "member_name" in ref:
                definition.extra_data["member_name"] = ref["member_name"]
            if "member_parent" in ref:
                definition.extra_data["member_parent"] = ref["member_parent"]
        else:
            if hasattr(ref, "member_name"):
                definition.extra_data["member_name"] = ref.member_name
            if hasattr(ref, "member_parent"):
                definition.extra_data["member_parent"] = ref.member_parent
