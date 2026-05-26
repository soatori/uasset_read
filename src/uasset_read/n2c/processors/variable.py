"""Variable 节点处理器 — 变量 Get/Set 节点。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class VariableProcessor(N2CNodeProcessor):
    """处理 VariableGet 和 VariableSet 类型节点。

    提取变量名和方向（get/set）。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.VariableGet, N2CNodeType.VariableSet]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        # Determine direction from node type
        node_type = definition.node_type
        if node_type == N2CNodeType.VariableSet:
            definition.extra_data["direction"] = "set"
        else:
            definition.extra_data["direction"] = "get"

        # Extract variable name from node_data or class_name
        var_name = None
        data = node.node_data

        if data is not None:
            if isinstance(data, dict):
                var_name = data.get("variable_name") or data.get("member_name")
            else:
                var_name = (
                    getattr(data, "variable_name", None)
                    or getattr(data, "member_name", None)
                )

        # Fallback to class_name if no variable name found
        if not var_name and node.class_name:
            var_name = node.class_name

        if var_name:
            definition.extra_data["variable_name"] = var_name
