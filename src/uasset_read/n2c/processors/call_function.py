"""CallFunction 节点处理器 — 提取函数引用和纯函数检测。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class CallFunctionProcessor(N2CNodeProcessor):
    """处理 K2Node_CallFunction 类型节点。

    提取函数引用（member_name, member_parent, b_self_context），
    并检测是否为纯函数（无 exec 引脚）。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.CallFunction]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        # Handle node_data=None
        if node.node_data is not None:
            self._extract_function_reference(node, definition)

        # Pure detection: no exec pin means pure function
        has_exec_pin = any(
            pin.pin_type and pin.pin_type.pin_category == "exec"
            for pin in node.pins
        )
        if not has_exec_pin:
            definition.extra_data["pure"] = True

    def _extract_function_reference(
        self, node: UEdGraphNode, definition: N2CNodeDefinition
    ) -> None:
        """从 node_data 提取 FMemberReference 字段。"""
        ref = None
        data = node.node_data

        if isinstance(data, dict):
            ref = data.get("function_reference")
        else:
            # Assume dataclass / object with attribute
            ref = getattr(data, "function_reference", None)

        if ref is None:
            return

        if isinstance(ref, dict):
            if "member_name" in ref:
                definition.extra_data["member_name"] = ref["member_name"]
            if "member_parent" in ref:
                definition.extra_data["member_parent"] = ref["member_parent"]
            if "b_self_context" in ref:
                definition.extra_data["b_self_context"] = ref["b_self_context"]
        else:
            # Object / dataclass
            if hasattr(ref, "member_name"):
                definition.extra_data["member_name"] = ref.member_name
            if hasattr(ref, "member_parent"):
                definition.extra_data["member_parent"] = ref.member_parent
            if hasattr(ref, "b_self_context"):
                definition.extra_data["b_self_context"] = ref.b_self_context
