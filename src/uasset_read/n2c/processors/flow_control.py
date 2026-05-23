"""FlowControl 节点处理器 — 分支/流程控制节点。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.constants import BRANCH_TYPE_MAP
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class FlowControlProcessor(N2CNodeProcessor):
    """处理 Branch, Sequence, Switch* 等流程控制节点。

    从 BRANCH_TYPE_MAP 查找分支类型，标记终止执行。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [
            N2CNodeType.Branch,
            N2CNodeType.Sequence,
            N2CNodeType.SwitchInt,
            N2CNodeType.SwitchString,
            N2CNodeType.SwitchEnum,
        ]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        class_name = node.class_name or ""
        branch_type = BRANCH_TYPE_MAP.get(class_name, "unknown")
        definition.extra_data["branch_type"] = branch_type
        definition.extra_data["stops_execution"] = True
