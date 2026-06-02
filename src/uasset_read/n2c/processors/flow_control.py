"""FlowControl 节点处理器 — 分支/流程控制/循环节点。

覆盖 K2Node_IfThenElse、K2Node_ExecutionSequence、K2Node_Switch*、
K2Node_DoOnceMultiInput、K2Node_Select、K2Node_EaseFunction、
K2Node_MultiGate、K2Node_Knot 及 ForEach* 循环节点。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.constants import BRANCH_TYPE_MAP
from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class FlowControlProcessor(N2CNodeProcessor):
    """处理 Branch, Sequence, Switch*, Knot 等基础流程控制节点。

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
            N2CNodeType.Knot,
        ]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        class_name = node.class_name or ""
        branch_type = BRANCH_TYPE_MAP.get(class_name, "unknown")
        definition.extra_data["branch_type"] = branch_type
        definition.extra_data["stops_execution"] = True


class MultiGateProcessor(N2CNodeProcessor):
    """处理 K2Node_MultiGate 多门节点。

    多门节点有多个输出引脚，按顺序触发。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MultiGate]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        output_pins = [
            p for p in node.pins
            if getattr(p.pin_type, "pin_direction", "") == "EGPD_Output"
        ]
        definition.extra_data["gate_type"] = "multi_gate"
        definition.extra_data["output_count"] = len(output_pins)


class DoOnceProcessor(N2CNodeProcessor):
    """处理 K2Node_DoOnceMultiInput 单次执行节点。

    只执行一次，需要显式 Reset 才能再次触发。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.DoOnce]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["gate_type"] = "do_once"
        definition.extra_data["stops_execution"] = True


class SelectProcessor(N2CNodeProcessor):
    """处理 K2Node_Select 选择节点。

    根据 Index 引脚的值选择对应的输出分支。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.Select]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["gate_type"] = "select"


class EaseFunctionProcessor(N2CNodeProcessor):
    """处理 K2Node_EaseFunction 缓动函数节点。

    提供缓动曲线插值功能。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.EaseFunction]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["ease_function"] = True


class ForEachEnumProcessor(N2CNodeProcessor):
    """处理 K2Node_ForEachElementInEnum 枚举遍历节点。

    遍历枚举类型的所有值。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.ForEachEnum]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if isinstance(data, dict):
            enum_name = data.get("enum_type") or data.get("enum_name")
            if enum_name:
                definition.extra_data["enum_type"] = enum_name
        else:
            enum_name = getattr(data, "enum_type", None) or getattr(data, "enum_name", None)
            if enum_name:
                definition.extra_data["enum_type"] = enum_name


class MapForEachProcessor(N2CNodeProcessor):
    """处理 K2Node_MapForEach Map 遍历节点。

    遍历 Map 容器的键值对。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MapForEach]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["container_type"] = "map"
        definition.extra_data["loop_type"] = "for_each"


class SetForEachProcessor(N2CNodeProcessor):
    """处理 K2Node_SetForEach Set 遍历节点。

    遍历 Set 容器的元素。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.SetForEach]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["container_type"] = "set"
        definition.extra_data["loop_type"] = "for_each"
