"""Cast 节点处理器 — 类型转换节点。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class CastProcessor(N2CNodeProcessor):
    """处理 DynamicCast 和 ClassDynamicCast 类型节点。

    提取转换目标类型。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.DynamicCast, N2CNodeType.ClassDynamicCast]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        target = None

        if isinstance(data, dict):
            target = (
                data.get("target_type")
                or data.get("cast_target")
                or data.get("target_class")
            )
        else:
            target = (
                getattr(data, "target_type", None)
                or getattr(data, "cast_target", None)
                or getattr(data, "target_class", None)
            )

        if target:
            definition.extra_data["target_type"] = str(target)
