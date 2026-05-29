"""Delegate 节点处理器 — 委托相关节点。

覆盖：
- K2Node_AddDelegate（添加多播委托绑定）
- K2Node_AssignDelegate（赋值委托绑定）
- K2Node_CallDelegate（调用委托）
- K2Node_Message（消息调用）
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class DelegateProcessor(N2CNodeProcessor):
    """处理委托相关 K2Node 节点。

    提取委托名称和目标引用。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [
            N2CNodeType.AddDelegate,
            N2CNodeType.AssignDelegate,
            N2CNodeType.CallDelegate,
            N2CNodeType.Message,
        ]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if not isinstance(data, dict):
            return

        # 提取委托名称
        delegate_name = data.get("delegate_name") or data.get("message_name")
        if delegate_name:
            definition.extra_data["delegate_name"] = delegate_name

        # 提取消息名称（K2Node_Message 专用）
        message_name = data.get("message_name")
        if message_name:
            definition.extra_data["message_name"] = message_name
