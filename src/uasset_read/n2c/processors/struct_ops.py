"""Struct/Container/Cast 节点处理器 — 结构体与容器操作。

覆盖 K2Node_MakeStruct、K2Node_BreakStruct、K2Node_MakeArray、
K2Node_MakeMap、K2Node_MakeSet、K2Node_DynamicCast、
K2Node_ClassDynamicCast。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class MakeStructProcessor(N2CNodeProcessor):
    """处理 K2Node_MakeStruct 结构体创建节点。

    提取结构体类型和输入字段。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MakeStruct]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            definition.extra_data["operation"] = "make_struct"
            return

        data = node.node_data
        struct_type = None

        if isinstance(data, dict):
            struct_type = data.get("struct_type") or data.get("struct_class")
        else:
            struct_type = getattr(data, "struct_type", None) or getattr(data, "struct_class", None)

        if struct_type:
            definition.extra_data["struct_type"] = str(struct_type)
        definition.extra_data["operation"] = "make_struct"


class BreakStructProcessor(N2CNodeProcessor):
    """处理 K2Node_BreakStruct 结构体解构节点。

    提取结构体类型和输出字段。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.BreakStruct]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            definition.extra_data["operation"] = "break_struct"
            return

        data = node.node_data
        struct_type = None

        if isinstance(data, dict):
            struct_type = data.get("struct_type") or data.get("struct_class")
        else:
            struct_type = getattr(data, "struct_type", None) or getattr(data, "struct_class", None)

        if struct_type:
            definition.extra_data["struct_type"] = str(struct_type)
        definition.extra_data["operation"] = "break_struct"


class MakeArrayProcessor(N2CNodeProcessor):
    """处理 K2Node_MakeArray 数组创建节点。

    提取输入元素数量。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MakeArray]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "make_array"
        definition.extra_data["container_type"] = "array"
        input_pins = [
            p for p in node.pins
            if getattr(p.pin_type, "pin_direction", "") != "EGPD_Output"
        ]
        definition.extra_data["element_count"] = len(input_pins)


class MakeMapProcessor(N2CNodeProcessor):
    """处理 K2Node_MakeMap Map 创建节点。

    提取键值对数量。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MakeMap]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "make_map"
        definition.extra_data["container_type"] = "map"


class MakeSetProcessor(N2CNodeProcessor):
    """处理 K2Node_MakeSet Set 创建节点。

    提取元素数量。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MakeSet]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        definition.extra_data["operation"] = "make_set"
        definition.extra_data["container_type"] = "set"


class StructOpsProcessor(N2CNodeProcessor):
    """统一处理 MakeStruct/BreakStruct 结构体操作节点。

    提取结构体类型和操作方向。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.MakeStruct, N2CNodeType.BreakStruct]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        op = "make_struct" if definition.node_type == N2CNodeType.MakeStruct else "break_struct"
        definition.extra_data["operation"] = op

        if node.node_data is None:
            return

        data = node.node_data
        struct_type = None

        if isinstance(data, dict):
            struct_type = data.get("struct_type") or data.get("struct_class")
        else:
            struct_type = getattr(data, "struct_type", None) or getattr(data, "struct_class", None)

        if struct_type:
            definition.extra_data["struct_type"] = str(struct_type)


class CastOpsProcessor(N2CNodeProcessor):
    """处理 DynamicCast 和 ClassDynamicCast 类型转换节点。

    提取转换目标类型和转换方式。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.DynamicCast, N2CNodeType.ClassDynamicCast]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        cast_type = (
            "class_dynamic_cast"
            if definition.node_type == N2CNodeType.ClassDynamicCast
            else "dynamic_cast"
        )
        definition.extra_data["cast_type"] = cast_type

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
