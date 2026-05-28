"""K2Node_EnhancedInputAction 处理器 — 提取输入动作资源信息。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class EnhancedInputActionProcessor(N2CNodeProcessor):
    """处理 K2Node_EnhancedInputAction 类型节点。

    提取: InputAction 资源路径, TriggeredSeconds, ElapsedSeconds, AdvancedPinDisplay。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.EnhancedInputAction]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if not isinstance(data, dict):
            return

        # 提取 InputAction 资源路径
        input_action = data.get("InputAction") or data.get("input_action") or data.get("input_action_path")
        if input_action is not None:
            if isinstance(input_action, str):
                if input_action:
                    definition.extra_data["input_action"] = input_action
                    short_name = input_action.split("/")[-1].split(".")[0]
                    if short_name:
                        definition.extra_data["input_action_short_name"] = short_name
            elif isinstance(input_action, dict):
                path = input_action.get("path", input_action.get("object_path", ""))
                if path:
                    definition.extra_data["input_action"] = path
                    short_name = path.split("/")[-1].split(".")[0]
                    if short_name:
                        definition.extra_data["input_action_short_name"] = short_name

        # 提取定时器字段
        for key in ("TriggeredSeconds", "ElapsedSeconds"):
            if key in data:
                definition.extra_data[key.lower()] = data[key]

        # 提取高级引脚显示
        if "AdvancedPinDisplay" in data:
            adv = data["AdvancedPinDisplay"]
            definition.extra_data["advanced_pin_display"] = (
                "hidden" if adv in (1, True, "True") else "visible"
            )
