"""Widget 节点处理器 — UMG 控件相关节点。

覆盖：
- K2Node_CreateWidget（创建 UMG 控件）
- K2Node_FunctionResult（函数返回值）
- K2Node_MacroInstance（宏实例）
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class WidgetProcessor(N2CNodeProcessor):
    """处理 UMG 控件和宏相关 K2Node 节点。

    提取控件类名、宏名称等信息。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [
            N2CNodeType.CreateWidget,
            N2CNodeType.FunctionResult,
            N2CNodeType.MacroInstance,
        ]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if not isinstance(data, dict):
            return

        # K2Node_CreateWidget: 提取控件类名
        widget_class = data.get("widget_class")
        if widget_class:
            definition.extra_data["widget_class"] = widget_class

        # K2Node_MacroInstance: 提取宏名称
        macro_name = data.get("macro_name")
        if macro_name:
            definition.extra_data["macro_name"] = macro_name

        # K2Node_FunctionResult: 提取函数引用
        func_ref = data.get("function_reference")
        if func_ref and isinstance(func_ref, dict):
            member_name = func_ref.get("member_name")
            if member_name:
                definition.extra_data["member_name"] = member_name
